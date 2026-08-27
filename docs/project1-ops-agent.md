# 项目1：Ops Agent（智能运维客服）— 技术方案

> 版本: v2.1 | 日期: 2026-08-04 | 状态: 设计阶段（Multi-Agent + Harness Engineering 架构）

---

## 架构变更说明

**v1.0 → v2.0 核心变更：** Ops Agent 从单体架构的一部分拆分为独立的 MCP Server，通过 Orchestrator 协调器接收前端请求。不再直接与 Dispatch Agent 共享数据库，而是通过 MCP 协议传递预填工单。自身保留 RAG 引擎、意图分类、多轮对话等核心能力，作为 MCP Tools 对外暴露。

---

## 零、问题陈述

运维团队每天处理大量重复咨询（打印机卡纸、网络不通、账号异常），80% 是已知问题，但员工仍需排队等待人工响应。当前痛点：

1. **响应慢**：人工平均响应 15 分钟，员工体验差
2. **效率低**：工程师被琐碎咨询占满，无法专注复杂故障
3. **无沉淀**：每次解决问题后知识未系统化，新人上手困难
4. **无闭环**：报修后无自动化工单流转，依赖人工记录和派发

**本方案要解决的核心问题：** 构建一个基于本地大模型的运维智能客服，作为独立的 MCP Server，能自动回答 60% 的常见问题，无法解答时通过 MCP 协议生成预填工单并传递给 Dispatch Agent，为后续派单系统提供标准化输入。

---

## 方案对比与选择

| 维度 | 方案 A：单体扩展（v1.0） | 方案 B：MCP Server（选中，v2.0） |
|------|--------------------------|--------------------------------|
| **代码组织** | 与 Dispatch/Warehouse 共用代码库 | 独立代码库，MCP 协议通信 |
| **通信方式** | 内部函数调用 + 共享数据库 | MCP Tools/Resources |
| **部署** | 全量 docker-compose | 独立容器，按需扩缩 |
| **故障隔离** | 无隔离 | 独立故障域 |
| **扩展性** | 整体扩展 | 按需独立扩展 RAG 服务 |
| **开发独立性** | 共享依赖版本 | 独立技术栈和依赖 |

**选择方案 B 的理由：** Ops Agent 作为用户入口，是系统中负载最高的服务。独立部署后可针对 RAG 检索和 LLM 推理独立扩容，不影响其他 Agent。MCP 协议标准化后，后续可无缝替换底层 LLM 或升级 RAG 策略。

---

## 关键决策

| 决策点 | 结论 |
|--------|------|
| 架构模式 | 独立 MCP Server，通过 Orchestrator 接收前端请求 |
| 知识库来源 | 混合模式（文档导入 + 人工补充） |
| 模型策略 | 架构模型无关，生产用千问，测试用 DeepSeek 1.5B |
| 部署方式 | 独立 Docker 容器，通过顶层 docker-compose 编排 |
| 并发规模 | 按生产级设计（Redis + Celery + 异步） |
| 短期记忆 | 滑动窗口 + 对话摘要压缩 |
| 长期记忆 | 结构化查询（SQL）+ 轻量用户画像 |
| RAG 增强 | 检索前问题改写 + 混合检索（向量+BM25）+ Rerank 重排 |
| 流式输出 | WebSocket 逐 token 推送（通过 Orchestrator 中转） |
| 安全鉴权 | JWT 认证 + Rate Limit（Orchestrator 统一鉴权后传递） |
| 与 Dispatch 通信 | 通过 Orchestrator 编排，MCP 调用 `dispatch.create_ticket` |

---

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                   Orchestrator（协调器）                         │
│        全局意图路由 → 判定为 consult/repair → 路由至 Ops Agent    │
└─────────────────────────────┬───────────────────────────────────┘
                              │ MCP Protocol
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Ops Agent (MCP Server)                       │
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ MCP 工具  │ │ 意图路由  │ │问题改写器│ │ RAG 引擎  │          │
│  │ 注册      │ │(规则+模型)│ │(LLM改写) │ │(LangChain)│          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ 会话管理  │ │ 工单生成器│ │记忆管理  │ │ 反馈收集  │          │
│  │(Redis)   │ │(LangChain)│ │(摘要+画像)│ │(Celery)  │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    基础设施（Agent 私有）                   │   │
│  │  PostgreSQL  │  Redis  │  PGVector │  vLLM   │  Celery    │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**核心设计要点：**

