from celery import Celery
from app.config import settings

celery_app = Celery(
    "data_platform",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.collect_tasks",
        "app.tasks.clean_tasks",
        "app.tasks.material_tasks",
        "app.tasks.snapshot_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    beat_schedule={
        "collect-data-every-5-minutes": {
            "task": "app.tasks.collect_tasks.collect_data",
            "schedule": 300.0,
        },
        "clean-data-every-hour": {
            "task": "app.tasks.clean_tasks.clean_data",
            "schedule": 3600.0,
        },
        "generate-materials-every-30-minutes": {
            "task": "app.tasks.material_tasks.generate_materials",
            "schedule": 1800.0,
        },
        "snapshot-analytics-every-15-minutes": {
            "task": "app.tasks.snapshot_tasks.snapshot_analytics",
            "schedule": 900.0,
        },
    },
)