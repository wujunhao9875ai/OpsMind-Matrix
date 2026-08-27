from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "warehouse_agent",
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
        "check_inventory_threshold": {
            "task": "check_inventory_threshold",
            "schedule": crontab(minute="*/30"),
        },
        "check_idle_devices": {
            "task": "check_idle_devices",
            "schedule": crontab(minute=0, hour=1),
        },
        "weekly_damaged_report": {
            "task": "weekly_damaged_report",
            "schedule": crontab(minute=0, hour=9, day_of_week=1),
        },
        "check_repair_overdue": {
            "task": "check_repair_overdue",
            "schedule": crontab(minute=0, hour=8),
        },
        "sync_spare_requests": {
            "task": "sync_spare_requests",
            "schedule": 30.0,
        },
    },
)