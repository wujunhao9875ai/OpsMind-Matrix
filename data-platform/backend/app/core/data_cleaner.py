"""数据清洗 - 处理脏数据、格式化、标准化"""
from app.core.logger import setup_logger, log_event

logger = setup_logger("data_cleaner")


async def clean_event(event: dict) -> dict:
    """Clean a single event - trim whitespace, normalize fields."""
    cleaned = {}
    for key, value in event.items():
        if isinstance(value, str):
            cleaned[key] = value.strip()
        else:
            cleaned[key] = value
    log_event(logger, "event_cleaned", event_id=cleaned.get("event_id"))
    return cleaned


async def clean_material(question: str, answer: str) -> dict:
    """Clean a material QA pair - remove extra whitespace, ensure valid content."""
    q = question.strip()
    a = answer.strip()
    if not q or not a:
        return {"valid": False, "reason": "Empty question or answer"}
    return {"valid": True, "question": q, "answer": a}