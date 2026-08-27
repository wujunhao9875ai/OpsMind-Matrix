# 项目4：AI 数据中台 — 技术方案

> 版本: v1.1 | 日期: 2026-08-04 | 状态: 设计阶段（Harness Engineering 架构）

---

## 架构定位

**在 Multi-Agent + Harness 架构中的角色：** AI 数据中台作为独立 MCP Server，被动接收各业务 Agent 通过 Celery 异步写入的全量数据，负责数据清洗、存储、治理，并通过素材工厂模块自动化生成高质量训练样本，为模型微调提供数据燃料。

**核心原则：** 中台不主动拉取数据，不阻塞业务 Agent 主流程。所有数据写入通过 Celery 异步任务完成，数据质量由中台侧统一治理。

---

## 零、问题陈述

各业务 Agent 独立运行后，数据分散在各自的数据库中，面临以下问题：

1. **数据孤岛**：Ops/Dispatch/Warehouse Agent 各自拥有独立数据库，无法跨 Agent 关联分析
2. **数据质量参差**：各 Agent 的日志格式、字段命名不统一，无法直接用于训练
3. **无训练数据生产管线**：高质量问答对靠人工标注，效率低、成本高、不可持续
4. **数据资产无沉淀**：对话记录、工单操作、库房流水等数据用完即弃，无法形成数据飞轮
5. **无法支撑模型微调**：项目6 的模型微调缺少高质量领域数据集

**本方案要解决的核心问题：** 构建统一的数据中台，作为独立 MCP Server，采集各 Agent 的全量数据，通过素材工厂自动化生产训练样本，对外暴露数据服务和查询分析能力，为模型微调提供数据底座。

---

## 方案对比与选择

| 维度 | 方案 A：Agent 内嵌上报 | 方案 B：独立 MCP Server（选中） |
|------|----------------------|-------------------------------|
| **数据采集方式** | 各 Agent 直连中台 DB | Celery 异步任务 + 消息队列 |
| **耦合度** | 中台故障影响业务 Agent | 完全解耦，中台故障不影响业务 |
| **数据治理** | 各 Agent 自行处理 | 中台统一清洗、标准化 |
| **素材生产** | 无 | 中台素材工厂自动化生产 |
| **扩展性** | 受限于 Agent 架构 | 独立扩展存储和计算 |

**选择方案 B 的理由：** 数据中台的核心价值在于"不影响业务的前提下完成数据沉淀"。Celery 异步任务确保数据写入不阻塞业务 Agent 主流程；中台独立部署后可针对性扩展存储（MinIO）和计算（素材工厂）资源。

---

## 关键决策

| 决策点 | 结论 |
|--------|------|
| 架构模式 | 独立 MCP Server，被动接收数据，不主动拉取 |
| 数据采集 | Celery 异步任务，各 Agent 写入 Redis 队列，中台 Worker 消费 |
| 存储方案 | PostgreSQL（结构化元数据 + PGVector 向量索引）+ MinIO（非结构化原始数据） |
| 素材工厂 | 规则引擎 + LLM 自动生成问答对，人工抽检审核 |
| 数据出口 | MCP Tools 对外暴露，供 Orchestrator 和项目6 调用 |
| 数据保留 | 原始数据永久保留，清洗中间态保留 30 天 |
| 权限控制 | JWT role：admin/data_engineer |

---

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                   Orchestrator（协调器）                         │
│   路由 query_analytics / export_dataset 等意图 → Data Platform   │
└─────────────────────────────┬───────────────────────────────────┘
                              │ MCP Protocol
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Data Platform (MCP Server)                      │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────────┐  ┌───────────┐  │
│  │ MCP Tools        │  │ 素材工厂              │  │ 数据治理  │  │
│  │ - export_dataset │  │ - 问答对生成          │  │ - 清洗    │  │
│  │ - query_analytics│  │ - 考题素材生成        │  │ - 标准化  │  │
│  │ - material_gen   │  │ - 质量评分            │  │ - 去重    │  │
│  │ - data_import    │  │ - 人工抽检工作流      │  │ - 脱敏    │  │
│  └────────┬─────────┘  └───────────┬──────────┘  └─────┬─────┘  │
│           │                        │                    │        │
│           ▼                        ▼                    ▼        │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │              基础设施（Agent 私有）                          │   │
│  │  PostgreSQL  │  MinIO  │  PGVector │  Redis  │  Celery      │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │              数据采集层（Celery 异步消费）                    │   │
│  │                                                              │   │
│  │  Ops Agent ──→ Redis Queue ──→ Data Collector Worker        │   │
│  │  Dispatch Agent ──→ Redis Queue ──→ Data Collector Worker   │   │
│  │  Warehouse Agent ──→ Redis Queue ──→ Data Collector Worker  │   │
│  └────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、MCP Tool 定义

