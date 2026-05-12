import uuid
import logging
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db import models  # noqa: F401
from app.db.models import Artifact, AssemblyMetadata, GenerationTask, Project, TaskEvent, User
from app.domain.enums import ArtifactKind, ErrorCode, ProjectCategory, ProjectStatus, TaskEventType, TaskStage, TaskStatus
from app.worker.orchestrator import (
    MockStageExecutor,
    StageResult,
    TaskExecutionError,
    cancel_generation_task,
    request_retry_from_stage,
    run_generation_pipeline,
)


@pytest.fixture(autouse=True)
def mock_object_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.worker.orchestrator.put_artifact_bytes", lambda *_args, **_kwargs: None)


@pytest.fixture()
def db() -> Generator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _create_task(db: Session, status: TaskStatus = TaskStatus.QUEUED) -> uuid.UUID:
    user = User(email=f"{uuid.uuid4()}@example.com")
    db.add(user)
    db.flush()
    project = Project(
        user_id=user.id,
        title="Worker Cat",
        category=ProjectCategory.PET.value,
        status=ProjectStatus.ACTIVE.value,
    )
    db.add(project)
    db.flush()
    task = GenerationTask(
        project_id=project.id,
        status=status.value,
        stage=TaskStage.UPLOAD_VALIDATION.value,
        progress=0,
    )
    db.add(task)
    db.commit()
    return task.id


def test_mock_pipeline_advances_task_to_completed(db: Session, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="papercraft.worker")
    task_id = _create_task(db)

    task = run_generation_pipeline(db, task_id)

    assert task.status == TaskStatus.COMPLETED.value
    assert task.stage == TaskStage.COMPLETED.value
    assert task.progress == 100
    assert task.started_at is not None
    assert task.finished_at is not None

    events = db.scalars(select(TaskEvent).where(TaskEvent.task_id == task_id)).all()
    assert any(event.event_type == TaskEventType.STAGE_STARTED.value for event in events)
    assert any(event.event_type == TaskEventType.PROGRESS_UPDATED.value for event in events)
    assert events[-1].event_type == TaskEventType.COMPLETED.value
    assert f"task_id={task_id}" in caplog.text

    artifacts = db.scalars(select(Artifact).where(Artifact.task_id == task_id)).all()
    assert {artifact.kind for artifact in artifacts} == {
        ArtifactKind.PREVIEW_MODEL.value,
        ArtifactKind.NET_JSON.value,
        ArtifactKind.EXPORT_PDF.value,
    }
    assert all(artifact.artifact_metadata["mock"] for artifact in artifacts)
    assert all(str(task_id) in artifact.storage_key for artifact in artifacts)

    assembly = db.scalar(select(AssemblyMetadata).where(AssemblyMetadata.task_id == task_id))
    assert assembly is not None
    assert assembly.page_count == 3
    assert assembly.part_count == 12
    assert assembly.difficulty_score == 3
    assert assembly.assembly_metadata["pair_numbering"]


def test_pipeline_failure_writes_readable_error(db: Session) -> None:
    class FailingExecutor(MockStageExecutor):
        def execute(self, task: GenerationTask, stage: TaskStage) -> StageResult:
            raise TaskExecutionError(ErrorCode.UNFOLD_FAILED, "mock unfold failed")

    task_id = _create_task(db)

    task = run_generation_pipeline(db, task_id, executor=FailingExecutor())

    assert task.status == TaskStatus.FAILED.value
    assert task.error_code == ErrorCode.UNFOLD_FAILED.value
    assert task.error_message == "mock unfold failed"
    failed_event = db.scalar(
        select(TaskEvent).where(TaskEvent.task_id == task_id, TaskEvent.event_type == TaskEventType.FAILED.value)
    )
    assert failed_event is not None
    assert failed_event.event_metadata["error_code"] == ErrorCode.UNFOLD_FAILED.value


def test_mock_failure_stage_from_task_event_fails_once_then_retry_succeeds(db: Session) -> None:
    task_id = _create_task(db)
    task = db.get(GenerationTask, task_id)
    assert task is not None
    db.add(
        TaskEvent(
            task_id=task.id,
            stage=TaskStage.UPLOAD_VALIDATION.value,
            event_type=TaskEventType.QUEUED.value,
            message="Task queued with mock failure.",
            event_metadata={"mock_failure_stage": TaskStage.UNFOLDING.value},
        )
    )
    db.commit()

    failed_task = run_generation_pipeline(db, task_id)

    assert failed_task.status == TaskStatus.FAILED.value
    assert failed_task.stage == TaskStage.UNFOLDING.value
    assert failed_task.error_code == ErrorCode.UNFOLD_FAILED.value

    assert request_retry_from_stage(db, task_id, TaskStage.UNFOLDING)
    completed_task = run_generation_pipeline(db, task_id)

    assert completed_task.status == TaskStatus.COMPLETED.value
    assert completed_task.progress == 100


def test_cancel_and_retry_hooks_update_task_state(db: Session) -> None:
    task_id = _create_task(db)

    assert cancel_generation_task(db, task_id)
    canceled_task = db.get(GenerationTask, task_id)
    assert canceled_task is not None
    assert canceled_task.status == TaskStatus.CANCELED.value

    assert request_retry_from_stage(db, task_id, TaskStage.DECIMATING)
    retried_task = db.get(GenerationTask, task_id)
    assert retried_task is not None
    assert retried_task.status == TaskStatus.QUEUED.value
    assert retried_task.retry_from_stage == TaskStage.DECIMATING.value


def test_retry_hook_rejects_non_execution_stage(db: Session) -> None:
    task_id = _create_task(db, status=TaskStatus.FAILED)

    assert not request_retry_from_stage(db, task_id, TaskStage.COMPLETED)
