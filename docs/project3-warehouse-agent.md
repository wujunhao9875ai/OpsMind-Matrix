# 项目3：Warehouse Agent（库房管理）— 技术方案

> 版本: v2.1 | 日期: 2026-08-04 | 状态: 设计阶段（Multi-Agent + Harness Engineering 架构）

---

## 架构变更说明

**v1.0 → v2.0 核心变更：** Warehouse Agent 从项目1/2 代码库中拆分出来，成为独立的 MCP Server。不再与 Dispatch Agent 共享数据库，而是通过 MCP 协议接收备件申请并异步通知。自身保留设备状态机、库存管理、OCR 识别、库存监控等核心能力。

---

## 零、问题陈述

Dispatch Agent 已实现工单全生命周期管理，工程师在处理工单时可以记录耗材/设备使用。但当前库房管理仍依赖人工：

1. **无系统化库存管理**：设备的入库、出库、调拨全靠纸质记录或 Excel
2. **备件申请无闭环**：工程师在工单中记录了耗材使用，但库管员不知道、库存未扣减
3. **设备生命周期无追踪**：设备从采购→入库→出库→维修→报废，状态流转无记录
4. **出入库操作低效**：库管员需要手动录入序列号、型号
5. **库存告警缺失**：常用耗材耗尽时才发现；呆滞设备长期占用库存
6. **设备铭牌信息录入慢**：手动输入序列号、型号容易出错

**本方案要解决的核心问题：** 作为独立 MCP Server，实现设备全生命周期管理、自然语言出入库、OCR 铭牌识别、备件申请联动、库存监控告警。通过 Orchestrator 编排与 Dispatch Agent 联动，完成备件申请→库管确认→扣减库存的闭环。

---

## 方案对比与选择

| 维度 | 方案 A：扩展项目1/2（v1.0） | 方案 B：独立 MCP Server（选中，v2.0） |
|------|----------------------------|--------------------------------------|
| **代码组织** | 与 Ops/Dispatch 共用代码库 | 独立代码库，MCP 协议通信 |
| **数据共享** | 共享 PostgreSQL，直接关联 | 独立数据库，通过 MCP 传递标识 |
| **备件申请联动** | 同库事务，内部函数调用 | Orchestrator 编排 MCP 调用链 |
| **OCR 集成** | 共享 Docker 网络 | 独立 PaddleOCR 服务 |
| **故障隔离** | 无隔离 | 独立故障域 |

**选择方案 B 的理由：** Warehouse Agent 的 OCR 服务是 GPU 密集型，独立部署后可针对性配置硬件资源。与 Dispatch Agent 的备件申请联动通过 Orchestrator 编排，调用链清晰可追踪，便于排查问题。

---

## 关键决策

| 决策点 | 结论 |
|--------|------|
| 架构模式 | 独立 MCP Server，通过 Orchestrator 接收请求 |
| 设备状态机 | 有限状态机管理设备生命周期（7 状态），数据库事务+乐观锁 |
| 备件申请联动 | 通过 Orchestrator 编排，Dispatch 调用 `warehouse.spare_request` |
| 自然语言操作 | 复用 NLU 模式（意图分类+槽位提取），操作对象为库房管理 |
| OCR 方案 | 本地 PaddleOCR Docker 服务，HTTP API 调用 |
| 库存扣减 | 数据库事务内完成，version 字段乐观锁 |
| 库存告警 | Celery 定时任务 + 阈值配置，WebSocket 实时推送（通过 Orchestrator） |
| 权限控制 | JWT role：storekeeper |

