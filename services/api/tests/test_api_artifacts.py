import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.models import Artifact, GenerationTask, Project, User
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


def _create_completed_mock_task(session_factory: sessionmaker[Session]) -> uuid.UUID:
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
        task = GenerationTask(
            project_id=project.id,
            status=TaskStatus.QUEUED.value,
            stage=TaskStage.UPLOAD_VALIDATION.value,
            progress=0,
        )
        db.add(task)
        db.commit()
        task_id = task.id
        run_generation_pipeline(db, task_id)
        return task_id


def test_task_status_returns_mock_artifacts_and_download_urls(
    api_context: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = api_context
    task_id = _create_completed_mock_task(session_factory)

    response = client.get(f"/api/tasks/{task_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert {artifact["kind"] for artifact in payload["artifacts"]} == {
        ArtifactKind.PREVIEW_MODEL.value,
        ArtifactKind.NET_JSON.value,
        ArtifactKind.EXPORT_PDF.value,
    }
    assert all(artifact["download_url"].startswith("/api/artifacts/") for artifact in payload["artifacts"])
    assert payload["assembly_metadata"]["page_count"] == 3
    assert payload["assembly_metadata"]["metadata"]["pair_numbering"]


def test_mock_pdf_artifact_can_be_downloaded(api_context: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, session_factory = api_context
    task_id = _create_completed_mock_task(session_factory)
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

    retry_response = client.post(f"/api/tasks/{task_id}/retry", json={"stage": TaskStage.PREPROCESSING.value})

    assert retry_response.status_code == 200
    assert retry_response.json()["status"] == TaskStatus.QUEUED.value
    assert enqueued_task_ids == [str(task_id)]
