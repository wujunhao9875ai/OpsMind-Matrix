# 项目6：模型微调与反馈闭环 — 技术方案

> 版本: v1.1 | 日期: 2026-08-04 | 状态: 设计阶段（Harness Engineering 架构）

---

## 架构定位

**在 Multi-Agent + Harness 架构中的角色：** 模型微调是数据飞轮的"最后一公里"。利用 AI 数据中台积累的领域高质量数据，对 Ops Agent 使用的 LLM 进行参数高效微调，评估后通过 Orchestrator 的 A/B 测试能力灰度替换原模型，完成"运行→采集→训练→部署"的完整闭环。

**核心原则：** 模型服务与 Agent 服务解耦。Agent 通过 LLM 适配器调用模型，更换模型无需修改业务代码。微调流水线可集成到 CI/CD，当素材工厂新增样本达到阈值时自动触发训练。

---

## 零、问题陈述

Ops Agent 当前使用通用大模型（如 Qwen），在运维领域存在以下问题：

1. **领域知识不足**：通用模型对打印机型号、网络拓扑、运维流程等专业知识理解有限
2. **回答风格不匹配**：通用模型回答偏学术，运维场景需要简洁、可操作的指导
3. **意图分类不准**：通用模型对"报修"和"咨询"的边界判断有偏差
4. **无法持续进化**：每次对话产生的知识无法反哺模型，能力停滞
5. **无数据飞轮**：AI 数据中台积累的高质量数据未被充分利用

**本方案要解决的核心问题：** 利用数据中台积累的领域数据，通过 QLoRA 参数高效微调，持续提升 Ops Agent 的 LLM 在运维领域的表现，构建"运行→采集→训练→部署"的数据飞轮。

---

## 方案对比与选择

| 维度 | 方案 A：全量微调 | 方案 B：QLoRA 参数高效微调（选中） |
|------|----------------|----------------------------------|
| **GPU 需求** | 多卡 A100（80GB）| 单卡 RTX 3090/4090（24GB） |
| **训练时间** | 数小时～数天 | 30 分钟～2 小时（取决于数据量） |
| **存储成本** | 每版本 ~14GB | 每版本 ~100MB（LoRA 权重） |
| **灾难恢复** | 需备份完整模型 | 只需保存 LoRA adapter |
| **A/B 测试** | 部署两套完整模型 | 基座模型共享 + 不同 adapter |
| **回滚速度** | 分钟级（加载模型） | 秒级（切换 adapter） |

**选择方案 B 的理由：** QLoRA 在消费级 GPU 上即可完成微调，LoRA adapter 体积小（~100MB），便于版本管理和快速切换。基座模型共享，多版本 adapter 同时加载，天然支持 A/B 测试。回滚成本极低，切换 adapter 即可。

---

## 关键决策

| 决策点 | 结论 |
|--------|------|
| 微调方法 | QLoRA（4-bit 量化 + LoRA），目标模块：q_proj, v_proj, k_proj, o_proj |
| 基座模型 | Qwen2.5-7B-Instruct（或 Qwen3 系列，架构模型无关） |
| 训练框架 | Transformers + PEFT + bitsandbytes |
| 实验管理 | MLflow 记录超参数、数据集版本、评估指标 |
| 评估体系 | 自动评估（perplexity + ROUGE/BLEU）+ 人工评估（准确率、流畅度） |
| 模型服务 | vLLM 加载，与 Agent 通过 OpenAI 兼容 API 解耦 |
| A/B 测试 | Orchestrator 按流量比例路由到不同版本 Ops Agent 实例 |
| 触发策略 | 素材工厂新增样本 ≥ 2000 条时自动触发训练（可手动触发） |

---

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     AI 数据中台 (Data Platform)                   │
│                                                                  │
│  export_dataset ──→ 训练集 (train.jsonl)                        │
│                   ├─ 验证集 (val.jsonl)                          │
│                   └─ 测试集 (test.jsonl)                         │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   模型微调 Pipeline                               │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ 数据预处理│→│ QLoRA   │→│ 评估     │→│ 模型注册        │  │
│  │          │  │ 微调     │  │          │  │ (MLflow)        │  │
│  │ - 格式转换│  │ - LoRA   │  │ - 自动   │  │ - 版本管理      │  │
│  │ - 分词    │  │ - 4-bit  │  │ - 人工   │  │ - 指标对比      │  │
│  │ - 数据增强│  │ - 多轮   │  │ - A/B测试│  │ - 回滚支持      │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              模型服务层（与 Agent 解耦）                    │   │
│  │                                                              │   │
│  │  vLLM 模型仓库:                                            │   │
│  │  ├─ qwen2.5:7b-instruct        (基座模型)                    │   │
│  │  ├─ ops-agent:v1.0             (原始模型)                    │   │
│  │  ├─ ops-agent:v1.1-lora        (微调 v1)                     │   │
│  │  └─ ops-agent:v2.0-lora        (微调 v2, 当前生产)           │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Orchestrator（协调器）                         │
│                                                                  │
│  A/B 测试路由:                                                   │
│  ├─ 90% 流量 → ops-agent:v2.0-lora (生产模型)                   │
│  └─ 10% 流量 → ops-agent:v2.1-lora (候选模型)                   │
│                                                                  │
│  指标对比:                                                       │
│  ├─ 用户满意度 (feedback 评分)                                   │
│  ├─ 回答准确率 (人工抽检)                                        │
│  ├─ 意图分类准确率                                                │
│  └─ 转人工比例                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、微调 Pipeline 详细设计

