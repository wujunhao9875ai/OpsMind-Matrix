# Multi-Agent + Harness Engineering 架构设计

> 版本: v1.0 | 日期: 2026-08-04 | 状态: 设计阶段

---

## 零、架构背景

### 当前架构问题

前三个项目（运维客服、自动派单、库房管理）当前采用**单体扩展模式**：所有模块共享同一个代码库、数据库和 Docker 编排。这种模式在项目初期降低了开发成本，但随着系统演进暴露出以下问题：

1. **耦合严重**：项目间通过内部函数调用通信，一个模块的变更可能影响其他模块
2. **无法独立部署**：任何改动都需要全量重新部署
3. **故障不隔离**：一个模块的异常（如 OCR 服务内存泄漏）可能拖垮整个系统
4. **扩展粒度粗**：无法按模块负载独立扩缩容
5. **技术栈绑定**：所有模块必须使用相同的技术栈和依赖版本

### 目标架构

将三个业务 Agent 拆分为独立服务，通过标准化的 MCP（Multi-agent Communication Protocol）协议通信，由 Orchestrator（协调器）统一路由和编排，实现：

- **独立开发**：每个 Agent 拥有独立的代码库、数据库和部署单元
- **独立部署**：可单独上线、回滚、扩缩容
- **故障隔离**：单个 Agent 故障不影响其他服务
- **标准化通信**：MCP 协议定义统一的 Tools 和 Resources 接口
- **弹性伸缩**：Harness 层提供服务发现、负载均衡和健康检查

---

## 一、整体架构

```
                        ┌─────────────────────────────┐
                        │     前端 (Vue 3 SPA)         │
                        │  员工端 / 管理端 / 工程师端    │
                        │  库管员端 / 统一入口          │
                        └─────────────┬───────────────┘
                                      │ HTTP/WebSocket (JWT)
                                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Orchestrator Agent (协调器)                    │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ 全局意图  │  │ 会话上下文│  │ 服务发现  │  │ 结果聚合/降级  │  │
│  │ 路由分发  │  │ 管理     │  │ 负载均衡  │  │                │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    MCP Client 层                           │   │
│  │  - 统一调用各 Agent 的 MCP Tools                          │   │
│  │  - 支持超时/重试/降级                                      │   │
│  │  - 跨 Agent 编排（如备件申请联动）                          │   │
│  │  - 全链路 traceId 追踪                                     │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────┬──────────────────┬──────────────────┬────────────┘
               │ MCP Protocol     │                  │
               ▼                  ▼                  ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  Ops Agent       │ │  Dispatch Agent  │ │  Warehouse Agent │
│  (MCP Server)    │ │  (MCP Server)    │ │  (MCP Server)    │
│                  │ │                  │ │                  │
│ Tools:           │ │ Tools:           │ │ Tools:           │
│ - rag_search     │ │ - create_ticket  │ │ - stock_in       │
│ - intent_classify│ │ - assign_ticket  │ │ - stock_out      │
│ - prefill_ticket │ │ - query_tickets  │ │ - device_query   │
│ - chat_reply     │ │ - get_engineers  │ │ - ocr_recognize  │
│                  │ │ - urge_ticket    │ │ - spare_request  │
│                  │ │ - resolve_ticket │ │ - inventory_check│
│                  │ │                  │ │                  │
│ Resources:       │ │ Resources:       │ │ Resources:       │
│ - knowledge://*  │ │ - ticket://*     │ │ - device://*     │
│ - conversation://│ │ - engineer://*   │ │ - inventory://*  │
│                  │ │ - sla://*        │ │ - location://*   │
└──────────────────┘ └──────────────────┘ └──────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    共享基础设施 (Harness)                         │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ Consul   │  │ Redis    │  │ Nginx    │  │ Docker Compose  │  │
│  │ 服务注册  │  │ 会话/Pub  │  │ 反向代理  │  │ 容器编排        │  │
│  │ 健康检查  │  │ /负载计数 │  │ 负载均衡  │  │                 │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    可观测性平台                             │   │
│  │  - 结构化日志（JSON，携带 traceId）                         │   │
│  │  - 全链路追踪（Orchestrator → Agent）                       │   │
│  │  - 健康检查端点（/health）                                  │   │
│  │  - 指标监控（Prometheus + Grafana，可选）                    │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、Orchestrator（协调器）设计

### 2.1 职责

| 职责 | 说明 |
|------|------|
| **全局意图路由** | 分析用户消息，决定调用哪个 Agent（或哪些 Agent） |
| **会话上下文** | 维护跨 Agent 的用户会话状态（Redis），任意 Orchestrator 实例均可接管 |
| **服务发现** | 通过 Consul/Redis 感知各 Agent 实例的健康状态，动态获取节点列表 |
| **负载均衡** | 加权轮询选择健康的 Agent 实例 |
| **跨 Agent 编排** | 当需要多个 Agent 协作时，Orchestrator 编排调用链（如 dispatch → warehouse） |
| **降级兜底** | Agent 不可用时返回友好提示，不丢消息 |
| **全链路追踪** | 生成 traceId 并下传至各 Agent，所有日志携带 traceId |

### 2.2 请求处理流程

```
用户消息 → Orchestrator WebSocket 接收 (JWT 鉴权)
              │
              ▼
      ┌─ 全局意图分类 ──────────────┐
      │ 识别：intent + target_agent │
      │ 规则匹配 + LLM 兜底          │
      └───────┬─────────────────────┘
              │
    ┌─────────┼─────────────┬──────────────┐
    ▼         ▼             ▼              ▼
  ops     dispatch      warehouse      跨 Agent
  Agent    Agent         Agent         编排
    │         │             │              │
    │         │             │    ┌─────────┴─────────┐
    │         │             │    │ 备件申请联动：      │
    │         │             │    │ 1. dispatch.       │
    │         │             │    │    query_tickets   │
    │         │             │    │ 2. warehouse.      │
    │         │             │    │    spare_request   │
    │         │             │    │ 3. 聚合结果         │
    │         │             │    └───────────────────┘
    └─────────┴─────────────┘
              │
              ▼
      结果聚合（流式推送）
              │
              ▼
      WebSocket 推送完成 + traceId
