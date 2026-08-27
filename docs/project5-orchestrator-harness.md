# 项目5：Orchestrator + Harness 集群 — 技术方案

> 版本: v1.0 | 日期: 2026-08-04 | 状态: 设计阶段（Harness Engineering 架构）

---

## 架构定位

**在 Multi-Agent + Harness 架构中的角色：** Orchestrator 是前端唯一入口，Harness 层是支撑整个 Multi-Agent 集群运行的基础设施。本项目将二者统一设计，实现从"功能可用"到"生产级弹性"的跨越。

**核心原则：** Orchestrator 无状态可水平扩展；Harness 层提供服务发现、负载均衡、健康检查、全链路追踪和降级兜底，确保任何单个 Agent 故障不影响整体服务。

---

## 零、问题陈述

当前项目1-4 的 Agent 设计已就绪，但从开发到生产部署存在以下基础设施缺口：

1. **无统一入口**：前端需要知道每个 Agent 的地址，无法做统一鉴权和路由
2. **无服务发现**：Agent 实例地址硬编码，新增/下线实例需要手动改配置
3. **无负载均衡**：Agent 多实例部署后，请求分发无策略
4. **无故障隔离**：单个 Agent 故障可能导致前端请求超时或报错
5. **无可观测性**：跨 Agent 调用链无法追踪，排查问题困难
6. **无弹性伸缩**：无法根据负载动态扩缩 Agent 实例

**本方案要解决的核心问题：** 实现 Orchestrator 协调器作为统一入口，集成 Harness 基础设施层，构建可弹性伸缩、故障自愈、全链路可追踪的生产级 Agent 集群。

---

## 方案对比与选择

| 维度 | 方案 A：K8s + Istio 服务网格 | 方案 B：Docker Compose + Consul（选中） |
|------|---------------------------|--------------------------------------|
| **复杂度** | 高，需要 K8s 集群运维能力 | 低，单机可运行，与现有 Docker Compose 一致 |
| **服务发现** | K8s Service + DNS | Consul 注册中心 |
| **负载均衡** | Istio sidecar | Nginx + Consul 健康检查 |
| **可观测性** | Istio telemetry | 结构化日志 + traceId |
| **部署门槛** | 需要 K8s 集群 | 单机 Docker 即可 |
| **迁移路径** | 直接生产级 | 预留 K8s Helm Chart，渐进迁移 |

**选择方案 B 的理由：** 当前阶段以 Windows 开发环境 + Docker 部署为主，K8s 引入运维复杂度远超收益。Docker Compose + Consul 方案降低部署门槛，同时在架构上预留 K8s 迁移路径（Consul 可替换为 K8s Service，Nginx 可替换为 Ingress）。

---

## 关键决策

| 决策点 | 结论 |
|--------|------|
| 架构模式 | Orchestrator 无状态 + Consul 服务发现 + Nginx 反向代理 |
| 服务注册 | Agent 启动时向 Consul 注册，通过 HTTP Health Check 维持心跳 |
| 负载均衡 | Orchestrator 维护实例池，加权轮询，权重 = 1/(当前请求数+1) |
| 会话管理 | Redis 集中存储会话上下文，任意 Orchestrator 实例可接管 |
| 全链路追踪 | Orchestrator 生成 traceId → 下传至各 Agent → 所有日志携带 |
| 降级策略 | Agent 不可用 → 返回友好提示；LLM 超时 → 降级至规则引擎 |
| 工具集市 | Consul KV 存储所有 MCP Tool 元数据，动态注册和发现 |
| K8s 迁移 | 预留 Helm Chart 目录结构，Consul → K8s Service 映射 |

---

## 一、整体架构

