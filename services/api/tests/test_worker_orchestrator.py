import uuid
import logging
from collections.abc import Generator
from io import BytesIO

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db import models  # noqa: F401
from app.db.models import Artifact, AssemblyMetadata, GenerationTask, ParamConfig, Project, SourceImage, TaskEvent, User
from app.domain.enums import ArtifactKind, ErrorCode, ProjectCategory, ProjectStatus, TaskEventType, TaskStage, TaskStatus
from app.services.exporting import ExportFailed
from app.worker.orchestrator import (
    cancel_generation_task,
    request_retry_from_stage,
    run_generation_pipeline,
)


@pytest.fixture(autouse=True)
def mock_object_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    stored_artifacts: dict[str, bytes] = {}
    monkeypatch.setattr(
        "app.worker.orchestrator.put_artifact_bytes",
        lambda key, content, _content_type: stored_artifacts.update({key: content}),
    )
    monkeypatch.setattr("app.worker.orchestrator.get_artifact_bytes", lambda key: stored_artifacts[key])
    monkeypatch.setattr("app.worker.orchestrator.get_upload_bytes", lambda _key: _source_png_bytes())


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
    source_bytes = _source_png_bytes()
    db.add(
        SourceImage(
            project_id=project.id,
            storage_key=f"projects/{project.id}/source-images/{uuid.uuid4()}/cat.png",
            mime_type="image/png",
            width=80,
            height=60,
            file_size=len(source_bytes),
            sort_order=0,
        )
    )
    db.flush()
    task = GenerationTask(
        project_id=project.id,
        status=status.value,
        stage=TaskStage.UPLOAD_VALIDATION.value,
        progress=0,
    )
    db.add(task)
    db.flush()
    db.add(
        ParamConfig(
            task_id=task.id,
            category=ProjectCategory.PET.value,
            complexity_level="balanced",
            target_poly_count=300,
            paper_size="a4",
            texture_mode="print_friendly",
            flap_size=5,
            max_pages=12,
            build_difficulty_mode="standard",
        )
    )
    db.commit()
    return task.id


def _source_png_bytes() -> bytes:
    image = Image.new("RGB", (80, 60), color=(245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.rectangle((22, 12, 56, 48), fill=(190, 72, 52))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _blank_png_bytes() -> bytes:
    image = Image.new("RGB", (80, 60), color=(245, 245, 245))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_pipeline_advances_task_to_completed_with_real_export(db: Session, caplog: pytest.LogCaptureFixture) -> None:
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
        ArtifactKind.PREPROCESS_MASK.value,
        ArtifactKind.PREPROCESS_CROP.value,
        ArtifactKind.BASE_MESH.value,
        ArtifactKind.REPAIRED_MESH.value,
        ArtifactKind.LOW_POLY_MESH.value,
        ArtifactKind.PREVIEW_MODEL.value,
        ArtifactKind.NET_JSON.value,
        ArtifactKind.NET_SVG.value,
        ArtifactKind.EXPORT_PDF.value,
    }
    preprocessing_artifacts = [
        artifact for artifact in artifacts if artifact.kind in {ArtifactKind.PREPROCESS_MASK.value, ArtifactKind.PREPROCESS_CROP.value}
    ]
    assert all(artifact.artifact_metadata["real_stage"] == "preprocessing" for artifact in preprocessing_artifacts)
    base_mesh = next(artifact for artifact in artifacts if artifact.kind == ArtifactKind.BASE_MESH.value)
    assert base_mesh.artifact_metadata["real_stage"] == "model_generating"
    assert base_mesh.artifact_metadata["mesh_strategy"] == "pet_body_head"
    repaired_mesh = next(artifact for artifact in artifacts if artifact.kind == ArtifactKind.REPAIRED_MESH.value)
    assert repaired_mesh.artifact_metadata["real_stage"] == "paperability_optimizing"
    low_poly_mesh = next(artifact for artifact in artifacts if artifact.kind == ArtifactKind.LOW_POLY_MESH.value)
    assert low_poly_mesh.artifact_metadata["real_stage"] == "decimating"
    net_json = next(artifact for artifact in artifacts if artifact.kind == ArtifactKind.NET_JSON.value)
    assert net_json.artifact_metadata["real_stage"] == "unfolding"
    net_svg = next(artifact for artifact in artifacts if artifact.kind == ArtifactKind.NET_SVG.value)
    assert net_svg.artifact_metadata["real_stage"] == "unfolding"
    export_pdf = next(artifact for artifact in artifacts if artifact.kind == ArtifactKind.EXPORT_PDF.value)
    assert export_pdf.artifact_metadata["mock"] is False
    assert export_pdf.artifact_metadata["real_stage"] == "exporting"
    assert export_pdf.artifact_metadata["instruction_sheet"]
    assert all(str(task_id) in artifact.storage_key for artifact in artifacts)

    assembly = db.scalar(select(AssemblyMetadata).where(AssemblyMetadata.task_id == task_id))
    assert assembly is not None
    assert assembly.page_count == export_pdf.artifact_metadata["page_count"]
    assert assembly.part_count == export_pdf.artifact_metadata["part_count"]
    assert 1 <= assembly.difficulty_score <= 10
    assert assembly.assembly_metadata["mock"] is False
    assert assembly.assembly_metadata["instruction_sheet"]
    assert assembly.assembly_metadata["pair_numbering"]


def test_preprocessing_subject_not_found_fails_task(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.worker.orchestrator.get_upload_bytes", lambda _key: _blank_png_bytes())
    task_id = _create_task(db)

    task = run_generation_pipeline(db, task_id)

    assert task.status == TaskStatus.FAILED.value
    assert task.stage == TaskStage.PREPROCESSING.value
    assert task.error_code == ErrorCode.PREPROCESS_SUBJECT_NOT_FOUND.value
    failed_event = db.scalar(
        select(TaskEvent).where(TaskEvent.task_id == task_id, TaskEvent.event_type == TaskEventType.FAILED.value)
    )
    assert failed_event is not None
    assert failed_event.event_metadata["error_code"] == ErrorCode.PREPROCESS_SUBJECT_NOT_FOUND.value


def test_pipeline_failure_writes_readable_error(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_export(**_kwargs) -> None:
        raise ExportFailed("pdf export failed")

    monkeypatch.setattr("app.worker.orchestrator.export_papercraft_pdf", fail_export)
    task_id = _create_task(db)

    task = run_generation_pipeline(db, task_id)

    assert task.status == TaskStatus.FAILED.value
    assert task.stage == TaskStage.EXPORTING.value
    assert task.error_code == ErrorCode.EXPORT_FAILED.value
    assert task.error_message == "pdf export failed"
    failed_event = db.scalar(
        select(TaskEvent).where(TaskEvent.task_id == task_id, TaskEvent.event_type == TaskEventType.FAILED.value)
    )
    assert failed_event is not None
    assert failed_event.event_metadata["error_code"] == ErrorCode.EXPORT_FAILED.value


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