```

### 2.3 全局意图定义

| 意图 | 目标 Agent | 示例 |
|------|-----------|------|
| `consult` | ops | "打印机怎么用" |
| `repair` | ops → dispatch | "打印机坏了，帮我报修" |
| `check_progress` | dispatch | "我的工单处理到哪了" |
| `ticket_manage` | dispatch | "把WO-001派给王工" |
| `warehouse_op` | warehouse | "入库5个墨盒" |
| `spare_request` | dispatch → warehouse | "WO-001需要更换墨盒" |
| `query_stats` | dispatch / warehouse | "今天完成多少工单" |

### 2.4 跨 Agent 编排

当用户请求涉及多个 Agent 时，Orchestrator 负责编排调用链：

```
示例：工程师申请备件
Orchestrator 收到 → 识别为 spare_request
  │
  ├─ 1. 调用 dispatch.query_tickets(ticket_id)
  │      → 确认工单状态为 in_progress
  │
  ├─ 2. 调用 warehouse.spare_request(item_name, quantity, ticket_id)
  │      → 创建备件申请，通知库管员
  │
  └─ 3. 聚合结果 → 流式推送
         "已为工单 WO-001 申请 HP 12A 墨盒 × 1，等待库管员备货"
```

---

## 三、MCP 协议标准化

### 3.1 协议概述

每个业务 Agent 作为 MCP Server，通过标准化的 Tools 和 Resources 对外暴露能力。Orchestrator 通过 MCP Client 调用各 Agent。

### 3.2 Ops Agent 接口

**Tools：**

| Tool | 参数 | 返回 | 说明 |
|------|------|------|------|
| `rag_search` | query: str, conversation_id: str | 流式 answer + sources | 知识库检索问答 |
| `intent_classify` | message: str | intent + confidence | 意图分类 |
| `prefill_ticket` | conversation_id: str | pre_ticket JSON | 生成预填工单 |
| `chat_reply` | message: str, conversation_id: str | 流式 reply | 对话回复（含槽位填充） |

**Resources：**

| URI | 说明 |
|-----|------|
| `knowledge://{doc_id}` | 知识库文档内容 |
| `conversation://{session_id}` | 会话历史消息 |

### 3.3 Dispatch Agent 接口

**Tools：**

