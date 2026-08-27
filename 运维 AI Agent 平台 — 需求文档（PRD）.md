# 运维 AI Agent 平台 — 需求文档（PRD）

> 版本: v2.1 | 日期: 2026-08-04 | 状态: 设计阶段（Multi-Agent + Harness Engineering 架构）

---

## 一、项目背景

运维团队日常面临大量重复性工作：员工报修打印机卡纸、网络不通、账号异常等，80% 为常见问题；人工响应平均 15 分钟，工程师被琐碎咨询占满，真正需要深度排查的故障反而被延误。

**目标：** 构建一套基于 Multi-Agent + Harness Engineering 架构的完整运维 AI 闭环，从"员工报修 → AI 客服解答 → 自动派单 → 库房备件 → 数据沉淀 → 模型进化"，让 AI 处理 60% 常见咨询，把工程师释放出来做高价值工作。

**架构核心：** 采用独立 Agent + Orchestrator 协调器模式，每个业务 Agent 作为 MCP Server 独立部署，通过标准化 MCP 协议通信。Harness 层统一提供服务发现、负载均衡、健康检查和全链路追踪。

**核心价值：**

| 角色 | 痛点 | AI 闭环后的改善 |
|------|------|----------------|
| 普通员工 | 报修响应慢，反复描述问题 | 秒级响应，AI 自动收集信息 |
| 运维工程师 | 被琐碎咨询淹没 | 只处理复杂故障，AI 预填工单 |
| 库管员 | 手工记录出入库，盘点耗时 | 自然语言操作，OCR 自动录入 |
| 管理者 | 绩效评估靠印象，无数据支撑 | 数据驱动决策，全链路可追溯 |

---

## 二、目标用户

| 角色 | 描述 |
|------|------|
| **普通员工** | 提交报修、咨询运维问题，是 Ops Agent 的主要使用者 |
| **运维工程师** | 接收 AI 派单、处理工单、汇报进度，使用工程师工作台 |
| **库管员** | 管理设备与备件出入库，响应备件申请，使用 Warehouse Agent |
| **管理员/主管** | 查看绩效、管理工单、查看统计，使用管理后台 |

---

## 三、成功指标（KPIs）

| 指标 | 目标值 | 衡量方式 |
|------|--------|----------|
| AI 自动解决率 | ≥ 60% | 无需转人工即关闭的会话占比 |
| 首次响应时间 | < 3 秒 | 从用户发送到收到首 token 的延迟 |
| 用户满意度 | ≥ 4.0/5.0 | 聊天界面反馈按钮统计 |
| 工单预填准确率 | ≥ 85% | 管理员审核通过率 |
| 知识库覆盖率 | ≥ 80% | 拒答率 < 20% |
| 系统可用性 | ≥ 99.5% | 月度正常运行时间 |
| Agent 间通信延迟 | < 50ms | Orchestrator → Agent 调用 P99 延迟 |

---

## 四、架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                    前端 (Vue 3 SPA) — 统一入口                   │
│       员工端 / 管理端 / 工程师端 / 库管员端                       │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTP/WebSocket (JWT)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Orchestrator（协调器）— 统一入口                  │
│  全局意图路由 │ 会话管理 │ 服务发现 │ 跨 Agent 编排 │ 降级兜底   │
└───┬──────────────┬──────────────┬──────────────┬────────────────┘
    │ MCP Protocol │              │              │
    ▼              ▼              ▼              ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
│Ops Agent │ │Dispatch  │ │Warehouse │ │Data Platform │
│(MCP)     │ │Agent(MCP)│ │Agent(MCP)│ │(MCP)         │
│客服/咨询  │ │派单/工单  │ │库房/设备  │ │数据采集/治理  │
└──────────┘ └──────────┘ └──────────┘ └──────────────┘
    │              │              │              │
    └──────────────┴──────────────┴──────────────┘
                       │
