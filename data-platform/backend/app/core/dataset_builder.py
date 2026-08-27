"""数据集构建 - 导出训练/验证/测试集"""
import json
import os
import uuid
from datetime import datetime, timezone
from app.core.logger import setup_logger, log_event

logger = setup_logger("dataset_builder")


async def export_dataset(dataset_type: str = "qa", format: str = "jsonl", split: str = "train", size: int = 1000) -> dict:
    """Export dataset for model training."""
    # Simulated dataset export (in production, query from DB and write to MinIO)
    export_dir = "data/exports"
    os.makedirs(export_dir, exist_ok=True)

    filename = f"{dataset_type}_{split}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.{format}"
    filepath = os.path.join(export_dir, filename)

    # Generate sample data
    samples = []
    for i in range(min(size, 100)):
        sample = {
            "instruction": "你是运维智能客服助手，请根据知识库内容回答用户问题。",
            "input": f"示例问题 {i+1}",
            "output": f"示例回答 {i+1}",
        }
        samples.append(sample)

    if format == "jsonl":
        with open(filepath, "w", encoding="utf-8") as f:
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    log_event(logger, "dataset_exported", dataset_type=dataset_type, split=split, count=len(samples))
    return {
        "dataset_id": str(uuid.uuid4()),
        "dataset_type": dataset_type,
        "format": format,
        "split": split,
        "record_count": len(samples),
        "file_url": filepath,
        "status": "completed",
    }