---

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                   Orchestrator（协调器）                         │
│   路由 warehouse_op / spare_request 等意图 → Warehouse Agent     │
│   跨 Agent 编排：Dispatch.spare_request → Warehouse 处理         │
└─────────────────────────────┬───────────────────────────────────┘
                              │ MCP Protocol
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Warehouse Agent (MCP Server)                    │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────────┐  ┌───────────┐  │
│  │ MCP Tools        │  │ 设备状态机            │  │ OCR 服务  │  │
│  │ - stock_in       │  │ - 7 状态定义          │  │ - Paddle  │  │
│  │ - stock_out      │  │ - 转换规则            │  │ - 结构化  │  │
│  │ - device_query   │  │ - 乐观锁              │  │   提取    │  │
│  │ - ocr_recognize  │  │                      │  │          │  │
│  │ - spare_request  │  │                      │  │          │  │
│  │ - inventory_check│  │                      │  │          │  │
│  │ - device_status  │  │                      │  │          │  │
│  │ - transfer_device│  │                      │  │          │  │
│  └────────┬─────────┘  └───────────┬──────────┘  └─────┬─────┘  │
│           │                        │                    │        │
│           ▼                        ▼                    ▼        │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │              基础设施（Agent 私有）                          │   │
│  │  PostgreSQL  │  Redis (缓存/Pub-Sub/库存锁)  │  Celery     │   │
│  └────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、MCP Tool 定义

| Tool | 参数 | 返回 | 说明 |
|------|------|------|------|
| `stock_in` | inventory_id, quantity, operator_id, unit_price, comment | inventory result | 入库 |
| `stock_out` | inventory_id, quantity, operator_id, related_ticket_id, comment | inventory result | 出库 |
| `device_query` | device_id, serial_number, device_no, status, search, page, page_size | device list | 设备查询 |
| `ocr_recognize` | image_base64 | extracted fields | OCR 铭牌识别 |
| `spare_request` | item_name, quantity, ticket_id, operator_id | request result | 备件申请（接收 Dispatch 调用） |
| `inventory_check` | inventory_id, search, low_stock_only, page, page_size | inventory status | 库存查询 + 低库存标记 |
| `device_status_change` | device_id, action, operator_id, comment, repair_vendor, repair_cost, related_ticket_id | device result | 设备状态变更（触发状态机） |
| `transfer_device` | device_id, to_location_id, operator_id, comment | transfer result | 设备调拨 |
| `create_device` | serial_number, name, model, category, brand, location_id, purchase_price, supplier, notes | device JSON | 创建设备记录 |
| `create_inventory` | name, category, model_spec, unit, quantity, min_threshold, max_threshold, unit_price, location_id | inventory JSON | 创建库存物品 |
| `get_locations` | (无) | location list | 获取库房位置列表 |
| `create_location` | name, code, address, status, description | location JSON | 创建库房位置 |
| `update_location` | location_id, name, address, status, description | location JSON | 更新库房位置 |
| `delete_location` | location_id | delete result | 删除库房位置 |
| `warehouse_overview` | (无) | overview JSON | 库房概览统计 |
| `device_logs` | device_id | log list | 设备操作日志 |
| `inventory_transactions` | inventory_id, page, page_size | transaction list | 库存交易记录 |
| `spare_requests` | status, ticket_id, page, page_size | request list | 备件申请列表 |
| `approve_spare` | request_id, operator_id | approve result | 批准备件申请 |
| `reject_spare` | request_id, reason, operator_id | reject result | 拒绝备件申请 |
| `fulfill_spare` | request_id, operator_id | fulfill result | 完成备件申请（扣减库存） |

**MCP Resources：**

| URI | 说明 |
|-----|------|
| `device://{device_id}` | 设备详情 |
| `inventory://{item_id}` | 库存详情 |
| `location://{location_id}` | 库房信息 |

---

## 三、设备生命周期状态机（保持 v1.0 设计）

设备 7 状态（in_stock/allocated/in_use/damaged/in_repair/repaired/scrapped）、状态转换规则、副作用处理等核心设计保持不变，详见 v1.0 文档第三章。

---

## 四、备件申请联动（MCP 编排）

```
Dispatch Agent 工单处理中 → 工程师记录耗材使用
    │
    ▼
Orchestrator 编排调用链:
  1. dispatch.query_tickets(ticket_id) → 确认工单状态
  2. warehouse.spare_request(item_name, quantity, ticket_id)
    │
    ▼
Warehouse Agent 处理:
  - 匹配 inventory 表库存物品
  - 库存充足 → 创建 spare_part_requests (status=pending)
  - 库存不足 → 标记"库存不足"，通知库管员采购
    │
    ▼
库管员工作台: 待备货列表更新
  - WebSocket 推送通知库管员（通过 Orchestrator 中转）
    │
    ▼
库管员确认备货 → warehouse.spare_request 状态更新 → 扣减库存
    │
    ▼
异步通知 Dispatch Agent（通过 Orchestrator 编排回调）
```