- **MCP Server 入口**：通过 `mcp_server.py` 注册 Tools 和 Resources，暴露给 Orchestrator 调用。使用自定义 `SimpleMCP` 类适配 MCP 协议（替代 `FastMCP`，避免依赖版本兼容问题）
- **LLM 适配器层**：封装 vLLM/SiliconFlow 调用，通过配置切换模型，业务代码不感知模型差异。生产环境使用 SiliconFlow API（千问系列），本地开发使用 vLLM
- **意图路由**：独立于 LangChain 的轻量分类器，先规则匹配，再小模型兜底
- **RAG 引擎**：使用 LangChain `RetrievalQA` 链，Prompt 模板外部化
- **流式输出**：通过 MCP 的 SSE 传输逐 token 推送，Orchestrator 中转至前端
- **异步写入**：消息落库、分类标注、反馈处理通过 Celery 异步处理

---

## 二、MCP Tool 定义

| Tool | 参数 | 返回 | 说明 |
|------|------|------|------|
| `rag_search` | query: str, conversation_id: str | 流式 answer + sources | 知识库检索问答 |
| `intent_classify` | message: str | intent + confidence | 意图分类 |
| `prefill_ticket` | conversation_id: str | pre_ticket JSON | 生成预填工单 |
| `chat_reply` | message: str, conversation_id: str | 流式 reply | 多轮对话回复（含槽位填充） |

**MCP Resources：**

| URI | 说明 |
|-----|------|
| `knowledge://{doc_id}` | 知识库文档内容 |
| `conversation://{session_id}` | 会话历史消息 |

---

## 三、核心请求处理流程

```
Orchestrator 路由 → Ops Agent MCP Tool 调用
                        │
                        ▼
               ┌─ 意图路由分类器 ─┐
               │  (规则 + 小模型)  │
               └──────┬──────────┘
                      │
           ┌──────────┼──────────────┐
           ▼          ▼              ▼
         报修       咨询           查进度
           │          │              │
           │          ▼              │
           │    ┌─ 问题改写 ─┐       │
           │    │ (LLM 改写) │       │
           │    └─────┬─────┘       │
           │          ▼              │
           │    ┌─ RAG 混合检索 ─┐   │
           │    │ 向量+BM25+Rerank│   │
           │    └─────┬──────────┘   │
           │          ▼              │
           │    ┌─ 置信度检查 ─┐     │
           │    └────┬─────────┘     │
           │    ┌────┼────┐          │
           │    ▼    ▼    ▼          │
           │  高置信   低置信         │
           │    │      │             │
           │    ▼      ▼             │
           │  返回    转人工          │
           │  答案   (工单)           │
           │    │                     │
           └────┼─────────────────────┘
                │
                ▼
        流式输出（SSE → Orchestrator → 前端）
```

---

## 四、RAG 检索增强（保持 v1.0 设计）

Parent-Child 分块策略、混合检索 + RRF 融合 + Rerank 精排、Answer Coverage Guard 等 RAG 核心设计保持不变，详见 v1.0 文档的三、六、九、十四章节。

---

## 五、数据模型设计

Ops Agent 拥有独立的 `ops_db` 数据库，包含以下核心表：

- **conversations**：会话表
- **messages**：消息表（含三级分类标签）
- **user_profiles**：用户画像表
- **knowledge_docs**：知识库文档
- **knowledge_chunks**：文档分块（Parent-Child 结构）
- **pre_tickets**：预填工单

> 详细字段定义与 v1.0 文档第四、五、六章节保持一致。

**与 Dispatch Agent 的数据关联：** `pre_tickets.id` 以字符串形式传递至 Dispatch Agent 的 `create_ticket` MCP Tool，不再使用跨库 FK。

---

## 六、项目目录结构

```
f:\mysite\ops-agent\
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
│   │   │   ├── health.py           # 健康检查
│   │   │   └── knowledge.py        # 知识库管理（内部管理用）
│   │   ├── core/
│   │   │   ├── rag_engine.py       # 混合检索 + RAG
│   │   │   ├── intent_classifier.py
│   │   │   ├── query_rewriter.py
│   │   │   ├── ticket_generator.py
│   │   │   ├── session_manager.py
│   │   │   ├── memory_manager.py
│   │   │   ├── llm_adapter.py
│   │   │   ├── reranker.py
│   │   │   ├── bm25_retriever.py
│   │   │   └── logger.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── tasks/                  # Celery 异步任务
│   │   └── utils/
│   │       ├── prompts.py
│   │       ├── chunker.py
│   │       ├── coverage_guard.py
│   │       └── metrics.py
│   └── tests/
└── data/
    └── knowledge/                  # 知识库 Markdown 文档
```

---

## 七、Harness Engineering 集成

### 7.1 Consul 服务注册

Ops Agent 启动时自动向 Consul 注册，Orchestrator 通过 Consul 发现并路由请求：

