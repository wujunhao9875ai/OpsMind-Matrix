"""数据采集定时任务"""
from app.tasks.celery_app import celery_app
from app.core.logger import setup_logger

logger = setup_logger("collect_tasks")


@celery_app.task(name="app.tasks.collect_tasks.collect_data")
def collect_data():
    """Periodic task to collect data from Redis queue."""
    logger.info("Running collect_data task")
    # In production, this would call data_collector.consume_events()
    return {"status": "completed", "events_collected": 0}


@celery_app.task(name="app.tasks.collect_tasks.import_data")
def import_data(source: str, payload: list):
    """Task to import data from external sources."""
    logger.info(f"Running import_data task for source: {source}, count: {len(payload)}")
    # In production, validate and store payload
    return {"status": "completed", "source": source, "imported": len(payload)}