---

## 五、数据模型设计

Warehouse Agent 拥有独立的 `warehouse_db` 数据库：

- **warehouse_locations**：库房/库位表
- **devices**：设备表（含乐观锁 version 字段）
- **inventory**：库存表（耗材类物品，含乐观锁）
- **inventory_transactions**：库存流水表
- **device_logs**：设备操作日志表
- **spare_part_requests**：备件申请表

> 详细字段定义与 v1.0 文档第四章保持一致。

**与 Dispatch Agent 的数据关联：** `spare_part_requests.ticket_id` 存储 Dispatch Agent 的工单 ID 字符串，不再使用跨库 FK。`devices.consumable_id` 存储关联标识，不再使用跨库 FK。

---

## 六、项目目录结构

```
f:\mysite\warehouse-agent\
├── docker-compose.yml              # Agent 私有服务编排
├── Dockerfile
├── backend/
│   ├── requirements.txt
│   ├── main.py                     # MCP Server 入口
│   ├── mcp_server.py               # MCP 工具注册
│   ├── app/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── api/
│   │   │   ├── health.py
│   │   │   └── ocr_api.py          # OCR 内部 REST API
│   │   ├── core/
│   │   │   ├── device_state_machine.py
│   │   │   ├── warehouse_service.py
│   │   │   ├── ocr_service.py
│   │   │   ├── storekeeper_nlu.py
│   │   │   ├── spare_request_service.py
│   │   │   ├── inventory_guard.py
│   │   │   └── logger.py
│   │   ├── models/
│   │   │   ├── warehouse_location.py
│   │   │   ├── device.py
│   │   │   ├── inventory.py
│   │   │   ├── inventory_transaction.py
│   │   │   ├── device_log.py
│   │   │   └── spare_part_request.py
│   │   ├── schemas/
│   │   │   ├── warehouse.py
│   │   │   └── ocr.py
│   │   ├── tasks/
│   │   │   ├── celery_app.py
│   │   │   └── warehouse_tasks.py    # 库存监控 + 呆滞检查 + 备件申请任务 + 周报
│   │   └── utils/
│   │       └── prompts.py
│   └── tests/
```

---

## 七、Harness Engineering 集成

### 7.1 Consul 服务注册

Warehouse Agent 启动时自动向 Consul 注册，Orchestrator 通过 Consul 发现并路由请求：

```python
# mcp_server.py 启动流程
async def register_to_consul():
    await consul.register_service(
        name="warehouse-agent",
        address="warehouse-agent",
        port=8000,
        tags=["mcp", "version=1.0"],
        health_check={
            "http": "http://warehouse-agent:8000/health",
            "interval": "10s",
            "timeout": "3s",
            "deregister_critical_after": "30s"
        }
    )
    # 注册 MCP Tools 到 Consul KV
    await consul.kv_put("mcp/tools/warehouse/stock_in", {...})
    await consul.kv_put("mcp/tools/warehouse/stock_out", {...})
    await consul.kv_put("mcp/tools/warehouse/device_query", {...})
    await consul.kv_put("mcp/tools/warehouse/ocr_recognize", {...})
    await consul.kv_put("mcp/tools/warehouse/spare_request", {...})
    await consul.kv_put("mcp/tools/warehouse/inventory_check", {...})
    await consul.kv_put("mcp/tools/warehouse/device_status_change", {...})
    await consul.kv_put("mcp/tools/warehouse/transfer_device", {...})
```

### 7.2 健康检查端点

`GET /health` 返回 Agent 及依赖服务的健康状态：

```json
{
  "status": "healthy",
  "service": "warehouse-agent",
  "version": "1.0.0",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "paddleocr": "ok"
  },
  "timestamp": "2026-08-04T10:30:00Z"
}
```

