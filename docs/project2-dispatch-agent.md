# 项目2：Dispatch Agent（自动派单）— 技术方案

> 版本: v2.1 | 日期: 2026-08-04 | 状态: 设计阶段（Multi-Agent + Harness Engineering 架构）

---

## 架构变更说明

**v1.0 → v2.0 核心变更：** Dispatch Agent 从项目1 代码库中拆分出来，成为独立的 MCP Server。不再与 Ops Agent 共享数据库，而是通过 MCP 协议接收预填工单。需要备件时通过 Orchestrator 编排调用 Warehouse Agent 的 MCP Tool。自身保留工单状态机、派单引擎、SLA 监控等核心能力。

---

## 零、问题陈述

Ops Agent 已实现预填工单生成，但缺少后续处理链路：

1. **无正式工单**：预填工单需要转为正式工单、生成唯一工单号
2. **无派单机制**：工单无法自动分配给合适的工程师
3. **无工单生命周期管理**：从接单→处理→解决→关闭没有状态追踪
4. **无超时监控**：紧急工单可能被搁置，缺少催办和 SLA 保障
5. **工程师工作无载体**：工程师没有自己的工作台

**本方案要解决的核心问题：** 作为独立 MCP Server，接收 Ops Agent 的预填工单，实现工单自动创建、智能派发、全生命周期管理、超时监控催办，提供管理员自然语言操作和工程师工作台。

---

## 方案对比与选择

| 维度 | 方案 A：扩展项目1（v1.0） | 方案 B：独立 MCP Server（选中，v2.0） |
|------|--------------------------|--------------------------------------|
| **代码组织** | 与 Ops Agent 共用代码库 | 独立代码库，MCP 协议通信 |
| **数据共享** | 共享 PostgreSQL，直接关联 | 独立数据库，通过 MCP 传递标识 |
| **部署** | 同一 docker-compose | 独立容器，按需扩缩 |
| **故障隔离** | 无隔离 | 独立故障域 |
| **扩展性** | 整体扩展 | 按需独立扩展派单引擎 |

**选择方案 B 的理由：** Dispatch Agent 的派单引擎和 SLA 监控是 CPU 密集型任务，独立部署后可针对性扩容。与 Warehouse Agent 的备件申请联动通过 Orchestrator 编排，形成清晰的调用链，便于追踪和调试。

---

## 关键决策

| 决策点 | 结论 |
|--------|------|
| 架构模式 | 独立 MCP Server，通过 Orchestrator 接收请求 |
| 正式工单创建 | 通过 MCP Tool `create_ticket` 接收预填工单或手动创建 |
| 派单算法 | 加权评分模型：技能匹配(40%) + 负载率(30%) + 负载均衡(20%) + 历史表现(10%) |
| 工单状态机 | LangGraph 定义 6 状态 |
| 实时通知 | Redis Pub/Sub 多进程广播 + WebSocket 推送（通过 Orchestrator 中转） |
| 负载统计 | Redis 原子计数器，Celery 定时同步到 PostgreSQL |
| 与 Warehouse 通信 | 通过 Orchestrator 编排，MCP 调用 `warehouse.spare_request` |
| 权限控制 | JWT role 字段：user/engineer/admin |

---

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                   Orchestrator（协调器）                         │
│   路由 ticket_manage / spare_request 等意图 → Dispatch Agent     │
└─────────────────────────────┬───────────────────────────────────┘
                              │ MCP Protocol
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Dispatch Agent (MCP Server)                    │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────────┐  ┌───────────┐  │
│  │ MCP Tools        │  │ 派单引擎              │  │ 通知服务  │  │
│  │ - create_ticket  │  │ - 加权评分            │  │ - Pub/Sub │  │
│  │ - assign_ticket  │  │ - 技能匹配            │  │ - 催办推送│  │
│  │ - query_tickets  │  │ - 负载均衡            │  │ - 状态通知│  │
│  │ - get_engineers  │  │                      │  │          │  │
│  │ - urge_ticket    │  │                      │  │          │  │
│  │ - resolve_ticket │  │                      │  │          │  │
│  │ - reassign_ticket│  │                      │  │          │  │
│  │ - cancel_ticket  │  │                      │  │          │  │
│  └────────┬─────────┘  └───────────┬──────────┘  └─────┬─────┘  │
│           │                        │                    │        │
│           ▼                        ▼                    ▼        │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │              基础设施（Agent 私有）                          │   │
│  │  PostgreSQL  │  Redis (会话/负载计数/Pub-Sub)  │  Celery   │   │
│  └────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、MCP Tool 定义