```python
# mcp_server.py 启动流程
async def register_to_consul():
    await consul.register_service(
        name="ops-agent",
        address="ops-agent",
        port=8000,
        tags=["mcp", "version=1.0"],
        health_check={
            "http": "http://ops-agent:8000/health",
            "interval": "10s",
            "timeout": "3s",
            "deregister_critical_after": "30s"
        }
    )
    # 注册 MCP Tools 到 Consul KV
    await consul.kv_put("mcp/tools/ops/rag_search", {...})
    await consul.kv_put("mcp/tools/ops/intent_classify", {...})
    await consul.kv_put("mcp/tools/ops/prefill_ticket", {...})
    await consul.kv_put("mcp/tools/ops/chat_reply", {...})
```

### 7.2 健康检查端点

`GET /health` 返回 Agent 及依赖服务的健康状态：

```json
{
  "status": "healthy",
  "service": "ops-agent",
  "version": "1.0.0",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "pgvector": "ok",
    "vllm": "ok"
  },
  "timestamp": "2026-08-04T10:30:00Z"
}
```

### 7.3 traceId 全链路追踪

- **接收**：从 MCP 调用 Header `X-Trace-Id` 提取 traceId（Orchestrator 生成并传入）
- **传递**：所有内部日志、Celery 任务、数据库操作携带 traceId
- **上报**：响应中附加 `traceId` 和 `duration_ms`，供 Orchestrator 聚合

```python
# logger.py 结构化日志格式
{
  "timestamp": "2026-08-04T10:30:00.123Z",
  "level": "INFO",
  "traceId": "a1b2c3d4-...",
  "service": "ops-agent",
  "tool": "rag_search",
  "step": "vector_retrieval",
  "duration_ms": 234,
  "user_id": "user_001",
  "message": "Retrieved 5 chunks from PGVector"
}
```

### 7.4 数据上报

所有对话记录和操作日志通过 Celery 异步写入 AI 数据中台，不阻塞主流程：

```python
# 消息发送后异步上报
@celery_app.task(queue="data_collect")
async def report_to_data_platform(event: dict, trace_id: str):
    await redis.lpush("data_collect", json.dumps({
        "event_id": str(uuid4()),
        "source_agent": "ops",
        "event_type": event["type"],
        "timestamp": datetime.utcnow().isoformat(),
        "trace_id": trace_id,
        "payload": event
    }))
```

### 7.5 降级策略

Ops Agent 依赖多个外部服务，需定义各依赖不可用时的降级行为：

| 依赖故障 | 检测方式 | 降级行为 |
|---------|---------|---------|
| vLLM 不可用 | 推理请求超时（30s）或连接拒绝 | 返回预设友好回复："AI 引擎暂时繁忙，请稍后重试或联系人工客服"；不丢失用户消息 |
| PGVector 不可用 | 向量检索超时（5s）或连接失败 | 降级为纯 BM25 关键词检索；若 BM25 也不可用，返回"知识库暂时不可用，请描述问题，我们将为您转接工程师" |
| Redis 不可用 | 连接超时或拒绝 | 会话降级为内存存储（单实例内有效），无法跨实例共享；标记 degraded 状态 |
| PostgreSQL 不可用 | 查询超时或连接池耗尽 | 历史消息无法持久化，但当前对话不中断；消息暂存内存队列，恢复后批量写入 |
| Celery Worker 不可用 | 任务投递失败 | 异步任务（分类标注、反馈处理、数据上报）降级为同步执行或跳过，不影响主流程 |

**降级恢复机制：** 所有依赖每 30s 自动重试连接，恢复后自动从 degraded 状态切回 healthy。降级期间 `/health` 端点返回 `status: "degraded"` 及具体故障项，Consul 健康检查不会剔除（仅标记 degraded）。

---

## 八、Docker 服务编排

```yaml
# ops-agent/docker-compose.yml
services:
  ops-agent:
    build: .
    ports: ["8100:8000"]
    environment:
      - DATABASE_URL=postgresql+asyncpg://ops:pass@postgres:5432/ops_db
      - REDIS_URL=redis://redis:6379/0
      - VLLM_URL=http://vllm:8000
      - EMBEDDING_DIM=4096
      - CONSUL_URL=http://consul:8500
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s

  postgres:
    image: pgvector/pgvector:pg17
    environment:
      POSTGRES_DB: ops_db

  redis:
    image: redis:7-alpine

  vllm:
    image: vllm/vllm-openai:latest

  celery_worker:
    build: .
    command: celery -A app.tasks.celery_app worker --loglevel=info
```

---

## 九、向下串联

Ops Agent 生成的预填工单通过 Orchestrator 编排，以 MCP 协议调用 `dispatch.create_ticket` 传递至 Dispatch Agent，触发正式工单创建流程。所有对话记录和操作日志通过 Celery 异步写入 AI 数据中台。