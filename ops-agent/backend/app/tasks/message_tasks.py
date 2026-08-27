from app.tasks.celery_app import celery_app
from app.utils.coverage_guard import validate_citations


@celery_app.task(bind=True, max_retries=3)
def validate_citation_task(self, message_id: str, answer: str, valid_source_ids: list):
    """异步校验回答中的来源引用。"""
    try:
        result = validate_citations(answer, valid_source_ids)
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)