┌─────────────────────────────────────────────────────────────────┐
│              Harness 基础设施层                                  │
│  Consul(服务发现) │ Redis(会话/Pub/Sub) │ Nginx(负载均衡)       │
│  可观测性(日志/追踪/指标) │ Docker Compose(容器编排)             │
│  Prometheus + Grafana(监控) │ LangGraph(Orchestrator 编排引擎)  │
└─────────────────────────────────────────────────────────────────┘
```

> 详细架构设计见 [docs/architecture/multi-agent-design.md](docs/architecture/multi-agent-design.md)

---

## 五、项目优先级与范围边界

| 项目 | 优先级 | 说明 |
|------|--------|------|
| 项目1：Ops Agent（智能运维客服） | **P0** | 入口项目，RAG 问答 + 意图识别 + 预填工单 |
| 项目2：Dispatch Agent（自动派单） | **P0** | 核心业务闭环，工单生命周期 + 智能派单 + SLA 监控 |
| 项目3：Warehouse Agent（库房管理） | **P1** | 备件管理闭环，设备生命周期 + OCR 铭牌 + 库存告警 |
| 项目4：AI 数据中台 | **P1** | 数据底座，全量采集 + 素材工厂 + 数据服务 API |
| 项目5：Orchestrator + Harness 集群 | **P2** | 生产级运维，MCP 协议标准化 + 服务发现 + 负载均衡 |
| 项目6：模型微调与反馈闭环 | **P2** | 持续优化，数据飞轮驱动模型能力提升 |

### 项目1 范围边界（Ops Agent）

| 本期做 | 本期不做 |
|--------|----------|
| 员工端 Web 聊天界面 | 管理后台（由 Dispatch Agent 提供） |
| RAG 知识库问答 | 语音/视频通话 |
| 意图分类 + 槽位填充 | 多语言支持 |
| 预填工单生成（通过 MCP 传给 Dispatch） | 正式工单生命周期管理（Dispatch Agent） |
| JWT 认证 + Rate Limit | SSO/LDAP 集成 |
| 单租户部署 | 多租户 SaaS |

### 项目2 范围边界（Dispatch Agent）

| 本期做 | 本期不做 |
|--------|----------|
| 正式工单 CRUD + 生命周期管理 | 库房管理（Warehouse Agent） |
| 智能派单引擎（加权评分） | 数据中台（Data Platform） |
| SLA 监控 + 催办 | 绩效考核（后续迭代） |
| 管理员自然语言操作 | 模型微调 |
| 工程师工作台 | |

### 项目3 范围边界（Warehouse Agent）

| 本期做 | 本期不做 |
|--------|----------|
| 设备生命周期管理（7 状态） | 采购管理 |
| 自然语言出入库 | 财务对账 |
| OCR 铭牌识别 | 供应商管理 |
| 备件申请联动（通过 MCP 与 Dispatch 协作） | |
| 库存监控与告警 | |

---

## 六、非功能需求

| 维度 | 要求 |
|------|------|
| **性能** | 单次 RAG 请求延迟 < 3s，TTFT < 2s，Agent 间 MCP 调用 P99 < 50ms |
| **可用性** | 服务可用性 ≥ 99.5%，单 Agent 故障不影响其他服务 |
| **安全** | 全链路 JWT 认证，MCP 调用携带 token，敏感信息脱敏 |
| **可扩展** | 每个 Agent 独立水平扩展，Orchestrator 无状态可任意扩容 |
| **兼容性** | Windows 开发环境，Docker 部署，Chrome/Firefox 浏览器 |
| **数据隐私** | 模型和数据本地部署，用户数据不出内网 |
| **可观测性** | 全链路 traceId 追踪，结构化日志，健康检查端点 |

---

## 七、验收标准

### 项目1 验收标准（Ops Agent）

1. 员工可通过 Web 界面登录并开始实时聊天
2. 输入运维问题后，AI 能在 3 秒内给出有知识库来源的回答
3. 报修场景下，AI 能多轮追问补全设备/位置等关键信息
4. 补全信息后通过 MCP 协议自动生成预填工单并传递给 Dispatch Agent
5. 无法解答的问题标记低置信并提示转人工
6. 聊天记录持久化，刷新页面后可恢复历史会话
7. 用户可对每条 AI 回复点击"有帮助/无帮助"

### 项目2 验收标准（Dispatch Agent）

1. 管理员可从预填工单列表审核确认并创建正式工单
2. 派单引擎自动选择最优工程师，加权评分可配置
3. 工单状态机完整流转（created→assigned→in_progress→resolved→closed）
4. 超时工单自动催办，超过 2×SLA 自动升级
5. 管理员可通过自然语言操作工单（创建/指派/改派/取消）
6. 工程师工作台实时显示待办工单和通知

### 项目3 验收标准（Warehouse Agent）

1. 库管员可通过自然语言完成出入库操作
2. OCR 铭牌识别准确率 ≥ 90%，自动提取序列号/型号
3. 备件申请联动：Dispatch Agent 通过 MCP 调用 Warehouse Agent，形成闭环
4. 设备状态机完整流转（in_stock→allocated→in_use→damaged→in_repair→repaired→scrapped）
5. 低库存自动告警，呆滞设备定期提醒

### 跨 Agent 协作验收标准

1. Orchestrator 正确路由用户请求到对应 Agent
2. 跨 Agent 编排（如备件申请）调用链完整，traceId 一致
3. 单个 Agent 故障时，Orchestrator 返回友好降级提示
4. 所有服务通过顶层 `docker-compose.yml` 一键启动

### 项目4 验收标准（AI 数据中台）

1. 各 Agent 的对话、工单、库存数据通过 Celery 异步写入中台，不阻塞业务主流程
2. 素材工厂每日自动生成问答对，质量评分 ≥ 80 的素材占比 ≥ 60%
3. 管理员可导出指定类型、格式和切分比例的训练数据集
4. 数据查询分析返回常用指标（工单量、解决率、满意度、响应时间）
5. 数据标准化事件格式统一，traceId 可追溯原始请求链路

### 项目5 验收标准（Orchestrator + Harness 集群）

1. Agent 启动后自动注册到 Consul，Orchestrator 动态发现并路由
2. 加权轮询负载均衡生效，多实例部署时请求均匀分发
3. Agent 实例故障后自动从实例池移除，恢复后自动加入
4. 全链路 traceId 从 Orchestrator 生成并下传至各 Agent，日志中可串联同一请求
5. Agent 全部不可用或超时后，返回友好降级提示，不丢消息
6. 工具集市动态更新，新增 Agent 或 Tool 无需重启 Orchestrator

### 项目6 验收标准（模型微调与反馈闭环）

1. 从数据中台导出 ≥ 2000 条高质量问答对，完成 QLoRA 微调
2. 微调后模型在人工评估中准确率 ≥ 85%，流畅度 ≥ 90%
3. MLflow 记录完整实验参数和评估指标，支持版本对比和回滚
4. 微调模型通过 Ollama 加载，Orchestrator 配置 A/B 测试流量分配
5. A/B 测试候选模型满意度 ≥ 生产模型，完成灰度全量切换
6. 数据飞轮闭环：素材工厂新增 → 触发训练 → 评估 → 部署，单次循环 ≤ 4 周

---

## 八、项目详细需求

### 项目1：Ops Agent（智能运维客服）[P0]

**项目目标：** 构建基于 RAG 的运维智能客服，作为 MCP Server 对外暴露知识检索、意图分类、预填工单等能力。通过 Orchestrator 接收前端请求，无法解答时自动生成预填工单并传递给 Dispatch Agent。

**技术栈：** Python, FastAPI, MCP SDK, SimpleMCP（MCP 协议适配层）, LangChain, PGVector, Redis, Celery, PostgreSQL, SiliconFlow API（生产环境千问系列）/ Ollama（本地开发）

**MCP Tools：**

| Tool | 说明 |
|------|------|
| `rag_search` | 知识库检索问答（流式输出） |
| `intent_classify` | 意图分类（repair/consult/check_progress） |
| `prefill_ticket` | 生成预填工单（传递至 Dispatch Agent） |
| `chat_reply` | 多轮对话回复（含槽位填充） |

**MCP Resources：** `knowledge://{doc_id}`, `conversation://{session_id}`