| Tool | 参数 | 返回 | 说明 |
|------|------|------|------|
| `export_dataset` | dataset_type (qa/classification/ticket), format (jsonl/csv), split (train/val/test), size | 数据集文件 URL | 导出训练/验证/测试集 |
| `query_analytics` | metric_name, time_range, group_by | 分析结果 JSON | 数据分析查询（工单量/解决率/满意度等） |
| `material_generate` | source (conversations/tickets), count, quality_threshold | 生成结果统计 | 素材工厂：批量生成问答对/考题素材 |
| `data_import` | source_agent (ops/dispatch/warehouse), data_type, payload | import result | 手动导入数据（管理用） |

**MCP Resources：**

| URI | 说明 |
|-----|------|
| `dataset://{dataset_id}` | 数据集详情（格式、大小、生成时间） |
| `analytics://{metric_name}` | 指标定义和最新值 |
| `material://{material_id}` | 素材详情（问答对、来源、质量评分） |

---

## 三、数据采集流程

### 3.1 数据写入链路

```
业务 Agent 产生数据
    │
    ├─ 主流程：正常处理业务逻辑
    │
    └─ 异步（Celery Task）：
        │
        ▼
    Redis Queue ("data_collect")
        │
        ▼
    Data Platform Celery Worker 消费
        │
        ├─ 1. 原始数据写入 MinIO（JSON Lines 格式）
        │
        ├─ 2. 元数据写入 PostgreSQL
        │
        ├─ 3. 清洗标准化
        │
        └─ 4. 触发素材工厂增量更新（可选）
```

### 3.2 各 Agent 上报数据

| 来源 Agent | 数据类型 | 上报频率 | 关键字段 |
|-----------|---------|---------|---------|
| Ops Agent | 对话消息 | 实时（每条消息） | session_id, role, content, intent, confidence, feedback |
| Ops Agent | 预填工单 | 工单生成时 | pre_ticket_id, extracted_fields, conversation_id |
| Dispatch Agent | 工单操作日志 | 状态变更时 | ticket_id, from_status, to_status, operator, timestamp |
| Dispatch Agent | 派单记录 | 派单时 | ticket_id, engineer_id, score_breakdown |
| Warehouse Agent | 库存流水 | 出入库时 | item_name, quantity, transaction_type, ticket_id |
| Warehouse Agent | 设备状态变更 | 状态变更时 | device_id, from_status, to_status, operator |

### 3.3 数据标准化

中台在消费数据时统一标准化：

```python
# 标准化事件格式
{
    "event_id": "uuid",
    "source_agent": "ops|dispatch|warehouse",
    "event_type": "message|ticket_log|inventory_tx|device_change",
    "timestamp": "ISO 8601",
    "trace_id": "从 Agent 传入",
    "user_id": "操作人",
    "payload": { /* 原始数据 */ },
    "metadata": {
        "version": "1.0",
        "schema": "data_platform_v1"
    }
}
```

---

## 四、素材工厂设计

### 4.1 核心流程