```
                            ┌─────────────────────────────┐
                            │     前端 (Vue 3 SPA)         │
                            │  员工端 / 管理端 / 工程师端    │
                            └─────────────┬───────────────┘
                                          │ HTTP/WebSocket (JWT)
                                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          Nginx (反向代理)                             │
│  路由: / → frontend | /api → orchestrator | /ws → orchestrator       │
│  限流: 100 req/s | 健康检查: /health                                 │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Orchestrator × N (无状态，可水平扩展)               │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────┐  │
│  │ 全局意图路由  │  │ 会话上下文    │  │ 服务发现      │  │ 结果聚合 │  │
│  │ (规则+LLM)   │  │ (Redis)      │  │ (Consul)     │  │ (流式)   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                     MCP Client 层                              │   │
│  │  - 加权轮询负载均衡（从 Consul 获取实例列表）                    │   │
│  │  - 超时 30s / 重试 3 次（指数退避 1s→2s→4s）                   │   │
│  │  - 跨 Agent 编排（如备件申请联动）                               │   │
│  │  - 全链路 traceId 生成与传递                                    │   │
│  │  - 降级兜底（Agent 不可用 → 友好提示）                          │   │
│  └──────────────────────────────────────────────────────────────┘   │
└───────┬──────────────┬──────────────┬──────────────┬────────────────┘
        │ MCP Protocol │              │              │
        ▼              ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
│Ops Agent │  │Dispatch  │  │Warehouse │  │Data Platform │
│(MCP)     │  │Agent(MCP)│  │Agent(MCP)│  │(MCP)         │
└──────────┘  └──────────┘  └──────────┘  └──────────────┘
        │              │              │              │
        └──────────────┴──────────────┴──────────────┘
                          │
┌─────────────────────────────────────────────────────────────────────┐
│                     Harness 基础设施层                                │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────────┐  │
│  │ Consul   │  │ Redis    │  │ Nginx    │  │ 可观测性            │  │
│  │ 服务注册  │  │ 会话/队列 │  │ 反向代理  │  │ 结构化日志          │  │
│  │ 健康检查  │  │ Pub/Sub  │  │ 负载均衡  │  │ traceId 全链路追踪  │  │
│  │ KV 存储  │  │ 负载计数 │  │ 限流     │  │ 健康检查端点        │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Orchestrator 核心设计

### 2.1 全局意图路由

```
用户消息 → Orchestrator WebSocket 接收 (JWT 鉴权)
              │
              ▼
      ┌─ 全局意图分类 ──────────────┐
      │                              │
      │ 第一层：规则匹配（毫秒级）     │
      │  ├─ 关键词匹配               │
      │  └─ 正则匹配                 │
      │                              │
      │ 第二层：LLM 兜底（规则未命中）│
      │  └─ 小模型意图分类           │
      └──────┬──────────────────────┘
             │
   ┌─────────┼─────────────┬──────────────┐
   ▼         ▼             ▼              ▼
 ops     dispatch      warehouse      跨 Agent
Agent    Agent         Agent         编排
```

**意图路由表：**

| 意图 | 目标 Agent | 关键词 | 示例 |
|------|-----------|--------|------|
| `consult` | ops | 怎么、如何、是什么、为什么 | "打印机怎么设置双面打印" |
| `repair` | ops → dispatch | 坏了、报修、故障、异常 | "打印机卡纸了，报修" |
| `check_progress` | dispatch | 进度、状态、处理、工单 | "我的工单 WO-001 处理到哪了" |
| `ticket_manage` | dispatch | 派单、指派、改派、取消 | "把 WO-001 派给王工" |
| `warehouse_op` | warehouse | 入库、出库、库存、设备 | "入库 5 个 HP 12A 墨盒" |
| `spare_request` | dispatch → warehouse | 备件、更换、耗材 | "WO-001 需要更换墨盒" |
| `query_stats` | dispatch / warehouse | 统计、报表、今天、本周 | "今天完成多少工单" |
| `data_query` | data-platform | 导出、数据集、分析 | "导出本月工单数据集" |

### 2.2 会话管理

```
会话上下文存储结构（Redis Hash）：
  session:{session_id}
    ├─ user_id: "user_001"
    ├─ role: "employee"
    ├─ current_agent: "ops"          # 当前对话的 Agent
    ├─ context: {JSON}               # 跨 Agent 上下文
    │   ├─ active_ticket_id: "WO-001"
    │   ├─ pre_ticket_id: "pre_001"
    │   └─ last_intent: "repair"
    ├─ message_history: [{JSON}]     # 最近 20 条消息
    └─ ttl: 3600                     # 1 小时过期

会话恢复策略：
  - Orchestrator 实例 A 故障 → Nginx 路由到实例 B
  - 实例 B 从 Redis 读取 session:{session_id} → 无缝接管
  - 用户无感知
