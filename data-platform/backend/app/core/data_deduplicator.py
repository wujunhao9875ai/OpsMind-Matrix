"""数据去重 - 基于语义相似度去重"""
from app.core.logger import setup_logger, log_event

logger = setup_logger("data_deduplicator")


async def deduplicate_materials(materials: list, threshold: float = 0.95) -> list:
    """Deduplicate materials based on question similarity."""
    # In production, use embedding similarity via vLLM
    # For now, use simple exact-match dedup
    seen = set()
    unique = []
    for m in materials:
        key = m.get("question", "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(m)
    removed = len(materials) - len(unique)
    if removed > 0:
        log_event(logger, "dedup_completed", original=len(materials), unique=len(unique), removed=removed)
    return unique


async def deduplicate_events(events: list) -> list:
    """Deduplicate events by event_id."""
    seen_ids = set()
    unique = []
    for e in events:
        eid = e.get("event_id")
        if eid and eid not in seen_ids:
            seen_ids.add(eid)
            unique.append(e)
    return unique