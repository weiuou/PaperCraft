import uuid

from app.worker.tasks import run_generation_task


def enqueue_generation_task(task_id: uuid.UUID) -> None:
    run_generation_task.delay(str(task_id))