```

### 2.3 跨 Agent 编排引擎

```
class OrchestrationEngine:
    """跨 Agent 编排引擎"""
    
    async def execute(self, plan: OrchestrationPlan, trace_id: str):
        """
        执行编排计划，支持顺序和并行步骤
        
        plan = {
            "steps": [
                {"agent": "dispatch", "tool": "query_tickets", "args": {...}},
                {"agent": "warehouse", "tool": "spare_request", "args": {...},
                 "depends_on": 0},  # 依赖第 0 步的结果
            ]
        }
        """
        results = {}
        for step in plan.steps:
            if step.depends_on:
                # 注入上一步结果
                step.args.update(results[step.depends_on])
            results[step.id] = await self.call_agent(step, trace_id)
        return self.aggregate(results)
```

**编排示例：备件申请联动**

```
输入: "WO-001 需要更换 HP 12A 墨盒"
输出: "已为工单 WO-001 申请 HP 12A 墨盒 x1，等待库管员备货"

编排步骤:
  1. dispatch.query_tickets(ticket_id="WO-001")
     → 确认工单状态为 in_progress，工程师: 王工
  2. warehouse.spare_request(item_name="HP 12A 墨盒", quantity=1, ticket_id="WO-001")
     → 创建备件申请，状态: pending
  3. 聚合结果 → 流式推送至前端
```

### 2.4 工具集市

```
Consul KV 存储 MCP Tool 元数据：

consul kv get mcp/tools/ops/rag_search
{
  "name": "rag_search",
  "agent": "ops-agent",
  "description": "知识库检索问答（流式输出）",
  "parameters": {
    "query": {"type": "string", "required": true},
    "conversation_id": {"type": "string", "required": true}
  },
  "returns": "流式 answer + sources",
  "auth_required": ["employee", "engineer", "admin"],
  "rate_limit": "20/min",
  "version": "1.0.0"
}

Orchestrator 启动时从 Consul 拉取全量工具注册表
→ 构建工具路由映射
→ 订阅 Consul KV 变更 → 热更新工具注册表
```

---

## 三、Harness 层详细设计

### 3.1 服务注册与发现（Consul）

```
Agent 启动流程:
  1. HTTP Server 启动
  2. 向 Consul 注册服务:
     PUT /v1/agent/service/register
     {
       "Name": "ops-agent",
       "Address": "ops-agent",
       "Port": 8000,
       "Check": {
         "HTTP": "http://ops-agent:8000/health",
         "Interval": "10s",
         "Timeout": "3s",
         "DeregisterCriticalServiceAfter": "30s"
       },
       "Tags": ["mcp", "version=1.0"]
     }
  3. 向 Consul KV 注册 MCP Tools
  4. 启动心跳维持

Orchestrator 启动流程:
  1. 连接 Consul
  2. 拉取所有 mcp 标签的服务列表
  3. 为每个服务构建实例池（InstancePool）
  4. 订阅 Consul 服务变更事件 → 动态更新实例池
  5. 从 Consul KV 拉取工具注册表