### 7.3 traceId 全链路追踪

- **接收**：从 MCP 调用 Header `X-Trace-Id` 提取 traceId（Orchestrator 生成并传入）
- **传递**：所有内部日志、Celery 任务、状态机事件、Redis Pub/Sub 消息携带 traceId
- **上报**：响应中附加 `traceId` 和 `duration_ms`，供 Orchestrator 聚合

```python
# logger.py 结构化日志格式
{
  "timestamp": "2026-08-04T10:30:00.123Z",
  "level": "INFO",
  "traceId": "a1b2c3d4-...",
  "service": "warehouse-agent",
  "tool": "stock_out",
  "step": "inventory_deduction",
  "item_name": "HP 12A 墨盒",
  "quantity": 1,
  "ticket_id": "WO-001",
  "duration_ms": 23,
  "message": "Inventory deducted with optimistic lock"
}
```

### 7.4 数据上报

所有库房操作日志、设备状态变更、备件消耗数据通过 Celery 异步写入 AI 数据中台：

```python
# 出入库操作后异步上报
@celery_app.task(queue="data_collect")
async def report_to_data_platform(event: dict, trace_id: str):
    await redis.lpush("data_collect", json.dumps({
        "event_id": str(uuid4()),
        "source_agent": "warehouse",
        "event_type": event["type"],
        "timestamp": datetime.utcnow().isoformat(),
        "trace_id": trace_id,
        "payload": event
    }))
```

### 7.5 降级策略

Warehouse Agent 依赖多个外部服务，需定义各依赖不可用时的降级行为：

| 依赖故障 | 检测方式 | 降级行为 |
|---------|---------|---------|
| PaddleOCR 不可用 | OCR 请求超时（10s）或连接拒绝 | 返回提示"OCR 识别服务暂不可用，请手动输入设备信息"；出入库操作不受影响，仅跳过 OCR 自动填充 |
| PostgreSQL 不可用 | 查询超时或连接池耗尽 | 出入库操作无法执行，返回"系统繁忙，请稍后重试"；库存扣减必须在事务内完成，不可降级 |
| Redis 不可用 | 连接超时或拒绝 | Pub/Sub 通知失效，库管员无法收到实时备件申请推送；降级为轮询模式（每 5s 查 DB 待处理备件申请） |
| Celery Worker 不可用 | 任务投递失败 | 库存监控和呆滞检查定时任务无法执行，降级为 Warehouse Agent 主进程内定时器兜底；数据上报跳过 |
| 乐观锁冲突 | version 不匹配（重试 3 次后仍失败） | 返回"操作冲突，请刷新后重试"；说明有其他库管员正在操作同一物品 |

**降级恢复机制：** 所有依赖每 30s 自动重试连接，恢复后自动从 degraded 状态切回 healthy。降级期间 `/health` 端点返回 `status: "degraded"` 及具体故障项。库存监控恢复后自动补检上次检查周期内的库存变化。

---

## 八、Docker 服务编排

```yaml
# warehouse-agent/docker-compose.yml
services:
  warehouse-agent:
    build: .
    ports: ["8300:8000"]
    environment:
      - DATABASE_URL=postgresql+asyncpg://warehouse:pass@postgres:5432/warehouse_db
      - REDIS_URL=redis://redis:6379/0
      - PADDLEOCR_URL=http://paddleocr:8866
      - CONSUL_URL=http://consul:8500
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s

  postgres:
    image: postgres:17
    environment:
      POSTGRES_DB: warehouse_db

  redis:
    image: redis:7-alpine

  paddleocr:
    image: paddlepaddle/paddleocr:latest
    ports: ["8866:8866"]

  celery_worker:
    build: .
    command: celery -A app.tasks.celery_app worker -Q warehouse --loglevel=info
```

---

## 九、向下串联

所有库房操作日志（入库/出库/调拨/报废）、设备状态变更记录、备件消耗数据通过 Celery 异步写入 AI 数据中台，为后续模型微调提供数据基础。