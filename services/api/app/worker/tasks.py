import uuid

from app.db.session import SessionLocal
from app.worker.celery_app import celery_app
from app.worker.orchestrator import run_generation_pipeline


@celery_app.task(name="papercraft.run_generation_task")
def run_generation_task(task_id: str) -> str:
    parsed_task_id = uuid.UUID(task_id)
    with SessionLocal() as db:
        task = run_generation_pipeline(db, parsed_task_id)
        return task.status
