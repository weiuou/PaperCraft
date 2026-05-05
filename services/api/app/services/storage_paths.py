import re
import uuid
from enum import StrEnum


class StorageBucketRole(StrEnum):
    UPLOADS = "uploads"
    ARTIFACTS = "artifacts"


class ArtifactPathGroup(StrEnum):
    PREPROCESS = "preprocess"
    MESHES = "meshes"
    NETS = "nets"
    PREVIEWS = "previews"
    EXPORTS = "exports"


_SAFE_FILENAME_PATTERN = re.compile(r"[^a-zA-Z0-9._-]+")


def sanitize_filename(filename: str) -> str:
    trimmed = filename.strip().replace("\\", "/").split("/")[-1]
    safe = _SAFE_FILENAME_PATTERN.sub("-", trimmed).strip(".-").lower()
    safe = safe.replace("-.", ".")
    return safe or "file"


def source_image_key(project_id: uuid.UUID, image_id: uuid.UUID, filename: str) -> str:
    safe_filename = sanitize_filename(filename)
    return f"projects/{project_id}/source-images/{image_id}/{safe_filename}"


def task_artifact_key(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    group: ArtifactPathGroup,
    artifact_id: uuid.UUID,
    filename: str,
) -> str:
    safe_filename = sanitize_filename(filename)
    return f"projects/{project_id}/tasks/{task_id}/{group.value}/{artifact_id}/{safe_filename}"
