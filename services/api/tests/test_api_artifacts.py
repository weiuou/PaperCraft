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
def api_context() -> Generator[tuple[TestClient, sessionmaker[Session]]]:
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
