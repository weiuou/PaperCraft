import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Artifact, AssemblyMetadata, GenerationTask, SourceImage, TaskEvent
from app.domain.enums import ArtifactKind, ErrorCode, TaskEventType, TaskStage, TaskStatus
from app.services.mock_artifacts import mock_artifact_content
from app.services.object_storage import ObjectStorageError, get_upload_bytes, put_artifact_bytes
from app.services.preprocessing import (
    PreprocessingFailed,
    PreprocessingSubjectNotFound,
    preprocess_source_image,
)
from app.services.storage_paths import ArtifactPathGroup, task_artifact_key

logger = logging.getLogger("papercraft.worker")


class TaskExecutionError(Exception):
    def __init__(self, code: ErrorCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class StageResult:
    progress: int
    message: str
    metadata: dict[str, object] | None = None


class MockStageExecutor:
    def execute(self, task: GenerationTask, stage: TaskStage) -> StageResult:
        messages = {
            TaskStage.PREPROCESSING: "Mock preprocessing completed.",
            TaskStage.MODEL_GENERATING: "Mock model generation completed.",
            TaskStage.PAPERABILITY_OPTIMIZING: "Mock paperability optimization completed.",
            TaskStage.DECIMATING: "Mock decimation completed.",
            TaskStage.UNFOLDING: "Mock unfolding completed.",
            TaskStage.EXPORTING: "Mock export completed.",
        }
        progress = {
            TaskStage.PREPROCESSING: 15,
            TaskStage.MODEL_GENERATING: 35,
            TaskStage.PAPERABILITY_OPTIMIZING: 50,
            TaskStage.DECIMATING: 65,
            TaskStage.UNFOLDING: 85,
            TaskStage.EXPORTING: 95,
        }
        return StageResult(
            progress=progress[stage],
            message=messages[stage],
            metadata={"executor": "mock", "task_id": str(task.id), "stage": stage.value},
        )


PIPELINE_EXECUTION_STAGES: tuple[TaskStage, ...] = (
    TaskStage.PREPROCESSING,
    TaskStage.MODEL_GENERATING,
    TaskStage.PAPERABILITY_OPTIMIZING,
    TaskStage.DECIMATING,
    TaskStage.UNFOLDING,
    TaskStage.EXPORTING,
)


def cancel_generation_task(db: Session, task_id: uuid.UUID) -> bool:
    task = db.get(GenerationTask, task_id)
    if task is None or task.status not in {TaskStatus.QUEUED.value, TaskStatus.IN_PROGRESS.value}:
        return False
    task.status = TaskStatus.CANCELED.value
    task.finished_at = datetime.now(UTC)
    _add_event(db, task, TaskEventType.CANCELED, "Task cancellation requested.", stage=task.stage)
    db.commit()
    return True


def request_retry_from_stage(db: Session, task_id: uuid.UUID, stage: TaskStage) -> bool:
    task = db.get(GenerationTask, task_id)
    if task is None or task.status not in {TaskStatus.FAILED.value, TaskStatus.CANCELED.value}:
        return False
    if stage not in PIPELINE_EXECUTION_STAGES:
        return False
    task.status = TaskStatus.QUEUED.value
    task.stage = stage.value
    task.progress = 0
    task.retry_from_stage = stage.value
    task.error_code = None
    task.error_message = None
    task.started_at = None
    task.finished_at = None
    _add_event(
        db,
        task,
        TaskEventType.RETRY_REQUESTED,
        "Task retry requested.",
        stage=stage.value,
        metadata={"clear_mock_failure": True},
    )
    db.commit()
    return True


def run_generation_pipeline(
    db: Session,
    task_id: uuid.UUID,
    *,
    executor: MockStageExecutor | None = None,
) -> GenerationTask:
    executor = executor or MockStageExecutor()
    task = db.get(GenerationTask, task_id)
    if task is None:
        raise ValueError(f"Task not found: {task_id}")
    if task.status == TaskStatus.CANCELED.value:
        return task
    if task.status not in {TaskStatus.QUEUED.value, TaskStatus.IN_PROGRESS.value}:
        raise ValueError(f"Task {task_id} is not runnable from status {task.status}")

    task.status = TaskStatus.IN_PROGRESS.value
    task.started_at = task.started_at or datetime.now(UTC)
    task.finished_at = None
    task.error_code = None
    task.error_message = None
    _add_event(db, task, TaskEventType.STAGE_STARTED, "Worker picked up task.", stage=task.stage)
    db.commit()
    logger.info(
        "Task picked up by worker. task_id=%s stage=%s",
        task.id,
        task.stage,
        extra={"task_id": str(task.id), "stage": task.stage},
    )

    try:
        for stage in _stages_for_task(task):
            db.refresh(task)
            if task.status == TaskStatus.CANCELED.value:
                _add_event(db, task, TaskEventType.CANCELED, "Task canceled before stage execution.", stage=stage.value)
                db.commit()
                return task

            task.stage = stage.value
            _add_event(db, task, TaskEventType.STAGE_STARTED, f"{stage.value} started.", stage=stage.value)
            db.commit()
            logger.info(
                "Stage started. task_id=%s stage=%s",
                task.id,
                stage.value,
                extra={"task_id": str(task.id), "stage": stage.value},
            )

            mock_failure = _mock_failure_for_stage(db, task, stage)
            if mock_failure is not None:
                raise TaskExecutionError(mock_failure, f"Mock failure at {stage.value}.")

            result = _run_preprocessing_stage(db, task) if stage == TaskStage.PREPROCESSING else executor.execute(task, stage)
            task.progress = result.progress
            _add_event(
                db,
                task,
                TaskEventType.STAGE_COMPLETED,
                result.message,
                stage=stage.value,
                metadata=result.metadata or {},
            )
            _add_event(
                db,
                task,
                TaskEventType.PROGRESS_UPDATED,
                f"Task progress updated to {result.progress}.",
                stage=stage.value,
                metadata={"progress": result.progress},
            )
            db.commit()
            logger.info(
                "Stage completed. task_id=%s stage=%s progress=%s",
                task.id,
                stage.value,
                result.progress,
                extra={"task_id": str(task.id), "stage": stage.value},
            )

        task.stage = TaskStage.COMPLETED.value
        task.status = TaskStatus.COMPLETED.value
        task.progress = 100
        task.finished_at = datetime.now(UTC)
        _create_mock_outputs(db, task)
        _add_event(db, task, TaskEventType.COMPLETED, "Task completed.", stage=TaskStage.COMPLETED.value)
        db.commit()
        logger.info(
            "Task completed. task_id=%s stage=%s progress=%s",
            task.id,
            task.stage,
            task.progress,
            extra={"task_id": str(task.id), "stage": task.stage},
        )
        return task
    except TaskExecutionError as exc:
        task.status = TaskStatus.FAILED.value
        task.error_code = exc.code.value
        task.error_message = exc.message
        task.finished_at = datetime.now(UTC)
        _add_event(db, task, TaskEventType.FAILED, exc.message, stage=task.stage, metadata={"error_code": exc.code.value})
        db.commit()
        logger.exception(
            "Task failed. task_id=%s stage=%s error_code=%s",
            task.id,
            task.stage,
            exc.code.value,
            extra={"task_id": str(task.id), "stage": task.stage, "error_code": exc.code.value},
        )
        return task
    except Exception as exc:
        task.status = TaskStatus.FAILED.value
        task.error_code = ErrorCode.INTERNAL_ERROR.value
        task.error_message = str(exc)
        task.finished_at = datetime.now(UTC)
        _add_event(
            db,
            task,
            TaskEventType.FAILED,
            str(exc),
            stage=task.stage,
            metadata={"error_code": ErrorCode.INTERNAL_ERROR.value},
        )
        db.commit()
        logger.exception(
            "Task failed unexpectedly. task_id=%s stage=%s",
            task.id,
            task.stage,
            extra={"task_id": str(task.id), "stage": task.stage},
        )
        return task


def _stages_for_task(task: GenerationTask) -> Iterable[TaskStage]:
    if task.retry_from_stage:
        retry_stage = TaskStage(task.retry_from_stage)
        start_index = PIPELINE_EXECUTION_STAGES.index(retry_stage)
        return PIPELINE_EXECUTION_STAGES[start_index:]
    return PIPELINE_EXECUTION_STAGES


def _mock_failure_for_stage(db: Session, task: GenerationTask, stage: TaskStage) -> ErrorCode | None:
    events = db.scalars(
        select(TaskEvent)
        .where(TaskEvent.task_id == task.id)
        .order_by(TaskEvent.created_at.desc(), TaskEvent.id.desc())
    ).all()
    if any(event.event_type == TaskEventType.RETRY_REQUESTED.value for event in events):
        return None
    requested_stage = next(
        (
            event.event_metadata.get("mock_failure_stage")
            for event in events
            if event.event_type == TaskEventType.QUEUED.value and event.event_metadata.get("mock_failure_stage")
        ),
        None,
    )
    if requested_stage != stage.value:
        return None
    return {
        TaskStage.PREPROCESSING: ErrorCode.PREPROCESS_FAILED,
        TaskStage.MODEL_GENERATING: ErrorCode.MODEL_GEN_FAILED,
        TaskStage.PAPERABILITY_OPTIMIZING: ErrorCode.PAPERABILITY_OPT_FAILED,
        TaskStage.DECIMATING: ErrorCode.DECIMATE_FAILED,
        TaskStage.UNFOLDING: ErrorCode.UNFOLD_FAILED,
        TaskStage.EXPORTING: ErrorCode.EXPORT_FAILED,
    }[stage]


def _run_preprocessing_stage(db: Session, task: GenerationTask) -> StageResult:
    source_image = db.scalar(
        select(SourceImage).where(SourceImage.project_id == task.project_id).order_by(SourceImage.sort_order)
    )
    if source_image is None:
        raise TaskExecutionError(
            ErrorCode.PREPROCESS_SUBJECT_NOT_FOUND,
            "Project has no source image available for preprocessing.",
        )

    try:
        content = get_upload_bytes(source_image.storage_key)
        result = preprocess_source_image(
            source_image_id=source_image.id,
            source_storage_key=source_image.storage_key,
            content=content,
        )
    except ObjectStorageError as exc:
        raise TaskExecutionError(exc.code, exc.message) from exc
    except PreprocessingSubjectNotFound as exc:
        raise TaskExecutionError(ErrorCode.PREPROCESS_SUBJECT_NOT_FOUND, str(exc)) from exc
    except PreprocessingFailed as exc:
        raise TaskExecutionError(ErrorCode.PREPROCESS_FAILED, str(exc)) from exc

    for payload in result.artifacts:
        artifact_id = uuid.uuid4()
        storage_key = task_artifact_key(task.project_id, task.id, ArtifactPathGroup.PREPROCESS, artifact_id, payload.filename)
        try:
            put_artifact_bytes(storage_key, payload.content, payload.mime_type)
        except ObjectStorageError as exc:
            raise TaskExecutionError(exc.code, exc.message) from exc

        db.add(
            Artifact(
                id=artifact_id,
                task_id=task.id,
                kind=payload.kind.value,
                storage_key=storage_key,
                mime_type=payload.mime_type,
                file_size=len(payload.content),
                artifact_metadata=payload.metadata,
            )
        )

    return StageResult(
        progress=15,
        message="Image preprocessing completed.",
        metadata=result.metadata,
    )


def _add_event(
    db: Session,
    task: GenerationTask,
    event_type: TaskEventType,
    message: str,
    *,
    stage: str | None,
    metadata: dict[str, object] | None = None,
) -> None:
    db.add(
        TaskEvent(
            task_id=task.id,
            stage=stage,
            event_type=event_type.value,
            message=message,
            event_metadata=metadata or {},
        )
    )


def _create_mock_outputs(db: Session, task: GenerationTask) -> None:
    if task.assembly_metadata is not None:
        return

    outputs = (
        (
            ArtifactKind.PREVIEW_MODEL,
            ArtifactPathGroup.PREVIEWS,
            "mock-preview-model.glb",
            "model/gltf-binary",
            4096,
            {"mock": True, "label": "3D preview placeholder"},
        ),
        (
            ArtifactKind.NET_JSON,
            ArtifactPathGroup.NETS,
            "mock-paper-net.json",
            "application/json",
            2048,
            {"mock": True, "pages": 3, "fold_lines": True, "glue_flaps": True},
        ),
        (
            ArtifactKind.EXPORT_PDF,
            ArtifactPathGroup.EXPORTS,
            "mock-papercraft.pdf",
            "application/pdf",
            8192,
            {"mock": True, "paper_size": "a4", "printable": True},
        ),
    )

    for kind, group, filename, mime_type, file_size, metadata in outputs:
        artifact_id = uuid.uuid4()
        content = mock_artifact_content(artifact_id, kind.value)
        storage_key = task_artifact_key(task.project_id, task.id, group, artifact_id, filename)
        try:
            put_artifact_bytes(storage_key, content, mime_type)
        except ObjectStorageError as exc:
            raise TaskExecutionError(exc.code, exc.message) from exc

        db.add(
            Artifact(
                id=artifact_id,
                task_id=task.id,
                kind=kind.value,
                storage_key=storage_key,
                mime_type=mime_type,
                file_size=len(content) or file_size,
                artifact_metadata=metadata,
            )
        )

    db.add(
        AssemblyMetadata(
            task_id=task.id,
            page_count=3,
            part_count=12,
            difficulty_score=3,
            estimated_build_minutes=45,
            assembly_metadata={
                "mock": True,
                "instruction_sheet": True,
                "cut_lines": True,
                "fold_lines": True,
                "glue_flaps": True,
                "pair_numbering": True,
            },
        )
    )