| Tool | 参数 | 返回 | 说明 |
|------|------|------|------|
| `create_ticket` | pre_ticket_id / manual_fields | ticket JSON | 创建正式工单 |
| `assign_ticket` | ticket_id: str, engineer_id: str (optional) | assignment result | 派单/自动派单 |
| `query_tickets` | filters: dict, page: int, page_size: int | ticket list + total | 查询工单列表 |
| `get_engineers` | status: str (optional) | engineer list | 获取工程师状态 |
| `urge_ticket` | ticket_id: str | urge result | 催单 |
| `resolve_ticket` | ticket_id: str, resolution: str | resolve result | 解决/关闭工单 |
| `reassign_ticket` | ticket_id: str, engineer_id: str | reassign result | 改派工单 |
| `cancel_ticket` | ticket_id: str, reason: str | cancel result | 取消工单 |

**Resources：**

| URI | 说明 |
|-----|------|
| `ticket://{ticket_id}` | 工单详情 |
| `engineer://{engineer_id}` | 工程师详情 |
| `sla://{ticket_id}` | SLA 状态 |

### 3.4 Warehouse Agent 接口

**Tools：**

| Tool | 参数 | 返回 | 说明 |
|------|------|------|------|
| `stock_in` | item_name: str, quantity: int, location: str | inventory result | 入库 |
| `stock_out` | item_name: str, quantity: int, ticket_id: str | inventory result | 出库 |
| `device_query` | filters: dict | device list | 设备查询 |
| `ocr_recognize` | image: bytes | extracted fields | OCR 铭牌识别 |
| `spare_request` | item_name: str, quantity: int, ticket_id: str | request result | 备件申请 |
| `inventory_check` | item_name: str (optional) | inventory status | 库存查询 |
| `device_status_change` | device_id: str, action: str | device result | 设备状态变更 |
| `transfer_device` | device_id: str, from_loc: str, to_loc: str | transfer result | 设备调拨 |

**Resources：**

| URI | 说明 |
|-----|------|
| `device://{device_id}` | 设备详情 |
| `inventory://{item_id}` | 库存详情 |
| `location://{location_id}` | 库房信息 |

### 3.5 MCP 调用约定

- **传输协议**：HTTP/SSE（Streamable HTTP），WebSocket 用于流式推送
- **超时**：默认 30s，流式调用无超时
- **重试**：幂等操作自动重试 3 次（指数退避 1s→2s→4s）
- **降级**：Agent 不可用时返回预设友好提示
- **认证**：JWT token 通过 MCP 调用上下文传递
- **追踪**：所有调用携带 `traceId` header

---

## 四、数据架构

### 4.1 数据库拆分

每个 Agent 拥有独立的 PostgreSQL 数据库，通过 API 而非共享数据库通信：

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ ops_db       │  │ dispatch_db  │  │ warehouse_db │
│              │  │              │  │              │
│ conversations│  │ tickets      │  │ devices      │
│ messages     │  │ ticket_logs  │  │ inventory    │
│ knowledge    │  │ engineers    │  │ transactions │
│ pre_tickets  │  │ urge_records │  │ spare_reqs   │
│ user_profiles│  │              │  │ locations    │
│              │  │              │  │ device_logs  │
└──────────────┘  └──────────────┘  └──────────────┘
```

### 4.2 数据关联策略

由于数据库拆分，原有的 FK 外键关联改为逻辑关联：

| 关联关系 | 旧方案 | 新方案 |
|----------|--------|--------|
| 预填工单 → 正式工单 | FK `pre_ticket_id` | `pre_ticket_id` 字段存储，跨库查询通过 dispatch API |
| 工单 → 原始会话 | FK `conversation_id` | `conversation_id` 字段存储，跨库查询通过 ops API |
| 工单 → 备件申请 | FK `consumable_id` | `ticket_id` + `item_name` 逻辑关联，通过 warehouse API |
| 用户 | 共享 users 表 | 各 Agent 维护 `user_id` 引用，Orchestrator 统一认证 |

### 4.3 共享 Redis

Redis 保留为共享基础设施，用途：

| 用途 | 说明 |
|------|------|
| 会话状态 | 跨 Agent 的用户会话上下文 |
| Pub/Sub 通知 | 实时消息推送（工单指派、备件备货等） |
| 负载计数 | 工程师实时负载（Redis 原子操作） |
| 服务注册 | Agent 实例心跳 + 健康状态 |

---

## 五、Harness 层设计

### 5.1 服务发现

```
每个 Agent 实例启动时 → 向 Consul 注册
  - service_name: "ops-agent" / "dispatch-agent" / "warehouse-agent"
  - address:port
  - health_check: HTTP GET /health
  - tags: ["version=1.0", "mcp"]