```
┌──────────────────────────────────────────────────────────────┐
│                      素材工厂 Pipeline                        │
│                                                              │
│  原始对话 ──→ 规则筛选 ──→ LLM 生成 ──→ 质量评分 ──→ 人工抽检 │
│              │                                                │
│              ├─ 过滤低质量对话（< 3 轮、纯寒暄）               │
│              ├─ 过滤已标注数据                                │
│              └─ 筛选高置信度回答                               │
│                                                              │
│  LLM 生成策略：                                               │
│  ├─ 问答对生成：从对话中提取"问题-答案"对                      │
│  ├─ 变体生成：同一问题生成 3-5 个不同表述                      │
│  ├─ 考题生成：从知识库文档生成选择题/判断题                     │
│  └─ 负样本生成：构造错误答案，用于训练模型识别边界              │
│                                                              │
│  质量评分（0-100）：                                          │
│  ├─ 答案准确性（与知识库原文对比）                             │
│  ├─ 语言流畅度                                                │
│  ├─ 信息完整性                                                │
│  └─ 人工审核通过率（反馈回评分模型）                           │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 素材存储结构

```sql
-- 素材表
CREATE TABLE materials (
    id UUID PRIMARY KEY,
    source_conversation_id VARCHAR,      -- 来源会话 ID
    source_knowledge_id VARCHAR,         -- 来源知识库文档 ID
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    material_type VARCHAR NOT NULL,      -- qa_pair / variant / exam_question / negative_sample
    quality_score DECIMAL(3,1),          -- 0-100
    human_reviewed BOOLEAN DEFAULT FALSE,
    human_approved BOOLEAN,
    review_comment TEXT,
    tags JSONB,                          -- ["打印机", "网络", "账号"]
    difficulty VARCHAR DEFAULT 'easy',   -- easy / medium / hard
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 4.3 生成触发策略

| 触发方式 | 说明 |
|---------|------|
| **定时触发** | Celery Beat 每天凌晨 2:00 处理前一天的增量数据 |
| **阈值触发** | 当日新增对话超过 500 条时自动触发 |
| **手动触发** | 数据工程师通过 MCP Tool `material_generate` 手动触发 |
| **CI/CD 触发** | 累计未处理素材超过 2000 条时自动触发（用于模型微调管线） |

---

## 五、数据模型设计

Data Platform 拥有独立的 `data_platform_db` 数据库：

### 核心表

| 表名 | 说明 | 关键字段 |
|------|------|---------|
| `raw_events` | 原始事件（所有 Agent 上报的数据） | event_id, source_agent, event_type, payload(JSONB), trace_id |
| `conversations_archive` | 归档对话（清洗后） | session_id, messages(JSONB), intent, satisfaction_score |
| `ticket_archive` | 归档工单 | ticket_id, lifecycle(JSONB), resolution_time, engineer_id |
| `inventory_snapshots` | 库存快照（每日） | snapshot_date, item_name, quantity, location |
| `materials` | 素材（问答对/考题） | question, answer, material_type, quality_score |
| `datasets` | 数据集版本 | dataset_id, type, format, split, record_count, file_url |
| `analytics_cache` | 分析缓存（预计算指标） | metric_name, value, time_bucket, updated_at |

### 与业务 Agent 的数据关联

Data Platform 只存储数据副本，不反向写回业务 Agent。数据关联通过 `trace_id` 和逻辑标识（如 `ticket_id`、`session_id`）实现跨 Agent 追溯。

---

## 六、项目目录结构

```
f:\mysite\data-platform\
├── docker-compose.yml              # 中台私有服务编排
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
│   │   │   └── export.py           # 数据集导出 API
│   │   ├── core/
│   │   │   ├── data_collector.py   # 数据采集（Celery Worker 消费）
│   │   │   ├── data_cleaner.py     # 数据清洗标准化
│   │   │   ├── data_deduplicator.py # 数据去重
│   │   │   ├── data_desensitizer.py # 敏感信息脱敏
│   │   │   ├── material_factory.py  # 素材工厂核心
│   │   │   ├── quality_scorer.py    # 素材质量评分
│   │   │   ├── analytics_engine.py  # 分析查询引擎
│   │   │   ├── dataset_builder.py   # 数据集构建
│   │   │   └── logger.py
│   │   ├── models/
│   │   │   ├── raw_event.py
│   │   │   ├── material.py
│   │   │   ├── dataset.py
│   │   │   └── analytics_cache.py
│   │   ├── schemas/
│   │   │   ├── event.py
│   │   │   ├── material.py
│   │   │   └── dataset.py
│   │   ├── tasks/
│   │   │   ├── celery_app.py
│   │   │   ├── collect_tasks.py    # 数据采集 Worker
│   │   │   ├── clean_tasks.py      # 数据清洗定时任务
│   │   │   ├── material_tasks.py   # 素材工厂定时任务
│   │   │   └── snapshot_tasks.py   # 快照定时任务
│   │   └── utils/
│   │       └── prompts.py          # 素材工厂 LLM Prompt
│   └── tests/
├── minio/
│   └── data/                       # MinIO 数据持久化
└── data/
    └── exports/                    # 数据集导出目录
```

---

## 七、Harness Engineering 集成

### 7.1 Consul 服务注册

Data Platform 作为 MCP Server，启动时向 Consul 注册，Orchestrator 可路由 `query_analytics` / `export_dataset` 等管理类请求：

```python
# mcp_server.py 启动流程
async def register_to_consul():
    await consul.register_service(
        name="data-platform",
        address="data-platform",
        port=8000,
        tags=["mcp", "version=1.0"],
        health_check={
            "http": "http://data-platform:8000/health",
            "interval": "10s",
            "timeout": "3s",
            "deregister_critical_after": "30s"
        }
    )
    # 注册 MCP Tools 到 Consul KV
    await consul.kv_put("mcp/tools/data-platform/export_dataset", {...})
    await consul.kv_put("mcp/tools/data-platform/query_analytics", {...})
    await consul.kv_put("mcp/tools/data-platform/material_generate", {...})
```

### 7.2 健康检查端点

`GET /health` 返回中台及依赖服务的健康状态：

```json
{
  "status": "healthy",
  "service": "data-platform",
  "version": "1.0.0",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "minio": "ok"
  },
  "metrics": {
    "raw_events_today": 1523,
    "materials_generated": 89,
    "data_collect_queue_size": 12
  },
  "timestamp": "2026-08-04T10:30:00Z"
}
```

### 7.3 traceId 全链路追踪

Data Platform 作为数据消费方，traceId 追踪分为两个场景：

**场景一：接收数据（被动）** — 从各 Agent 上报的事件中提取 traceId：
```python
# logger.py 结构化日志格式
{
  "timestamp": "2026-08-04T10:30:00.123Z",
  "level": "INFO",
  "traceId": "a1b2c3d4-...",        # 从 Agent 上报事件中提取
  "service": "data-platform",
  "step": "data_collect",
  "source_agent": "ops",
  "event_type": "message",
  "duration_ms": 12,
  "message": "Event ingested and stored to MinIO"
}
```

**场景二：MCP 请求处理（主动）** — 从 Orchestrator 的 MCP 调用 Header 提取 traceId：
```python
# 处理管理端查询请求时
{
  "timestamp": "2026-08-04T10:30:00.123Z",
  "level": "INFO",
  "traceId": "a1b2c3d4-...",        # 从 X-Trace-Id Header 提取
  "service": "data-platform",
  "tool": "query_analytics",
  "metric_name": "ticket_resolution_rate",
  "duration_ms": 234,
  "user_id": "admin_001",
  "message": "Analytics query completed"
}
```

### 7.4 降级策略

| 依赖故障 | 检测方式 | 降级行为 |
|---------|---------|---------|
| MinIO 不可用 | 上传/下载超时（10s）或连接拒绝 | 原始数据暂存 Redis 队列（最大缓存 10000 条），MinIO 恢复后批量写入；数据集导出功能不可用 |
| PostgreSQL 不可用 | 查询超时或连接池耗尽 | 数据采集暂停，Redis 队列缓存原始事件；管理端查询返回"系统繁忙"；素材工厂暂停 |
| Redis 不可用 | 连接超时或拒绝 | 数据采集队列失效，各 Agent 上报数据丢失（记录 CRITICAL 日志）；MCP 请求正常（不依赖 Redis） |
| Celery Worker 不可用 | 任务投递失败 | 数据采集、清洗、素材生成全部暂停；恢复后从 Redis 队列积压中批量消费 |
| vLLM 不可用（素材工厂） | 推理超时 | 素材工厂暂停 LLM 生成环节，规则筛选和去重继续；素材生成降级为纯规则模式 |

**降级恢复机制：** 所有依赖每 30s 自动重试连接。恢复后优先消费积压的 Redis 队列数据，再恢复正常采集节奏。降级期间 `/health` 端点返回 `status: "degraded"` 及具体故障项。

---

## 八、Docker 服务编排

```yaml
# data-platform/docker-compose.yml
services:
  data-platform:
    build: .
    ports: ["8400:8000"]
    environment:
      - DATABASE_URL=postgresql+asyncpg://dataplatform:pass@postgres:5432/data_platform_db
      - REDIS_URL=redis://redis:6379/0
      - MINIO_URL=http://minio:9000
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin
      - VLLM_URL=http://vllm:8000
      - CONSUL_URL=http://consul:8500
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s

  postgres:
    image: postgres:17
    environment:
      POSTGRES_DB: data_platform_db

  redis:
    image: redis:7-alpine

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - ./minio/data:/data

  celery_collector:
    build: .
    command: celery -A app.tasks.celery_app worker -Q data_collect --loglevel=info

  celery_cleaner:
    build: .
    command: celery -A app.tasks.celery_app worker -Q data_clean --loglevel=info

  celery_beat:
    build: .
    command: celery -A app.tasks.celery_app beat --loglevel=info
```

---

## 九、向下串联

Data Platform 为项目6（模型微调）提供数据燃料：

- **数据集导出**：项目6 通过 MCP Tool `export_dataset` 获取训练/验证/测试集
- **素材增量通知**：素材工厂新生成高质量素材后，通过 Redis Pub/Sub 通知项目6
- **反馈回流**：项目6 微调后的模型评估结果回写至 Data Platform，形成素材质量反馈闭环

**与 Orchestrator 的交互：** 数据中台不直接面向最终用户，仅通过 MCP 协议向 Orchestrator 暴露数据查询和分析能力，管理员可通过 Orchestrator 路由查询数据统计和导出数据集。