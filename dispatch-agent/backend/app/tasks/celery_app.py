from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "dispatch_agent",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "check_sla_breach": {
            "task": "check_sla_breach",
            "schedule": 300.0,
        },
        "check_unassigned_pool": {
            "task": "check_unassigned_pool",
            "schedule": 60.0,
        },
        "auto_close_tickets": {
            "task": "auto_close_tickets",
            "schedule": crontab(minute=0, hour="*"),
        },
        "sync_engineer_load": {
            "task": "sync_engineer_load",
            "schedule": 60.0,
        },
    },
)