```

**实例池设计：**

```python
class InstancePool:
    """Agent 实例池，维护健康实例列表和负载均衡"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.instances: Dict[str, Instance] = {}  # id → Instance
        self.healthy: List[str] = []  # 健康实例 ID 列表
        self.round_robin_index = 0
    
    def get_instance(self) -> Instance:
        """加权轮询选择实例"""
        weights = [1 / (inst.active_requests + 1) for inst in self.healthy_instances]
        return weighted_round_robin(self.healthy_instances, weights)
    
    def on_health_change(self, instance_id: str, healthy: bool):
        """Consul 健康检查回调"""
        if healthy:
            self.healthy.append(instance_id)
        else:
            self.healthy.remove(instance_id)
```

### 3.2 负载均衡

| 策略 | 说明 |
|------|------|
| **加权轮询** | 默认策略，权重 = 1/(当前活跃请求数 + 1) |
| **最少连接** | 优先选择活跃请求数最少的实例 |
| **一致性哈希** | 同 session 路由到同实例（用于有状态中间件） |

### 3.3 健康检查矩阵

| 检查项 | 端点 | 间隔 | 超时 | 失败阈值 | 降级动作 |
|--------|------|------|------|---------|---------|
| Agent 存活 | GET /health | 10s | 3s | 3 次 | 从实例池移除 |
| MCP 可用 | list_tools() | 30s | 5s | 2 次 | 标记为 degraded |
| 数据库连接 | /health 内部检查 | 10s | 3s | 3 次 | 从实例池移除 |
| Redis 连接 | /health 内部检查 | 10s | 3s | 3 次 | 标记为 degraded |

### 3.4 全链路追踪

```
请求流程中的 traceId 传递:

前端 WebSocket 连接
  │
  ▼
Orchestrator 生成 traceId = uuid4()
  │
  ├─ 所有日志携带: {"traceId": "xxx", "step": "intent_classify"}
  │
  ├─ MCP 调用 Header: X-Trace-Id: xxx
  │
  ▼
Agent 接收请求
  │
  ├─ 从 Header 提取 traceId
  ├─ 所有日志携带: {"traceId": "xxx", "agent": "ops", "tool": "rag_search"}
  │
  └─ 返回时附加: {"traceId": "xxx", "agent": "ops", "duration_ms": 1234}
```

**日志格式规范：**

```json
{
  "timestamp": "2026-08-04T10:30:00.123Z",
  "level": "INFO",
  "traceId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "service": "orchestrator",
  "step": "agent_call",
  "target_agent": "ops-agent",
  "tool": "rag_search",
  "duration_ms": 1234,
  "status": "success",
  "user_id": "user_001",
  "message": "MCP call completed"
}
```

### 3.5 降级策略

| 场景 | 检测方式 | 处理 |
|------|---------|------|
| Agent 全部不可用 | 实例池为空 | 返回"系统繁忙，请稍后重试或联系管理员" |
| Agent 部分不可用 | 实例池数量 < 最小健康数 | 路由到健康实例，记录 WARN 日志 |
| Agent 超时 | 30s 无响应 | 重试另一个实例（最多 3 次），仍失败则降级 |
| LLM 超时 | 推理超时 | 降级至规则引擎返回预设答案 |
| 跨 Agent 编排中某步失败 | 步骤异常 | 已完成步骤不回滚，返回"部分操作已完成，请稍后重试" |
| Consul 不可用 | 连接断开 | 使用本地缓存的实例列表兜底，记录 ERROR 日志 |

### 3.6 安全设计

- **全链路 JWT 鉴权**：Nginx 验证 JWT 有效性 → Orchestrator 解析 role → 传递至 Agent
- **MCP 调用鉴权**：Orchestrator 在 MCP 调用 Header 中携带 JWT，Agent 验证 role 权限
- **工具级别鉴权**：工具集市中的每个 Tool 定义 `auth_required` 字段
- **Rate Limit**：Nginx 层 100 req/s 全局限制；Orchestrator 层按用户 20 req/min

---

## 四、项目目录结构

```
f:\mysite\orchestrator\
├── docker-compose.yml              # Orchestrator 私有服务编排
├── Dockerfile
├── backend/
│   ├── requirements.txt
│   ├── main.py                     # FastAPI 统一入口
│   ├── app/
│   │   ├── config.py
│   │   ├── api/
│   │   │   ├── health.py
│   │   │   ├── chat.py             # WebSocket 聊天入口
│   │   │   ├── auth.py             # JWT 鉴权
│   │   │   └── tools.py            # 工具集市 API
│   │   ├── core/
│   │   │   ├── router.py           # 全局意图路由
│   │   │   ├── intent_classifier.py # 全局意图分类
│   │   │   ├── mcp_client.py        # MCP 客户端（统一调用 Agent）
│   │   │   ├── orchestrator.py      # 跨 Agent 编排引擎
│   │   │   ├── graph.py             # LangGraph 状态机编排（意图分类→Agent调用→聚合）
│   │   │   ├── circuit_breaker.py   # 熔断器（Agent 故障隔离）
│   │   │   ├── harness_node.py      # Harness 节点（MCP 调用封装）
│   │   │   ├── discovery.py         # Consul 服务发现
│   │   │   ├── instance_pool.py     # 实例池 + 负载均衡
│   │   │   ├── session.py           # 跨 Agent 会话管理
│   │   │   ├── degrader.py          # 降级策略
│   │   │   ├── tracer.py            # traceId 生成与追踪
│   │   │   └── logger.py
│   │   ├── schemas/
│   │   │   ├── chat.py
│   │   │   ├── intent.py
│   │   │   └── tool.py
│   │   └── utils/
│   │       └── prompts.py          # 意图分类 LLM Prompt
│   └── tests/
│       ├── test_router.py
│       ├── test_orchestrator.py
│       └── test_discovery.py
├── nginx/
│   └── nginx.conf                  # 反向代理配置
├── consul/
│   └── consul-config.json          # Consul 初始配置
└── k8s/                            # 预留 K8s 迁移目录
    └── helm/
        └── values.yaml
```

---

## 五、Docker 服务编排

### 顶层 docker-compose.yml（完整集群）

```yaml
# f:\mysite\docker-compose.yml
version: "3.8"

services:
  # ===== Harness 基础设施 =====
  consul:
    image: consul:1.15
    ports: ["8500:8500"]
    command: agent -dev -client=0.0.0.0
    volumes:
      - ./orchestrator/consul/consul-config.json:/consul/config/config.json

  nginx:
    image: nginx:alpine
    ports: ["80:80"]
    volumes:
      - ./orchestrator/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - orchestrator

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  # ===== Orchestrator（可水平扩展） =====
  orchestrator:
    build: ./orchestrator
    ports: ["8000:8000"]
    environment:
      - REDIS_URL=redis://redis:6379/0
      - CONSUL_URL=http://consul:8500
    depends_on:
      - consul
      - redis
    deploy:
      replicas: 2  # 开发环境 2 副本

  # ===== 业务 Agent =====
  ops-agent:
    build: ./ops-agent
    environment:
      - CONSUL_URL=http://consul:8500
    depends_on:
      - consul
      - redis

  dispatch-agent:
    build: ./dispatch-agent
    environment:
      - CONSUL_URL=http://consul:8500
    depends_on:
      - consul
      - redis

  warehouse-agent:
    build: ./warehouse-agent
    environment:
      - CONSUL_URL=http://consul:8500
    depends_on:
      - consul
      - redis

  data-platform:
    build: ./data-platform
    environment:
      - CONSUL_URL=http://consul:8500
    depends_on:
      - consul
      - redis

  # ===== 前端 =====
  frontend:
    build: ./frontend
    ports: ["3000:80"]
    depends_on:
      - nginx

  # ===== 模型服务 =====
  vllm:
    image: vllm/vllm-openai:latest
    ports: ["8002:8000"]

  paddleocr:
    image: paddlepaddle/paddleocr:latest
    ports: ["8866:8866"]

  # ===== 可观测性（可选） =====
  # prometheus:
  #   image: prom/prometheus
  #   ports: ["9090:9090"]

  # grafana:
  #   image: grafana/grafana
  #   ports: ["3001:3000"]
```

### Nginx 配置

```nginx
# orchestrator/nginx/nginx.conf
upstream orchestrator {
    least_conn;
    server orchestrator:8000;
}

upstream frontend {
    server frontend:80;
}

server {
    listen 80;

    # 前端静态资源
    location / {
        proxy_pass http://frontend;
    }

    # API 请求 → Orchestrator
    location /api/ {
        proxy_pass http://orchestrator;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # WebSocket → Orchestrator
    location /ws/ {
        proxy_pass http://orchestrator;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400s;
    }
}
```

---

## 六、K8s 迁移预留

当系统规模增长（Agent 实例 > 10、日均请求 > 10 万），可迁移至 K8s：

| Docker Compose 组件 | K8s 对应 |
|---------------------|---------|
| Consul 服务注册 | K8s Service + DNS |
| Consul 健康检查 | K8s Liveness/Readiness Probe |
| Nginx 负载均衡 | K8s Ingress + Service |
| Docker Compose 编排 | K8s Deployment + StatefulSet |
| Redis 会话 | 保持 Redis，或迁移至 Redis Cluster |
| 结构化日志 | Fluentd → Elasticsearch |
| traceId 追踪 | Jaeger / Zipkin |

---

## 七、向下串联

Orchestrator + Harness 集群为模型微调（项目6）提供稳定的基础设施：

- **A/B 测试**：Orchestrator 根据流量比例路由到不同版本的 Ops Agent（原始模型 vs 微调模型）
- **灰度发布**：新模型先部署到 10% 实例，观察指标后全量切换
- **数据采集**：全链路 traceId 确保数据中台可追溯每次请求的完整调用链
- **弹性伸缩**：微调后的模型推理负载增加时，Harness 层自动扩容 Agent 实例