**向下串联：** 预填工单通过 Orchestrator 路由至 Dispatch Agent，触发正式工单创建流程。

---

### 项目2：Dispatch Agent（自动派单）[P0]

**项目目标：** 实现工单全生命周期管理、智能派单、SLA 监控。作为独立 MCP Server，通过 Orchestrator 接收管理员/工程师请求，需要备件时通过 MCP 调用 Warehouse Agent。

**技术栈：** Python, FastAPI, MCP SDK, LangGraph, Redis, Celery, PostgreSQL

**MCP Tools：**

| Tool | 说明 |
|------|------|
| `create_ticket` | 创建正式工单 |
| `assign_ticket` | 智能派单/手动指派 |
| `query_tickets` | 查询工单列表（分页+筛选） |
| `get_engineers` | 获取工程师状态和负载 |
| `urge_ticket` | 催单 |
| `resolve_ticket` | 解决/关闭工单 |
| `reassign_ticket` | 改派工单 |
| `cancel_ticket` | 取消工单 |
| `create_engineer` | 创建工程师档案 |
| `reopen_ticket` | 重开已关闭工单 |
| `change_priority` | 变更工单优先级 |
| `accept_ticket` | 工程师接单 |
| `reject_ticket` | 工程师拒单 |
| `get_stats` | 工单统计（总量/状态分布/紧急度/超时） |

**MCP Resources：** `ticket://{ticket_id}`, `engineer://{engineer_id}`, `sla://{ticket_id}`

**向下串联：** 工单处理中需要备件时，通过 Orchestrator 编排调用 Warehouse Agent 的备件申请接口。

