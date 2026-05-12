from collections.abc import Generator
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db.base import Base
from app.db import models  # noqa: F401
from app.main import create_app


@pytest.fixture()
def dispatched_task_ids(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    task_ids: list[str] = []

    def record_enqueue(task_id) -> None:
        task_ids.append(str(task_id))

    monkeypatch.setattr("app.api.routes.projects.enqueue_generation_task", record_enqueue)
    monkeypatch.setattr("app.api.routes.projects.put_upload_bytes", lambda *_args, **_kwargs: None)
    return task_ids


@pytest.fixture()
def client(dispatched_task_ids: list[str]) -> Generator[TestClient]:
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
        yield test_client


def _png_upload(name: str = "cat.png") -> tuple[str, BytesIO, str]:
    image_file = BytesIO()
    Image.new("RGB", (32, 24), color=(120, 80, 40)).save(image_file, format="PNG")
    image_file.seek(0)
    return (name, image_file, "image/png")


def _create_project(client: TestClient) -> str:
    response = client.post("/api/projects", json={"title": "Paper Cat", "category": "pet"})
    assert response.status_code == 201
    return response.json()["project_id"]


def test_project_upload_task_happy_path(client: TestClient, dispatched_task_ids: list[str]) -> None:
    project_id = _create_project(client)

    project_response = client.get(f"/api/projects/{project_id}")
    assert project_response.status_code == 200
    assert project_response.json()["title"] == "Paper Cat"
    assert project_response.json()["image_count"] == 0

    upload_response = client.post(
        f"/api/projects/{project_id}/images",
        files={"file": _png_upload("Cat Photo.PNG")},
    )
    assert upload_response.status_code == 201
    upload_payload = upload_response.json()
    assert upload_payload["mime_type"] == "image/png"
    assert upload_payload["width"] == 32
    assert upload_payload["height"] == 24
    assert upload_payload["sort_order"] == 0
    assert upload_payload["storage_key"].endswith("/cat-photo.png")

    task_response = client.post(
        f"/api/projects/{project_id}/tasks",
        json={
            "complexity_level": "balanced",
            "target_poly_count": 300,
            "paper_size": "a4",
            "texture_mode": "print_friendly",
            "flap_size": 5,
            "max_pages": 12,
            "build_difficulty_mode": "standard",
        },
    )
    assert task_response.status_code == 201
    task_payload = task_response.json()
    assert task_payload["initial_status"] == "queued"
    assert task_payload["stage"] == "upload_validation"
    assert task_payload["progress"] == 0
    assert dispatched_task_ids == [task_payload["task_id"]]

    status_response = client.get(f"/api/tasks/{task_payload['task_id']}")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "queued"
    assert status_payload["stage"] == "upload_validation"
    assert status_payload["error_code"] is None
    assert status_payload["artifacts"] == []
    assert status_payload["assembly_metadata"] is None

    list_response = client.get("/api/projects")
    assert list_response.status_code == 200
    assert list_response.json()["projects"][0]["latest_task_id"] == task_payload["task_id"]
    assert list_response.json()["projects"][0]["image_count"] == 1
    assert list_response.json()["projects"][0]["task_count"] == 1

    history_response = client.get(f"/api/projects/{project_id}/tasks")
    assert history_response.status_code == 200
    assert history_response.json()["tasks"][0]["task_id"] == task_payload["task_id"]


def test_missing_project_returns_stable_error(client: TestClient) -> None:
    response = client.get("/api/projects/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


def test_upload_rejects_unsupported_type(client: TestClient) -> None:
    project_id = _create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/images",
        files={"file": ("notes.txt", BytesIO(b"not an image"), "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UPLOAD_UNSUPPORTED_TYPE"


def test_upload_rejects_file_too_large(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.routes import projects

    monkeypatch.setattr(projects, "get_settings", lambda: SimpleNamespace(max_upload_images=3, max_upload_mb=0))
    project_id = _create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/images",
        files={"file": _png_upload("large.png")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UPLOAD_FILE_TOO_LARGE"


def test_upload_rejects_invalid_image_bytes(client: TestClient) -> None:
    project_id = _create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/images",
        files={"file": ("broken.png", BytesIO(b"not an image"), "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UPLOAD_IMAGE_INVALID"


def test_request_validation_uses_stable_error_shape(client: TestClient) -> None:
    response = client.post("/api/projects", json={"title": "", "category": "pet"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"


def test_upload_rejects_too_many_images(client: TestClient) -> None:
    project_id = _create_project(client)

    for index in range(3):
        response = client.post(
            f"/api/projects/{project_id}/images",
            files={"file": _png_upload(f"cat-{index}.png")},
        )
        assert response.status_code == 201

    response = client.post(
        f"/api/projects/{project_id}/images",
        files={"file": _png_upload("extra.png")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UPLOAD_TOO_MANY_IMAGES"


def test_task_not_found_returns_stable_error(client: TestClient) -> None:
    response = client.get("/api/tasks/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TASK_NOT_FOUND"


def test_create_task_accepts_mock_failure_stage(client: TestClient, dispatched_task_ids: list[str]) -> None:
    project_id = _create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/tasks",
        json={
            "complexity_level": "balanced",
            "target_poly_count": 300,
            "paper_size": "a4",
            "texture_mode": "print_friendly",
            "flap_size": 5,
            "max_pages": 12,
            "build_difficulty_mode": "standard",
            "mock_failure_stage": "unfolding",
        },
    )

    assert response.status_code == 201
    assert dispatched_task_ids == [response.json()["task_id"]]


def test_create_task_rejects_non_execution_mock_failure_stage(client: TestClient) -> None:
    project_id = _create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/tasks",
        json={
            "complexity_level": "balanced",
            "target_poly_count": 300,
            "paper_size": "a4",
            "texture_mode": "print_friendly",
            "flap_size": 5,
            "max_pages": 12,
            "build_difficulty_mode": "standard",
            "mock_failure_stage": "completed",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"
