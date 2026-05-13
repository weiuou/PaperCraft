import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.errors import ApiError
from app.db.models import Artifact, GenerationTask
from app.domain.enums import ErrorCode, TaskStage, TaskStatus
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
        next_actions=_next_actions_for_task(task, artifacts),
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


def _next_actions_for_task(task: GenerationTask, artifacts: list[Artifact]) -> list[str]:
    actions: list[str] = []
    if task.status == TaskStatus.FAILED.value and task.error_code:
        actions.extend(_next_actions_for_error(task.error_code))
    if task.status == TaskStatus.CANCELED.value:
        actions.append("Retry from the selected stage when you are ready to continue.")
    for artifact in artifacts:
        artifact_actions = artifact.artifact_metadata.get("next_actions")
        if isinstance(artifact_actions, list):
            actions.extend(str(action) for action in artifact_actions)
        if artifact.artifact_metadata.get("fallback_simplification") is True:
            actions.append("Layout was simplified automatically to stay within the page budget.")
        if artifact.artifact_metadata.get("auto_fallback") is True:
            actions.append("A fallback path adjusted complexity automatically.")
        warnings = artifact.artifact_metadata.get("buildability_warnings")
        if isinstance(warnings, list):
            actions.extend(str(warning) for warning in warnings)
    return list(dict.fromkeys(actions))


def _next_actions_for_error(error_code: str) -> list[str]:
    return {
        ErrorCode.PREPROCESS_SUBJECT_NOT_FOUND.value: [
            "Upload a cleaner image with one centered subject and stronger contrast.",
            "Retry from preprocessing after replacing the source image.",
        ],
        ErrorCode.PREPROCESS_FAILED.value: ["Retry from preprocessing or use a simpler, higher-contrast image."],
        ErrorCode.MODEL_GEN_FAILED.value: ["Retry from model generation with a lower target poly count."],
        ErrorCode.PAPERABILITY_OPT_FAILED.value: ["Retry from paperability after choosing simpler settings."],
        ErrorCode.DECIMATE_FAILED.value: ["Lower target poly count or increase max pages, then retry from decimating."],
        ErrorCode.UNFOLD_FAILED.value: ["Increase max pages or reduce target poly count, then retry from unfolding."],
        ErrorCode.EXPORT_FAILED.value: ["Retry from exporting. Prior net artifacts should remain available."],
        ErrorCode.STORAGE_READ_FAILED.value: ["Check object storage availability and retry the failed stage."],
        ErrorCode.STORAGE_WRITE_FAILED.value: ["Check object storage availability and retry the failed stage."],
        ErrorCode.INTERNAL_ERROR.value: ["Retry the task from the failed stage. Check worker logs if it fails again."],
    }.get(error_code, ["Retry the task from the failed stage or regenerate with simpler settings."])
