import uuid

from app.services.storage_paths import (
    ArtifactPathGroup,
    sanitize_filename,
    source_image_key,
    task_artifact_key,
)


def test_sanitize_filename_keeps_safe_ascii_name() -> None:
    assert sanitize_filename(" Preview Image.PNG ") == "preview-image.png"


def test_sanitize_filename_removes_directory_segments() -> None:
    assert sanitize_filename("../unsafe/My File!.png") == "my-file.png"


def test_source_image_key_uses_project_and_image_ids() -> None:
    project_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    image_id = uuid.UUID("00000000-0000-0000-0000-000000000002")

    key = source_image_key(project_id, image_id, "Cat Photo.PNG")

    assert key == (
        "projects/00000000-0000-0000-0000-000000000001/"
        "source-images/00000000-0000-0000-0000-000000000002/cat-photo.png"
    )


def test_task_artifact_key_uses_group_and_artifact_id() -> None:
    project_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    task_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    artifact_id = uuid.UUID("00000000-0000-0000-0000-000000000003")

    key = task_artifact_key(project_id, task_id, ArtifactPathGroup.EXPORTS, artifact_id, "Result.PDF")

    assert key == (
        "projects/00000000-0000-0000-0000-000000000001/"
        "tasks/00000000-0000-0000-0000-000000000002/"
        "exports/00000000-0000-0000-0000-000000000003/result.pdf"
    )
