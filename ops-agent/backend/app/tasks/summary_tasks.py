from app.tasks.celery_app import celery_app
from app.core.memory_manager import generate_summary


@celery_app.task
def generate_summary_task(early_messages: list[dict]) -> str:
    """异步生成对话摘要。"""
    return generate_summary(early_messages)