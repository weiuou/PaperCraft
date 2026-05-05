import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.errors import ApiError
from app.db.models import GenerationTask
from app.domain.enums import ErrorCode
from app.schemas.tasks import TaskStatusResponse

router = APIRouter(tags=["tasks"])


def _get_task_or_404(db: Session, task_id: uuid.UUID) -> GenerationTask:
    task = db.get(GenerationTask, task_id)
    if task is None:
        raise ApiError(
            ErrorCode.TASK_NOT_FOUND,
            "Task was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"task_id": str(task_id)},
        )
    return task


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: uuid.UUID, db: Session = Depends(get_db)) -> TaskStatusResponse:
    task = _get_task_or_404(db, task_id)
    return TaskStatusResponse(
        task_id=task.id,
        project_id=task.project_id,
        status=task.status,
        stage=task.stage,
        progress=task.progress,
        error_code=task.error_code,
        error_message=task.error_message,
        started_at=task.started_at,
        finished_at=task.finished_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
