import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.models import GenerationTask, TaskEvent
from app.domain.enums import ErrorCode, TaskEventType, TaskStage, TaskStatus

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
    _add_event(db, task, TaskEventType.RETRY_REQUESTED, "Task retry requested.", stage=stage.value)
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

            result = executor.execute(task, stage)
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