### 2.1 数据准备

```
从 Data Platform 导出数据集:
  export_dataset(type="qa", format="jsonl", split="train", size=2000)
  export_dataset(type="qa", format="jsonl", split="val", size=500)
  export_dataset(type="qa", format="jsonl", split="test", size=500)

数据格式转换（→ 指令微调格式）:
{
  "instruction": "你是运维智能客服助手，请根据知识库内容回答用户问题。",
  "input": "打印机显示错误代码 E001 怎么办？",
  "output": "E001 错误代码表示打印机卡纸。请按以下步骤操作：\n1. 打开打印机前盖\n2. 轻轻取出卡住的纸张\n3. 关闭前盖，打印机将自动恢复",
  "source": "material_id: xxx, quality_score: 92"
}

数据增强（可选，防止过拟合）:
  - 同义替换：将"怎么办"替换为"如何处理"、"如何解决"
  - 难度分层：easy (70%) / medium (20%) / hard (10%)
  - 负样本：在训练集中混入 5% 与"问题不匹配的错误答案"对
```

### 2.2 QLoRA 微调配置

```python
# 微调脚本核心配置
training_config = {
    "base_model": "Qwen/Qwen2.5-7B-Instruct",
    "lora_config": {
        "r": 16,                    # LoRA rank
        "lora_alpha": 32,           # LoRA alpha
        "lora_dropout": 0.1,
        "target_modules": [
            "q_proj", "v_proj",     # Attention 层
            "k_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj"  # FFN 层（可选）
        ],
        "bias": "none",
        "task_type": "CAUSAL_LM"
    },
    "quantization": {
        "load_in_4bit": True,
        "bnb_4bit_compute_dtype": "float16",
        "bnb_4bit_quant_type": "nf4",
        "bnb_4bit_use_double_quant": True
    },
    "training": {
        "num_train_epochs": 3,
        "per_device_train_batch_size": 4,
        "gradient_accumulation_steps": 4,
        "learning_rate": 2e-4,
        "warmup_ratio": 0.03,
        "lr_scheduler_type": "cosine",
        "logging_steps": 10,
        "save_steps": 100,
        "eval_steps": 100,
        "max_seq_length": 2048,
        "packing": False
    }
}
```

### 2.3 评估体系

```python
# 自动评估指标
auto_metrics = {
    "perplexity": "越低越好，衡量模型对测试集的拟合程度",
    "rouge-1": "衡量生成文本与参考答案的 n-gram 重叠",
    "rouge-l": "衡量最长公共子序列",
    "bleu-4": "衡量 4-gram 精确匹配",
    "bert_score": "基于语义相似度的评估（更接近人工判断）",
}

# 人工评估维度（抽检 100 条）
human_eval = {
    "准确率": "回答是否基于知识库，无幻觉",
    "完整性": "是否覆盖了问题的所有关键点",
    "流畅度": "语言是否通顺、专业",
    "可操作性": "是否给出了可执行的具体步骤",
    "安全性": "是否避免了危险操作建议",
}
```

### 2.4 MLflow 实验管理

```python
# MLflow 记录内容
mlflow.log_params({
    "base_model": "Qwen2.5-7B-Instruct",
    "lora_r": 16,
    "lora_alpha": 32,
    "learning_rate": 2e-4,
    "num_epochs": 3,
    "train_samples": 2000,
    "dataset_version": "v20260804",
})

mlflow.log_metrics({
    "eval/perplexity": 12.34,
    "eval/rouge-1": 0.45,
    "eval/rouge-l": 0.38,
    "eval/bleu-4": 0.28,
    "eval/bert_score": 0.72,
    "human/accuracy": 0.88,
    "human/completeness": 0.85,
    "human/fluency": 0.92,
})

mlflow.log_artifact("lora_adapter/")  # LoRA 权重
mlflow.log_artifact("training_config.json")
mlflow.log_artifact("eval_results.json")
```

### 2.5 模型注册与部署

