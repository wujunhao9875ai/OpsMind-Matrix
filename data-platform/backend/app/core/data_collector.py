"""数据采集 - 从 Redis 队列消费各 Agent 上报的数据"""
import json
import redis.asyncio as redis
from app.config import settings
from app.core.logger import setup_logger, log_event

logger = setup_logger("data_collector")
redis_client = redis.from_url(settings.redis_url, decode_responses=True)


async def consume_events():
    """Consume events from the data_collect queue."""
    while True:
        try:
            result = await redis_client.brpop("data_collect", timeout=10)
            if not result:
                continue
            _, data = result
            event = json.loads(data)
            await process_event(event)
        except Exception as e:
            log_event(logger, "consume_error", level="ERROR", error=str(e))


async def process_event(event: dict):
    """Process and store a single event."""
    from app.database import async_session
    from app.models.raw_event import RawEvent

    async with async_session() as db:
        raw = RawEvent(
            event_id=event.get("event_id"),
            source_agent=event.get("source_agent"),
            event_type=event.get("event_type"),
            trace_id=event.get("trace_id"),
            user_id=event.get("user_id"),
            payload=event.get("payload"),
            event_metadata=event.get("metadata"),
        )
        db.add(raw)
        await db.commit()
    log_event(logger, "event_processed", source_agent=event.get("source_agent"), event_type=event.get("event_type"))