Orchestrator 启动时 → 从 Consul 拉取所有 Agent 实例列表
  → 订阅变更通知 → 动态更新路由表
```

### 5.2 负载均衡

```
Orchestrator 维护每个 Agent 的实例池：
  - 加权轮询选择实例
  - 权重 = 1 / (当前请求数 + 1)
  - 健康检查失败 3 次 → 自动剔除
  - 恢复后自动加入
```

### 5.3 健康检查

| 检查项 | 端点 | 间隔 | 超时 | 失败阈值 |
|--------|------|------|------|---------|
| Agent 存活 | GET /health | 10s | 3s | 3 次 |
| MCP 可用 | list_tools | 30s | 5s | 2 次 |
| 数据库连接 | /health 内部检查 | 10s | 3s | 3 次 |

### 5.4 降级策略

| 场景 | 处理 |
|------|------|
| Agent 全部不可用 | 返回"系统繁忙，请稍后重试" |
| Agent 部分不可用 | 路由到健康实例，记录告警日志 |
| Agent 超时 | 重试另一个实例，仍失败则降级 |
| 跨 Agent 编排中某 Agent 失败 | 已完成的步骤不回滚，未完成的返回友好提示 |

---

## 六、项目目录结构

```
f:\mysite\
├── orchestrator/                    # 协调器（新增）
│   ├── backend/
│   │   ├── main.py                  # 统一入口 (FastAPI)
│   │   ├── router.py                # 全局意图路由
│   │   ├── mcp_client.py            # MCP 客户端
│   │   ├── orchestrator.py          # 跨 Agent 编排引擎
│   │   ├── session.py               # 跨 Agent 会话管理
│   │   ├── discovery.py             # 服务发现 (Consul)
│   │   └── config.py                # 配置管理
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── ops-agent/                       # 项目1：智能运维客服 Agent
│   ├── backend/
│   │   ├── main.py                  # MCP Server 入口
│   │   ├── mcp_server.py            # MCP 工具注册
│   │   ├── app/
│   │   │   ├── core/
│   │   │   │   ├── rag_engine.py
│   │   │   │   ├── intent_classifier.py
│   │   │   │   ├── ticket_generator.py
│   │   │   │   ├── query_rewriter.py
│   │   │   │   ├── memory_manager.py
│   │   │   │   ├── llm_adapter.py
│   │   │   │   ├── reranker.py
│   │   │   │   └── bm25_retriever.py
│   │   │   ├── models/
│   │   │   ├── tasks/               # Celery 异步任务
│   │   │   └── utils/
│   │   └── tests/
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── dispatch-agent/                  # 项目2：自动派单 Agent
│   ├── backend/
│   │   ├── main.py
│   │   ├── mcp_server.py
│   │   ├── app/
│   │   │   ├── core/
│   │   │   │   ├── ticket_state_machine.py
│   │   │   │   ├── dispatch_engine.py
│   │   │   │   ├── notification.py
│   │   │   │   └── admin_nlu.py
│   │   │   ├── models/
│   │   │   ├── tasks/               # SLA 监控 + 催单
│   │   │   └── utils/
│   │   └── tests/
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── warehouse-agent/                 # 项目3：库房管理 Agent
│   ├── backend/
│   │   ├── main.py
│   │   ├── mcp_server.py
│   │   ├── app/
│   │   │   ├── core/
│   │   │   │   ├── device_state_machine.py
│   │   │   │   ├── warehouse_service.py
│   │   │   │   ├── ocr_service.py
│   │   │   │   ├── storekeeper_nlu.py
│   │   │   │   └── inventory_guard.py
│   │   │   ├── models/
│   │   │   ├── tasks/               # 库存监控 + 呆滞检查
│   │   │   └── utils/
│   │   └── tests/
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── data-platform/                   # 项目4：AI 数据中台
│   ├── backend/
│   │   ├── main.py
│   │   ├── mcp_server.py
│   │   └── app/
│   │       ├── core/
│   │       │   ├── data_collector.py
│   │       │   ├── data_cleaner.py
│   │       │   └── material_factory.py
│   │       ├── models/
│   │       └── tasks/
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── frontend/                        # 统一前端
│   └── src/
│       ├── views/
│       │   ├── ChatView.vue
│       │   ├── AdminDashboard.vue
│       │   ├── EngineerWorkbench.vue
│       │   ├── StorekeeperDashboard.vue
│       │   └── LoginView.vue
│       ├── components/
│       │   ├── ChatInput.vue
│       │   ├── ChatWindow.vue
│       │   ├── MainLayout.vue
│       │   ├── MessageBubble.vue
│       │   └── SessionSidebar.vue
│       ├── composables/
│       │   ├── useWebSocket.ts              # 通用 WebSocket 连接
│       │   ├── useStorekeeperWebSocket.ts   # 库管员专用 WebSocket
│       │   └── useUnifiedWebSocket.ts       # 统一 WebSocket（支持多 Agent）
│       ├── stores/
│       │   ├── chat.ts
│       │   ├── orchestration.ts        # 前端编排状态
│       │   └── ticket.ts
│       ├── types/
│       │   └── index.ts
│       ├── router/
│       │   └── index.ts
│       ├── App.vue
│       ├── api.ts
│       └── main.ts
│
├── docker-compose.yml              # 顶层编排（一键启动全部）
├── 运维 AI Agent 平台 — 需求文档（PRD）.md
└── docs/
    ├── architecture/
    │   └── multi-agent-design.md   # 本文档
    ├── project1-ops-agent.md
    ├── project2-dispatch-agent.md
    ├── project3-warehouse-agent.md
    └── superpowers/
        ├── specs/
        │   └── 2026-08-04-multi-agent-architecture.md
        └── plans/
            └── archive/             # 已归档的旧实现计划
