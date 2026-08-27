"""数据准备 - 从 Data Platform 拉取数据集并转换为训练格式"""
import json
import os
from datetime import datetime


def prepare_data(
    dataset_type: str = "qa",
    train_size: int = 2000,
    val_size: int = 500,
    test_size: int = 500,
    data_dir: str = "./data",
):
    """Prepare training data from Data Platform."""
    os.makedirs(f"{data_dir}/train", exist_ok=True)
    os.makedirs(f"{data_dir}/val", exist_ok=True)
    os.makedirs(f"{data_dir}/test", exist_ok=True)

    # This would fetch from Data Platform API in production
    # For now, create placeholder structure
    print(f"Data preparation: {dataset_type} dataset, train={train_size}, val={val_size}, test={test_size}")

    # Template for instruction format
    template = {
        "instruction": "你是运维智能客服助手，请根据知识库内容回答用户问题。",
        "input": "示例问题",
        "output": "示例回答",
    }

    return {
        "status": "completed",
        "train_samples": train_size,
        "val_samples": val_size,
        "test_samples": test_size,
        "data_dir": data_dir,
    }


if __name__ == "__main__":
    prepare_data()