| Tool | 参数 | 返回 | 说明 |
|------|------|------|------|
| `create_ticket` | title, description, urgency, fault_category, device_info, location, created_by | ticket JSON | 创建正式工单 |
| `assign_ticket` | ticket_id, engineer_id (optional) | assignment result | 派单/自动派单 |
| `query_tickets` | status, urgency, engineer_id, ticket_no, created_by, page, page_size | ticket list + total | 查询工单列表 |
| `get_engineers` | status (optional) | engineer list | 获取工程师状态和负载 |
| `urge_ticket` | ticket_id | urge result | 催单 |
| `resolve_ticket` | ticket_id, resolution | resolve result | 解决/关闭工单 |
| `reassign_ticket` | ticket_id, new_engineer_id, reason | reassign result | 改派工单 |
| `cancel_ticket` | ticket_id, reason | cancel result | 取消工单 |
| `create_engineer` | user_id, display_name, skills, skill_levels, status, location | engineer JSON | 创建工程师档案 |
| `reopen_ticket` | ticket_id, reason | reopen result | 重开已关闭工单 |
| `change_priority` | ticket_id, urgency | update result | 变更工单优先级 |
| `accept_ticket` | ticket_id, engineer_id | accept result | 工程师接单 |
| `reject_ticket` | ticket_id, reason, engineer_id | reject result | 工程师拒单 |
| `get_stats` | (无) | stats JSON | 工单统计（总量/状态分布/紧急度分布/超时/未分配） |

**MCP Resources：**

| URI | 说明 |
|-----|------|
| `ticket://{ticket_id}` | 工单详情 |
| `engineer://{engineer_id}` | 工程师详情 |
| `sla://{ticket_id}` | SLA 状态 |

---

## 三、工单状态机（保持 v1.0 设计）

工单 6 状态（created/assigned/in_progress/resolved/closed/cancelled）、状态转换规则、副作用处理等核心设计保持不变，详见 v1.0 文档第三章。

---

## 四、派单引擎（保持 v1.0 设计）

加权评分模型、筛选流程、负载统计方案、待分配池等核心设计保持不变，详见 v1.0 文档第六章。

---

## 五、数据模型设计

Dispatch Agent 拥有独立的 `dispatch_db` 数据库：

- **tickets**：正式工单表（含 `pre_ticket_id` 字段，存储 Ops Agent 的预填工单 ID）
- **ticket_logs**：工单操作日志表
- **engineer_profiles**：工程师画像表
- **urge_records**：催办记录表

> 详细字段定义与 v1.0 文档第四章保持一致。

**与 Ops Agent 的数据关联：** `tickets.pre_ticket_id` 存储 Ops Agent 预填工单的 ID 字符串，不再使用跨库 FK。

**与 Warehouse Agent 的数据关联：** 备件申请通过 Orchestrator 编排 MCP 调用实现，Dispatch Agent 不直接持有 Warehouse 的数据引用。

---

## 六、项目目录结构

```
f:\mysite\dispatch-agent\
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
│   │   │   └── health.py
│   │   ├── core/
│   │   │   ├── ticket_state_machine.py
│   │   │   ├── dispatch_engine.py
│   │   │   ├── notification.py
│   │   │   ├── admin_nlu.py
│   │   │   └── logger.py
│   │   ├── models/
│   │   │   ├── ticket.py
│   │   │   ├── ticket_log.py
│   │   │   ├── engineer.py
│   │   │   └── urge_record.py
│   │   ├── schemas/
│   │   │   └── dispatch.py
│   │   ├── tasks/
│   │   │   ├── celery_app.py
│   │   │   └── monitor_tasks.py    # SLA 监控 + 催单 + 数据上报
│   │   └── utils/
│   │       └── prompts.py
│   └── tests/
```

---

## 七、Harness Engineering 集成

### 7.1 Consul 服务注册

Dispatch Agent 启动时自动向 Consul 注册，Orchestrator 通过 Consul 发现并路由请求：

