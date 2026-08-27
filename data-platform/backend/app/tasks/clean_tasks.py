"""数据清洗定时任务"""
from app.tasks.celery_app import celery_app
from app.core.logger import setup_logger

logger = setup_logger("clean_tasks")


@celery_app.task(name="app.tasks.clean_tasks.clean_data")
def clean_data():
    """Periodic task to clean and deduplicate data."""
    logger.info("Running clean_data task")
    # In production, query raw_events and apply cleaning + dedup
    return {"status": "completed", "cleaned": 0, "deduplicated": 0}


@celery_app.task(name="app.tasks.clean_tasks.deduplicate_materials")
def deduplicate_materials():
    """Task to deduplicate materials."""
    logger.info("Running deduplicate_materials task")
    return {"status": "completed", "removed": 0}