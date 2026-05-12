import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.errors import ApiError
from app.db.models import Artifact, GenerationTask
from app.domain.enums import ErrorCode, TaskStage
from app.schemas.tasks import ArtifactResponse, AssemblyMetadataResponse, RetryTaskRequest, TaskStatusResponse
from app.services.task_dispatch import enqueue_generation_task
from app.worker.orchestrator import cancel_generation_task, request_retry_from_stage

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
    return task_status_response(db, task)


@router.post("/tasks/{task_id}/cancel", response_model=TaskStatusResponse)
def cancel_task(task_id: uuid.UUID, db: Session = Depends(get_db)) -> TaskStatusResponse:
    if not cancel_generation_task(db, task_id):
        raise ApiError(
            ErrorCode.TASK_INVALID_STATE,
            "Task cannot be canceled from its current state.",
            details={"task_id": str(task_id)},
        )
    task = _get_task_or_404(db, task_id)
    return task_status_response(db, task)


@router.post("/tasks/{task_id}/retry", response_model=TaskStatusResponse)
def retry_task(task_id: uuid.UUID, payload: RetryTaskRequest, db: Session = Depends(get_db)) -> TaskStatusResponse:
    if payload.stage == TaskStage.COMPLETED:
        raise ApiError(
            ErrorCode.TASK_RETRY_NOT_ALLOWED,
            "Task retry must start from an execution stage.",
            details={"task_id": str(task_id), "stage": payload.stage.value},
        )
    if not request_retry_from_stage(db, task_id, payload.stage):
        raise ApiError(
            ErrorCode.TASK_RETRY_NOT_ALLOWED,
            "Task cannot be retried from its current state.",
            details={"task_id": str(task_id), "stage": payload.stage.value},
        )
    enqueue_generation_task(task_id)
    task = _get_task_or_404(db, task_id)
    return task_status_response(db, task)


def task_status_response(db: Session, task: GenerationTask) -> TaskStatusResponse:
    artifacts = db.scalars(select(Artifact).where(Artifact.task_id == task.id).order_by(Artifact.created_at)).all()
    return TaskStatusResponse(
        task_id=task.id,
        project_id=task.project_id,
        status=task.status,
        stage=task.stage,
        progress=task.progress,
        error_code=task.error_code,
        error_message=task.error_message,
        artifacts=[
            ArtifactResponse(
                artifact_id=artifact.id,
                kind=artifact.kind,
                storage_key=artifact.storage_key,
                download_url=f"/api/artifacts/{artifact.id}/download",
                mime_type=artifact.mime_type,
                file_size=artifact.file_size,
                metadata=artifact.artifact_metadata,
                created_at=artifact.created_at,
            )
            for artifact in artifacts
        ],
        assembly_metadata=(
            AssemblyMetadataResponse(
                page_count=task.assembly_metadata.page_count,
                part_count=task.assembly_metadata.part_count,
                difficulty_score=task.assembly_metadata.difficulty_score,
                estimated_build_minutes=task.assembly_metadata.estimated_build_minutes,
                metadata=task.assembly_metadata.assembly_metadata,
            )
            if task.assembly_metadata is not None
            else None
        ),
        started_at=task.started_at,
        finished_at=task.finished_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