---

### 项目3：Warehouse Agent（库房管理）[P1]

**项目目标：** 实现设备与耗材的智能库房管理，作为独立 MCP Server，与 Dispatch Agent 联动完成备件申请闭环，支持自然语言操作和 OCR 铭牌识别。

**技术栈：** Python, FastAPI, MCP SDK, PaddleOCR, Redis, Celery, PostgreSQL

**MCP Tools：**

| Tool | 说明 |
|------|------|
| `stock_in` / `stock_out` | 出入库操作 |
| `device_query` | 设备查询（分页+筛选） |
| `ocr_recognize` | OCR 铭牌识别 |
| `spare_request` | 备件申请处理（接收 Dispatch Agent 调用） |
| `inventory_check` | 库存查询 + 低库存告警 |
| `device_status_change` | 设备状态变更（触发状态机） |
| `transfer_device` | 设备调拨 |
| `create_device` | 创建设备记录 |
| `create_inventory` | 创建库存物品 |
| `get_locations` / `create_location` / `update_location` / `delete_location` | 库房位置 CRUD |
| `warehouse_overview` | 库房概览统计 |
| `device_logs` | 设备操作日志 |
| `inventory_transactions` | 库存交易记录 |
| `spare_requests` | 备件申请列表 |
| `approve_spare` / `reject_spare` / `fulfill_spare` | 备件申请审批流程 |

**MCP Resources：** `device://{device_id}`, `inventory://{item_id}`, `location://{location_id}`

**向下串联：** 所有库房操作日志和设备变更记录统一写入项目4 AI 数据中台。

---

### 项目4：AI 数据中台 [P1]

**项目目标：** 统一采集、治理、存储来自各 Agent 的全量数据，构建数据底座。内部设素材工厂模块，完成高质量训练样本的自动化生产，支撑模型微调。作为独立 MCP Server，被动接收数据，不阻塞业务 Agent 主流程。

**技术栈：** Python, FastAPI, MCP SDK, PostgreSQL, MinIO, PGVector, Celery, Redis, Pandas

**MCP Tools：**

| Tool | 说明 |
|------|------|
| `export_dataset` | 导出训练/验证/测试集（支持 jsonl/csv 格式，可按 train/val/test 切分） |
| `query_analytics` | 数据分析查询（工单量/解决率/满意度/响应时间等指标） |
| `material_generate` | 素材工厂：从对话中自动生成问答对/考题/变体/负样本 |
| `data_import` | 手动导入数据（管理用） |

**MCP Resources：** `dataset://{dataset_id}`, `analytics://{metric_name}`, `material://{material_id}`

**数据采集方式：** 各 Agent 通过 Celery 异步任务将操作日志、对话记录写入 Redis 队列，中台 Celery Worker 消费后写入 MinIO（原始数据）和 PostgreSQL（结构化元数据）。数据标准化为统一事件格式，携带 traceId 实现全链路追溯。

**素材工厂：** 规则筛选 → LLM 生成 → 质量评分 → 人工抽检。支持定时触发（每日凌晨）、阈值触发（新增对话 > 500 条）、手动触发和 CI/CD 触发。质量评分 ≥ 80 分的素材进入训练候选池。

**向下串联：** 素材工厂输出的高质量训练样本供项目6模型微调使用；所有新产生的数据同时回流至中台，形成数据飞轮。

> 详细技术方案见 [docs/project4-data-platform.md](docs/project4-data-platform.md)

---

### 项目5：Orchestrator + Harness 集群 [P2]

**项目目标：** 实现 Orchestrator 协调器统一入口、全局意图路由、跨 Agent 编排，以及 Harness 层的服务发现（Consul）、负载均衡（Nginx + 加权轮询）、健康检查（多层检查矩阵）和全链路追踪（traceId），构建可弹性伸缩、故障自愈的生产级 Agent 集群。

**技术栈：** Python, FastAPI, MCP SDK, Consul, Redis, Nginx, LangGraph, Docker Compose, Prometheus, Grafana

**Orchestrator 核心功能：**

- **全局意图路由**：规则匹配（毫秒级）+ LLM 兜底，覆盖 consult / repair / check_progress / ticket_manage / warehouse_op / spare_request / query_stats / data_query 八种意图
- **跨 Agent 编排引擎**：支持顺序和并行步骤，依赖注入上一步结果，以备件申请联动为典型场景
- **会话管理**：Redis 集中存储会话上下文，Orchestrator 无状态可水平扩展，任意实例无缝接管
- **工具集市**：Consul KV 存储所有 MCP Tool 元数据（参数、鉴权、限流），动态注册和热更新

