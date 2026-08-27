"""质量评分 - 评估素材质量"""
from app.core.logger import setup_logger

logger = setup_logger("quality_scorer")


async def score_material(question: str, answer: str) -> float:
    """Score a single material QA pair for quality (0-100)."""
    score = 70.0  # Base score

    # Length checks
    if len(question) >= 10:
        score += 5
    if len(answer) >= 20:
        score += 5

    # Content checks
    if "?" in question or "？" in question:
        score += 5
    if any(kw in answer for kw in ["步骤", "方法", "建议", "注意"]):
        score += 5

    # Penalties
    if len(question) < 5:
        score -= 10
    if len(answer) < 10:
        score -= 10

    return min(100.0, max(0.0, score))


async def batch_score(materials: list) -> list:
    """Score a batch of materials."""
    results = []
    for m in materials:
        score = await score_material(m.get("question", ""), m.get("answer", ""))
        m["quality_score"] = score
        results.append(m)
    return results