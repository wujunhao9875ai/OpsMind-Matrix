"""QLoRA 微调脚本 - 框架代码（需 GPU 环境实际运行）"""
import json
import os

# Training configuration (matches design doc)
TRAINING_CONFIG = {
    "base_model": "Qwen/Qwen2.5-7B-Instruct",
    "lora_config": {
        "r": 16,
        "lora_alpha": 32,
        "lora_dropout": 0.1,
        "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        "bias": "none",
        "task_type": "CAUSAL_LM",
    },
    "quantization": {
        "load_in_4bit": True,
        "bnb_4bit_compute_dtype": "float16",
        "bnb_4bit_quant_type": "nf4",
        "bnb_4bit_use_double_quant": True,
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
        "packing": False,
    },
}


def train_lora(
    data_dir: str = "./data",
    output_dir: str = "./outputs/lora_adapters",
    config: dict = None,
):
    """Train LoRA adapter using QLoRA."""
    if config is None:
        config = TRAINING_CONFIG

    os.makedirs(output_dir, exist_ok=True)

    print(f"QLoRA Training Configuration:")
    print(f"  Base Model: {config['base_model']}")
    print(f"  LoRA rank: {config['lora_config']['r']}")
    print(f"  Learning rate: {config['training']['learning_rate']}")
    print(f"  Epochs: {config['training']['num_train_epochs']}")
    print(f"  Batch size: {config['training']['per_device_train_batch_size']}")
    print(f"  Max seq length: {config['training']['max_seq_length']}")
    print()
    print("NOTE: This is a framework script. Actual training requires:")
    print("  - GPU with CUDA support (RTX 3090/4090 or better)")
    print("  - PyTorch + Transformers + PEFT + bitsandbytes installed")
    print("  - Training data from Data Platform")
    print()

    # In production, this would:
    # 1. Load base model with 4-bit quantization
    # 2. Apply LoRA config
    # 3. Load training data
    # 4. Train with SFTTrainer
    # 5. Save adapter weights

    # Save config for reference
    config_path = os.path.join(output_dir, "training_config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    return {
        "status": "framework_ready",
        "output_dir": output_dir,
        "config": config,
    }


if __name__ == "__main__":
    train_lora()