```

---

## 七、Docker 服务编排

### 顶层 docker-compose.yml

```yaml
services:
  # ===== Harness 基础设施 =====
  consul:
    image: consul:1.15
    ports: ["8500:8500"]

  nginx:
    image: nginx:alpine
    ports: ["80:80"]
    volumes: ["./nginx.conf:/etc/nginx/nginx.conf"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  # ===== Orchestrator =====
  orchestrator:
    build: ./orchestrator
    ports: ["8000:8000"]
    depends_on: [consul, redis]

  # ===== 业务 Agent =====
  ops-agent:
    build: ./ops-agent
    depends_on: [consul, redis]

  vllm:
    image: vllm/vllm-openai:latest
    ports: ["8002:8000"]

  dispatch-agent:
    build: ./dispatch-agent
    depends_on: [consul, redis]

  warehouse-agent:
    build: ./warehouse-agent
    depends_on: [consul, redis]

  paddleocr:
    image: paddlepaddle/paddleocr:latest
    ports: ["8866:8866"]

  # ===== 前端 =====
  frontend:
    build: ./frontend
    ports: ["3000:80"]

  # ===== 数据中台 =====
  data-platform:
    build: ./data-platform
    depends_on: [consul, redis]
```

---

## 八、迁移策略

从当前单体架构迁移到 Multi-agent 架构，分四个阶段渐进式推进：

### 阶段一：代码拆分（无架构变更）

- 将 `project1-ops-agent/` 中的 dispatch、warehouse 相关代码拆分到独立目录
- 保持共享数据库，仅做代码组织调整
- 验证所有功能正常

### 阶段二：数据库拆分

- 为 dispatch-agent 和 warehouse-agent 创建独立数据库
- 迁移数据，更新 FK 关联为逻辑关联
- 通过 API 调用替代跨库直接查询

### 阶段三：MCP 协议化

- 每个 Agent 实现 MCP Server 接口
- Orchestrator 实现 MCP Client 调用
- 前端统一连接到 Orchestrator

### 阶段四：Harness 集成

- 接入 Consul 服务发现
- 实现健康检查和负载均衡
- 全链路追踪和降级策略

---

## 九、风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 数据库拆分导致数据不一致 | 中 | 高 | 渐进式迁移，每阶段充分测试；关键数据保留双向同步过渡期 |
| MCP 调用增加网络延迟 | 高 | 中 | Agent 同 Docker 网络部署，延迟 < 5ms；Orchestrator 缓存频繁查询结果 |
| 服务发现故障导致路由失败 | 低 | 高 | Consul 集群部署；Orchestrator 本地缓存 Agent 列表兜底 |
| 跨 Agent 编排的分布式事务 | 中 | 中 | 采用最终一致性 + 补偿机制；关键操作先写日志再执行 |
| 现有代码重构量大 | 高 | 中 | 分阶段迁移，新旧架构并行运行过渡期 |