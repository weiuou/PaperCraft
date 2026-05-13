import uuid
from collections.abc import Generator
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.models import Artifact, GenerationTask, ParamConfig, Project, SourceImage, User
from app.domain.enums import ArtifactKind, ProjectCategory, ProjectStatus, TaskStage, TaskStatus
from app.main import create_app
from app.worker.orchestrator import run_generation_pipeline


@pytest.fixture()
def api_context(monkeypatch: pytest.MonkeyPatch) -> Generator[tuple[TestClient, sessionmaker[Session]]]:
    stored_artifacts: dict[str, bytes] = {}
    monkeypatch.setattr(
        "app.worker.orchestrator.put_artifact_bytes",
        lambda key, content, _content_type: stored_artifacts.update({key: content}),
    )
    monkeypatch.setattr("app.worker.orchestrator.get_artifact_bytes", lambda key: stored_artifacts[key])
    monkeypatch.setattr("app.worker.orchestrator.get_upload_bytes", lambda _key: _source_png_bytes())
    monkeypatch.setattr("app.api.routes.artifacts.get_artifact_bytes", lambda key: stored_artifacts[key])

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, TestingSessionLocal


def _create_completed_task(session_factory: sessionmaker[Session]) -> uuid.UUID:
    with session_factory() as db:
        user = User(email=f"{uuid.uuid4()}@example.com")
        db.add(user)
        db.flush()
        project = Project(
            user_id=user.id,
            title="Mock Demo Cat",
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
            status=TaskStatus.QUEUED.value,
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
        task_id = task.id
        run_generation_pipeline(db, task_id)
        return task_id


def _source_png_bytes() -> bytes:
    image = Image.new("RGB", (80, 60), color=(245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.rectangle((22, 12, 56, 48), fill=(190, 72, 52))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_task_status_returns_real_pipeline_artifacts_and_download_urls(
    api_context: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_context
    task_id = _create_completed_task(session_factory)

    response = client.get(f"/api/tasks/{task_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert isinstance(payload["next_actions"], list)
    assert {artifact["kind"] for artifact in payload["artifacts"]} == {
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
    assert all(artifact["download_url"].startswith("/api/artifacts/") for artifact in payload["artifacts"])
    preprocess_artifacts = [
        artifact
        for artifact in payload["artifacts"]
        if artifact["kind"] in {ArtifactKind.PREPROCESS_MASK.value, ArtifactKind.PREPROCESS_CROP.value}
    ]
    assert all(artifact["metadata"]["real_stage"] == "preprocessing" for artifact in preprocess_artifacts)
    base_mesh = next(artifact for artifact in payload["artifacts"] if artifact["kind"] == ArtifactKind.BASE_MESH.value)
    assert base_mesh["metadata"]["real_stage"] == "model_generating"
    assert base_mesh["download_url"].startswith("/api/artifacts/")
    repaired_mesh = next(artifact for artifact in payload["artifacts"] if artifact["kind"] == ArtifactKind.REPAIRED_MESH.value)
    assert repaired_mesh["metadata"]["real_stage"] == "paperability_optimizing"
    low_poly_mesh = next(artifact for artifact in payload["artifacts"] if artifact["kind"] == ArtifactKind.LOW_POLY_MESH.value)
    assert low_poly_mesh["metadata"]["real_stage"] == "decimating"
    net_json = next(artifact for artifact in payload["artifacts"] if artifact["kind"] == ArtifactKind.NET_JSON.value)
    assert net_json["metadata"]["real_stage"] == "unfolding"
    net_svg = next(artifact for artifact in payload["artifacts"] if artifact["kind"] == ArtifactKind.NET_SVG.value)
    assert net_svg["metadata"]["real_stage"] == "unfolding"
    export_pdf = next(artifact for artifact in payload["artifacts"] if artifact["kind"] == ArtifactKind.EXPORT_PDF.value)
    assert export_pdf["metadata"]["mock"] is False
    assert export_pdf["metadata"]["real_stage"] == "exporting"
    assert export_pdf["metadata"]["instruction_sheet"]
    assert payload["assembly_metadata"]["page_count"] == export_pdf["metadata"]["page_count"]
    assert payload["assembly_metadata"]["part_count"] == export_pdf["metadata"]["part_count"]
    assert payload["assembly_metadata"]["metadata"]["mock"] is False
    assert payload["assembly_metadata"]["metadata"]["pair_numbering"]


def test_real_pdf_artifact_can_be_downloaded(api_context: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, session_factory = api_context
    task_id = _create_completed_task(session_factory)
    with session_factory() as db:
        pdf_artifact = db.scalar(
            select(Artifact).where(Artifact.task_id == task_id, Artifact.kind == ArtifactKind.EXPORT_PDF.value)
        )
        assert pdf_artifact is not None
        artifact_id = pdf_artifact.id

    response = client.get(f"/api/artifacts/{artifact_id}/download")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF-1.4")
    assert b"AI PaperCraft Studio Assembly Guide" in response.content


def test_task_metrics_report_includes_completion_and_stage_duration(
    api_context: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_context
    _create_completed_task(session_factory)

    response = client.get("/api/metrics/tasks")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_tasks"] == 1
    assert payload["summary"]["completed_tasks"] == 1
    assert payload["summary"]["completion_rate"] == 1.0
    assert payload["business_metrics"]["export_rate"] == 1.0
    assert payload["business_metrics"]["average_page_count"] is not None
    assert payload["stage_durations_ms"]["preprocessing"]["count"] == 1
    assert payload["stage_durations_ms"]["exporting"]["avg"] >= 0


def test_missing_artifact_returns_stable_error(api_context: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, _session_factory = api_context

    response = client.get("/api/artifacts/00000000-0000-0000-0000-000000000001/download")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ARTIFACT_NOT_FOUND"


def test_cancel_and_retry_task_endpoints(
    api_context: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session_factory = api_context
    enqueued_task_ids: list[str] = []
    monkeypatch.setattr("app.api.routes.tasks.enqueue_generation_task", lambda task_id: enqueued_task_ids.append(str(task_id)))

    with session_factory() as db:
        user = User(email=f"{uuid.uuid4()}@example.com")
        db.add(user)
        db.flush()
        project = Project(
            user_id=user.id,
            title="Retry Demo Cat",
            category=ProjectCategory.PET.value,
            status=ProjectStatus.ACTIVE.value,
        )
        db.add(project)
        db.flush()
        task = GenerationTask(
            project_id=project.id,
            status=TaskStatus.QUEUED.value,
            stage=TaskStage.UPLOAD_VALIDATION.value,
            progress=0,
        )
        db.add(task)
        db.commit()
        task_id = task.id

    cancel_response = client.post(f"/api/tasks/{task_id}/cancel", json={})

    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == TaskStatus.CANCELED.value
    assert cancel_response.json()["next_actions"] == ["Retry from the selected stage when you are ready to continue."]

    retry_response = client.post(f"/api/tasks/{task_id}/retry", json={"stage": TaskStage.PREPROCESSING.value})

    assert retry_response.status_code == 200
    assert retry_response.json()["status"] == TaskStatus.QUEUED.value
    assert enqueued_task_ids == [str(task_id)]
