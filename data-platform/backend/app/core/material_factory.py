"""素材工厂 - 自动化生成训练样本"""
import uuid
from datetime import datetime, timezone
from app.core.logger import setup_logger, log_event

logger = setup_logger("material_factory")


async def generate_materials(source_type: str = "conversations", count: int = 100, quality_threshold: int = 80) -> dict:
    """Generate training materials from source data."""
    # In production, this would use LLM to generate QA pairs from conversations
    # For now, return a simulated result
    generated = []
    for i in range(min(count, 10)):  # Simulate generating 10 materials
        material = {
            "id": str(uuid.uuid4()),
            "question": f"运维问题示例 {i+1}",
            "answer": f"这是示例答案 {i+1}，包含具体的操作步骤和注意事项。",
            "material_type": "qa_pair",
            "quality_score": 85 + (i % 10),
            "tags": ["运维", "示例"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        generated.append(material)

    log_event(logger, "materials_generated", count=len(generated), source_type=source_type)
    return {"generated_count": len(generated), "materials": generated, "status": "completed"}