```
微调完成 → 评估通过 → 注册模型 → 打包为 vLLM 模型 → 部署

1. 导出 LoRA adapter 权重
2. 合并到基座模型（或保持分离，vLLM 支持 LoRA）
3. 编写 Modelfile:
   FROM qwen2.5:7b-instruct
   ADAPTER ./ops-agent-v2.1-lora.bin
   PARAMETER temperature 0.7
   PARAMETER top_p 0.9
   SYSTEM \"\"\"你是运维智能客服助手...\"\"\"

4. 启动 vLLM 服务:
   vllm serve ops-agent:v2.1-lora --port 8000

5. Orchestrator 配置 A/B 测试:
   - 10% 流量 → ops-agent:v2.1-lora
   - 90% 流量 → ops-agent:v2.0-lora
```

---

## 三、A/B 测试与灰度发布

### 3.1 测试流程

```
Orchestrator 配置流量分配:
  {
    "models": {
      "production": {
        "name": "ops-agent:v2.0-lora",
        "weight": 90
      },
      "candidate": {
        "name": "ops-agent:v2.1-lora",
        "weight": 10
      }
    }
  }

数据收集（通过 Data Platform）:
  - 每个用户在会话期间固定路由到同一模型（一致性哈希）
  - 两组用户的反馈评分、转人工率、意图分类准确率分别统计

评估周期: 7 天
决策标准:
  - 候选模型满意度 > 生产模型 + 5%  → 全量切换
  - 候选模型满意度 < 生产模型         → 回滚，分析原因
  - 候选模型满意度 ≈ 生产模型         → 延长观察期或调整训练策略
```

### 3.2 灰度策略

| 阶段 | 流量比例 | 观察周期 | 通过条件 |
|------|---------|---------|---------|
| 金丝雀 | 5% | 1 天 | 无异常告警，满意度不下降 |
| 小流量 | 10% | 3 天 | 满意度 ≥ 生产模型 |
| 半流量 | 50% | 3 天 | 满意度 > 生产模型 + 3% |
| 全量 | 100% | 持续 | 持续监控 |

---

## 四、数据飞轮闭环

```
        ┌─────────────────────────────────────────┐
        │                                         │
        ▼                                         │
  ┌──────────┐    ┌──────────┐    ┌────────────┐  │
  │ 运行     │───→│ 采集     │───→│ 素材工厂    │  │
  │ (Agent)  │    │ (中台)   │    │ 生成问答对  │  │
  └──────────┘    └──────────┘    └─────┬──────┘  │
        ▲                               │         │
        │                               ▼         │
        │                        ┌────────────┐   │
        │                        │ 质量筛选    │   │
        │                        │ score ≥ 80  │   │
        │                        └─────┬──────┘   │
        │                              │         │
        │                              ▼         │
        │                        ┌────────────┐   │
        │                        │ 数据集构建  │   │
        └────────────────────────┤ QLoRA 微调  │   │
          部署 (Orchestrator)    │ 评估        │───┘
                                 │ A/B 测试    │
                                 └────────────┘

飞轮转速:
  - 素材工厂: 每天凌晨处理增量数据
  - 触发训练: 累计新增素材 ≥ 2000 条
  - 平均周期: 约 2-4 周完成一次完整飞轮循环
```

---

## 五、项目目录结构

```
f:\mysite\model-finetuning\
├── docker-compose.yml              # 微调环境编排
├── Dockerfile
├── requirements.txt
├── scripts/
│   ├── prepare_data.py             # 数据准备：从 Data Platform 拉取 → 格式转换
│   ├── train_lora.py               # QLoRA 微调主脚本
│   ├── merge_lora.py               # LoRA 权重合并到基座模型
│   ├── evaluate.py                 # 自动评估脚本
│   ├── export_vllm.py            # 导出为 vLLM 模型
│   └── run_pipeline.py             # 一键 Pipeline 入口
├── configs/
│   ├── lora_config.yaml            # LoRA 训练参数
│   └── model_config.yaml           # 模型版本配置
├── data/                           # 本地数据集缓存
│   ├── train/
│   ├── val/
│   └── test/
├── outputs/                        # 训练输出
│   ├── lora_adapters/              # LoRA 权重
│   └── mlflow/                     # MLflow 实验记录
├── models/                         # vLLM 模型模板
│   └── Modelfile.template
└── tests/
    ├── test_data_pipeline.py
    └── test_evaluate.py
```

---

## 六、Harness Engineering 集成

> 注：模型微调是批处理 Pipeline，不是 MCP Server。不向 Consul 注册服务，不由 Orchestrator 路由。以下 Harness 集成适配批处理场景。

### 6.1 健康检查端点

Pipeline 服务提供 `/health` 端点，返回训练环境和依赖状态：