```python
# mcp_server.py 启动流程
async def register_to_consul():
    await consul.register_service(
        name="dispatch-agent",
        address="dispatch-agent",
        port=8000,
        tags=["mcp", "version=1.0"],
        health_check={
            "http": "http://dispatch-agent:8000/health",
            "interval": "10s",
            "timeout": "3s",
            "deregister_critical_after": "30s"
        }
    )
    # 注册 MCP Tools 到 Consul KV
    await consul.kv_put("mcp/tools/dispatch/create_ticket", {...})
    await consul.kv_put("mcp/tools/dispatch/assign_ticket", {...})
    await consul.kv_put("mcp/tools/dispatch/query_tickets", {...})
    await consul.kv_put("mcp/tools/dispatch/get_engineers", {...})
    await consul.kv_put("mcp/tools/dispatch/urge_ticket", {...})
    await consul.kv_put("mcp/tools/dispatch/resolve_ticket", {...})
    await consul.kv_put("mcp/tools/dispatch/reassign_ticket", {...})
    await consul.kv_put("mcp/tools/dispatch/cancel_ticket", {...})
```

### 7.2 健康检查端点

`GET /health` 返回 Agent 及依赖服务的健康状态：

```json
{
  "status": "healthy",
  "service": "dispatch-agent",
  "version": "1.0.0",
  "checks": {
    "database": "ok",
    "redis": "ok"
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
  "service": "dispatch-agent",
  "tool": "assign_ticket",
  "step": "dispatch_engine",
  "ticket_id": "WO-001",
  "engineer_id": "eng_003",
  "score_breakdown": {"skill": 38, "load": 28, "balance": 18, "history": 8},
  "duration_ms": 45,
  "message": "Ticket assigned to engineer"
}
```

### 7.4 数据上报

所有工单操作日志、派单记录、SLA 事件通过 Celery 异步写入 AI 数据中台：

```python
# 工单状态变更后异步上报
@celery_app.task(queue="data_collect")
async def report_to_data_platform(event: dict, trace_id: str):
    await redis.lpush("data_collect", json.dumps({
        "event_id": str(uuid4()),
        "source_agent": "dispatch",
        "event_type": event["type"],
        "timestamp": datetime.utcnow().isoformat(),
        "trace_id": trace_id,
        "payload": event
    }))
```

### 7.5 降级策略

Dispatch Agent 依赖多个外部服务，需定义各依赖不可用时的降级行为：

| 依赖故障 | 检测方式 | 降级行为 |
|---------|---------|---------|
| PostgreSQL 不可用 | 查询超时或连接池耗尽 | 工单操作无法执行，返回"系统繁忙，请稍后重试"；Redis 中的工程师负载计数继续工作 |
| Redis 不可用 | 连接超时或拒绝 | Pub/Sub 通知失效，降级为轮询模式（每 5s 查 DB）；工程师负载计数降级为 DB 查询（精度下降但可用） |
| Celery Worker 不可用 | 任务投递失败 | SLA 监控定时任务无法执行，降级为 Dispatch Agent 主进程内定时器兜底；数据上报跳过 |
| Celery Beat 不可用 | 定时任务未触发 | SLA 监控和催单任务失效，记录 CRITICAL 日志；管理员手动触发检查 |

**降级恢复机制：** 所有依赖每 30s 自动重试连接，恢复后自动从 degraded 状态切回 healthy。降级期间 `/health` 端点返回 `status: "degraded"` 及具体故障项。SLA 监控恢复后自动补检遗漏的工单。

---

## 八、Docker 服务编排

```yaml
# dispatch-agent/docker-compose.yml
services:
  dispatch-agent:
    build: .
    ports: ["8200:8000"]
    environment:
      - DATABASE_URL=postgresql+asyncpg://dispatch:pass@postgres:5432/dispatch_db
      - REDIS_URL=redis://redis:6379/0
      - CONSUL_URL=http://consul:8500
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s

  postgres:
    image: postgres:17
    environment:
      POSTGRES_DB: dispatch_db

  redis:
    image: redis:7-alpine

  celery_worker:
    build: .
    command: celery -A app.tasks.celery_app worker -Q dispatch --loglevel=info

  celery_beat:
    build: .
    command: celery -A app.tasks.celery_app beat --loglevel=info
```

---

## 九、向下串联

工单处理中若工程师判定需要更换备件，通过 Orchestrator 编排，以 MCP 协议调用 `warehouse.spare_request` 传递备件型号、数量、工单信息。所有工单操作日志和工程师绩效数据通过 Celery 异步写入 AI 数据中台。