# 运维 AI Agent 平台

基于 **Multi-Agent + MCP 协议 + Harness Engineering** 架构的智能运维闭环平台。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![Vue](https://img.shields.io/badge/Vue-3.4-brightgreen)](https://vuejs.org)

## 架构概览

```
用户 → Orchestrator（协调器） → Ops Agent（智能客服 MCP Server）
                              → Dispatch Agent（自动派单 MCP Server）
                              → Warehouse Agent（库房管理 MCP Server）
                              → Data Platform（AI 数据中台 MCP Server）
```

### 核心特性

- **Multi-Agent 协作**：4 个独立 Agent 通过 MCP 协议标准化通信，Orchestrator 统一路由
- **Harness 工程化**：Consul 服务发现 + Nginx 负载均衡 + 全链路追踪 + 健康检查
- **RAG 知识库**：PGVector 向量数据库 + BM25 混合检索 + 重排序 + Query Rewrite
- **意图路由**：LangGraph 状态图编排，规则匹配 + LLM 兜底，支持多轮对话
- **流式输出**：SSE 实时推送，WebSocket 前端渲染
- **降级容错**：6 层降级策略（LLM → 规则 → 关键词 → 预设回复 → 转人工），服务故障自动恢复
- **生产级基础设施**：PostgreSQL 17 + Redis 7 + Celery 异步任务 + Prometheus + Grafana 监控
- **Docker 容器化**：26 个容器一键部署，docker-compose 编排

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + asyncpg + Celery |
| Agent 协议 | MCP (Model Context Protocol) |
| 工作流编排 | LangGraph |
| 前端 | Vue 3 + Element Plus + TypeScript + Pinia |
| 数据库 | PostgreSQL 17 (PGVector) + Redis 7 |
| LLM | SiliconFlow API (Qwen3-32B) / vLLM (本地部署) |
| 容器化 | Docker Compose (26 容器) |
| 服务发现 | Consul |
| 负载均衡 | Nginx |
| 监控 | Prometheus + Grafana |
| 对象存储 | MinIO |
| 实验管理 | MLflow |

## 项目结构

| 目录 | 说明 | 端口 |
|------|------|------|
| `orchestrator/` | 协调器 - 统一入口，意图路由，JWT 认证 | 8000 |
| `ops-agent/` | Ops Agent - 智能客服，RAG 检索，工单生成 | 8100 |
| `dispatch-agent/` | Dispatch Agent - 自动派单，工程师分配 | 8200 |
| `warehouse-agent/` | Warehouse Agent - 库房管理，OCR 识别 | 8300 |
| `data-platform/` | Data Platform - 数据中台，素材工厂，数据采集 | 8400 |
| `frontend/` | 统一前端 - 聊天、管理后台、工程师工作台 | 3000 |
| `model-finetuning/` | 模型微调框架 - QLoRA 训练 Pipeline | — |
| `prometheus/` | 监控配置 | 9090 |
| `grafana/` | 可视化面板 | 3001 |
| `docs/` | 架构设计文档、各模块详细文档 | — |

## 快速开始

### 前置条件

- Docker & Docker Compose v2
- NVIDIA GPU + nvidia-container-toolkit（可选，vLLM 本地推理需要）
- SiliconFlow API Key（云推理，[注册获取](https://siliconflow.cn)）

### 一键部署

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 SILICONFLOW_API_KEY

# 2. 启动所有服务
docker compose up -d

# 3. 等待服务就绪后访问
# 前端:    http://localhost:3000
# API 文档: http://localhost:8000/docs
# Grafana:  http://localhost:3001  (admin / grafana-admin)
# Consul:   http://localhost:8500
```

### 测试账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | Admin@2024Demo |
| 工程师 | engineer1 | Engineer@123 |
| 普通用户 | testuser | User@123 |

### 本地开发

```bash
# 只启动基础设施
docker compose up -d orchestrator-db redis consul

# 启动后端（以 orchestrator 为例）
cd orchestrator/backend
cp .env.example .env
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 启动前端
cd frontend
npm install
npm run dev
```

## 系统设计亮点

### 1. 意图路由与降级

```
用户消息 → 关键词匹配 → 置信度 ≥ 0.7 → 路由到 Agent
                      ↓ 置信度 < 0.7
                   LLM 意图分类 → 路由到 Agent
                                ↓ LLM 不可用
                            规则兜底回复
```

### 2. RAG 检索增强

```
用户问题 → Query Rewrite → 向量检索(PGVector) + BM25 关键词 → 重排序 → LLM 生成
```

### 3. 降级容错策略

| 故障 | 降级行为 |
|------|---------|
| LLM 不可用 | 关键词匹配 → 预设回复 → 转人工 |
| PGVector 不可用 | 降级为纯 BM25 检索 |
| Redis 不可用 | 会话降级为内存存储 |
| PostgreSQL 不可用 | 消息暂存内存队列，恢复后批量写入 |
| Celery 不可用 | 异步任务降级为同步执行 |

### 4. 全链路追踪

每个请求携带 `trace_id`，贯穿 Orchestrator → Agent → LLM 调用 → 数据库操作，日志可追踪。

## License

MIT

## 文档

详细设计文档见 [docs/](docs/) 目录：
- [项目1：Ops Agent](docs/project1-ops-agent.md)
- [项目2：Dispatch Agent](docs/project2-dispatch-agent.md)
- [项目3：Warehouse Agent](docs/project3-warehouse-agent.md)
- [项目4：Data Platform](docs/project4-data-platform.md)
- [项目5：Orchestrator](docs/project5-orchestrator-harness.md)
- [项目6：模型微调](docs/project6-model-finetuning.md)
- [架构设计](docs/architecture/multi-agent-design.md)