```json
{
  "status": "healthy",
  "service": "model-finetuning",
  "version": "1.0.0",
  "checks": {
    "data_platform": "ok",
    "vllm": "ok",
    "mlflow": "ok",
    "gpu_available": true
  },
  "pipeline": {
    "last_run": "2026-08-04T02:00:00Z",
    "last_status": "success",
    "materials_pending": 1850
  },
  "timestamp": "2026-08-04T10:30:00Z"
}
```

### 6.2 traceId 全链路追踪

每次 Pipeline 运行生成唯一 `pipeline_run_id`（等价于 traceId），贯穿数据拉取、训练、评估、部署全流程：

```python
# logger.py 结构化日志格式
{
  "timestamp": "2026-08-04T02:00:00.123Z",
  "level": "INFO",
  "pipeline_run_id": "run-20260804-a1b2c3d4",  # 等价于 traceId
  "service": "model-finetuning",
  "step": "data_preparation",
  "dataset_version": "v20260804",
  "train_samples": 2000,
  "duration_ms": 1234,
  "message": "Dataset exported from Data Platform"
}
```

### 6.3 数据上报

训练完成后，评估结果和模型元数据回写至 Data Platform：

```python
# Pipeline 完成后异步上报
@celery_app.task(queue="data_collect")
async def report_training_result(result: dict, pipeline_run_id: str):
    await redis.lpush("data_collect", json.dumps({
        "event_id": str(uuid4()),
        "source_agent": "model-finetuning",
        "event_type": "training_completed",
        "timestamp": datetime.utcnow().isoformat(),
        "pipeline_run_id": pipeline_run_id,
        "payload": {
            "model_version": result["model_version"],
            "metrics": result["metrics"],
            "dataset_version": result["dataset_version"],
            "vllm_model_name": result["vllm_model_name"]
        }
    }))
```

### 6.4 降级策略

| 依赖故障 | 检测方式 | 降级行为 |
|---------|---------|---------|
| Data Platform 不可用 | 数据集导出请求超时（30s）或连接拒绝 | Pipeline 中止，记录 CRITICAL 日志；使用本地缓存的上次数据集（如有） |
| vLLM 不可用 | 模型创建/测试请求超时 | 跳过模型部署步骤，LoRA adapter 保存到 MLflow；标记"待部署"状态 |
| MLflow 不可用 | 连接超时或拒绝 | 训练仍正常执行，指标和 adapter 本地保存；MLflow 恢复后批量补录 |
| GPU 不可用 | CUDA 不可用或显存不足 | Pipeline 中止，发送告警通知；可降级为 CPU 训练（速度降低 10-20x） |
| 训练中途崩溃 | 异常退出 | 从最近的 checkpoint 恢复（save_steps=100），不从头开始 |

**降级恢复机制：** Pipeline 启动前检查所有依赖可用性，任一关键依赖（Data Platform、GPU）不可用则推迟执行并告警。非关键依赖（MLflow、vLLM）不可用时 Pipeline 继续运行，恢复后补录数据。

---

## 七、Docker 服务编排

```yaml
# model-finetuning/docker-compose.yml
services:
  mlflow:
    image: ghcr.io/mlflow/mlflow:v2.14.0
    ports: ["5000:5000"]
    command: mlflow server --host 0.0.0.0 --port 5000
    volumes:
      - ./outputs/mlflow:/mlflow

  finetuning:
    build: .
    ports: ["8500:8000"]
    environment:
      - MLFLOW_TRACKING_URI=http://mlflow:5000
      - DATA_PLATFORM_URL=http://data-platform:8400
      - VLLM_URL=http://vllm:8000
    volumes:
      - ./outputs:/app/outputs
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  # 可选：Jupyter Lab 用于实验分析
  jupyter:
    image: jupyter/scipy-notebook
    ports: ["8888:8888"]
    volumes:
      - ./outputs:/home/jovyan/outputs
```

---

## 八、向下串联

模型微调闭环是数据飞轮的终点，同时也是新循环的起点：

- **微调后模型** → 替换 Ops Agent 的 LLM → 提升回答质量 → 用户满意度上升 → 更多高质量对话 → 数据中台积累更多素材 → 触发下一次微调
- **评估结果** → 回写至 Data Platform → 素材工厂根据评估结果调整生成策略（如某类问题回答质量低，优先为该类问题生成训练样本）
- **A/B 测试指标** → 反馈至微调 Pipeline → 指导下一轮训练的超参数调整

**与 Orchestrator 的交互：** 微调后的模型通过 vLLM 注册后，Orchestrator 在工具集市中更新 Ops Agent 的 LLM 配置，实现模型切换。A/B 测试期间，Orchestrator 根据流量比例路由到不同模型版本的 Ops Agent 实例。