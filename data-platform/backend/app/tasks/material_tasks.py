"""素材生成定时任务"""
from app.tasks.celery_app import celery_app
from app.core.logger import setup_logger

logger = setup_logger("material_tasks")


@celery_app.task(name="app.tasks.material_tasks.generate_materials")
def generate_materials():
    """Periodic task to generate training materials."""
    logger.info("Running generate_materials task")
    # In production, call material_factory.generate_materials()
    return {"status": "completed", "generated": 0}


@celery_app.task(name="app.tasks.material_tasks.score_materials")
def score_materials(material_ids: list):
    """Task to quality-score materials."""
    logger.info(f"Running score_materials task for {len(material_ids)} materials")
    return {"status": "completed", "scored": len(material_ids)}