**Harness 层核心功能：**

- **服务注册与发现**：Agent 启动时向 Consul 注册（HTTP Health Check，10s 间隔），Orchestrator 动态获取节点列表，维护 InstancePool 实例池
- **负载均衡**：加权轮询（权重 = 1/(当前活跃请求数 + 1)）、最少连接、一致性哈希三种策略
- **健康检查矩阵**：Agent 存活（/health）、MCP 可用（list_tools）、数据库连接、Redis 连接四层检查，失败自动剔除
- **全链路追踪**：Orchestrator 生成 traceId → MCP 调用 Header 传递 → 各 Agent 日志携带，结构化 JSON 日志统一格式
- **降级策略**：Agent 全部不可用 → 友好提示；Agent 部分不可用 → 路由健康实例；Agent 超时 → 重试 3 次（指数退避）；LLM 超时 → 规则引擎兜底；Consul 不可用 → 本地缓存兜底
- **安全设计**：Nginx 验证 JWT → Orchestrator 解析 role → 传递至 Agent，工具级别 role 鉴权，Nginx 100 req/s 全局限流

**架构要点：**

- Orchestrator 无状态设计，可水平扩展；开发环境 2 副本，生产环境按需扩容
- 所有 Agent 的 MCP 工具通过 Consul KV 动态注册，实现工具集市即时更新
- 集群通过顶层 Docker Compose 一键部署，预留 K8s Helm Chart 迁移路径（Consul → K8s Service，Nginx → Ingress）

**向下串联：** Harness 集群为模型微调（项目6）提供 A/B 测试流量路由和灰度发布能力，微调后模型通过 Orchestrator 按比例分配流量，指标对比后全量切换。

> 详细技术方案见 [docs/project5-orchestrator-harness.md](docs/project5-orchestrator-harness.md)

---

### 项目6：模型微调与反馈闭环 [P2]

**项目目标：** 利用 AI 数据中台积累的领域高质量问答对和工单数据，通过 QLoRA 参数高效微调持续提升 Ops Agent 的 LLM 在运维领域的表现，评估后通过 Orchestrator 的 A/B 测试能力灰度替换原模型，完成"运行→采集→训练→部署"的数据飞轮。

**技术栈：** Python, PyTorch, Transformers, PEFT (QLoRA), bitsandbytes, MLflow, Ollama, PostgreSQL

**微调方案：**

- **QLoRA 参数高效微调**：4-bit 量化基座模型 + LoRA adapter（r=16, alpha=32），目标模块 q_proj/v_proj/k_proj/o_proj，单卡 RTX 3090/4090 即可训练
- **基座模型**：Qwen2.5-7B-Instruct（架构模型无关，可替换），adapter 仅 ~100MB，便于版本管理和回滚
- **训练数据**：从数据中台素材工厂导出，指令微调格式（instruction/input/output），支持数据增强（同义替换、难度分层、负样本）
- **实验管理**：MLflow 记录超参数、数据集版本、评估指标（perplexity/ROUGE/BLEU/BERTScore），支持实验对比和回滚

**评估与部署：**

- **自动评估**：perplexity + ROUGE-1/ROUGE-L + BLEU-4 + BERTScore
- **人工评估**：抽检 100 条，评估准确率/完整性/流畅度/可操作性/安全性
- **模型部署**：导出 LoRA adapter → 编写 Ollama Modelfile → ollama create → Orchestrator 配置 A/B 测试
- **A/B 测试**：候选模型 5% 金丝雀 → 10% 小流量 → 50% 半流量 → 100% 全量，每阶段观察 1-3 天，满意度显著提升后全量切换
- **灰度发布**：Orchestrator 按流量比例路由到不同版本的 Ops Agent 实例，用户会话内一致性哈希保持体验一致

**数据飞轮：**

```
运行(Agent) → 采集(中台) → 素材工厂(生成问答对) → 质量筛选(score≥80) → QLoRA微调 → 评估 → A/B测试 → 部署(Orchestrator) → 运行...
```

飞轮转速：素材工厂每日凌晨处理，累计新增素材 ≥ 2000 条触发训练，约 2-4 周完成一次完整循环。

**架构要点：**

- 模型服务与 Agent 服务解耦，通过 Ollama API 调用，更换模型无需修改 Agent 业务代码
- 微调流水线可集成到 CI/CD，当素材工厂新增样本达到阈值时自动触发训练
- 基座模型共享，多版本 LoRA adapter 同时加载，天然支持 A/B 测试和秒级回滚

> 详细技术方案见 [docs/project6-model-finetuning.md](docs/project6-model-finetuning.md)