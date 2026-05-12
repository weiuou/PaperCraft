import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.errors import ApiError
from app.db.models import Artifact
from app.domain.enums import ErrorCode
from app.services.mock_artifacts import mock_artifact_content
from app.services.object_storage import ObjectStorageError, get_artifact_bytes

router = APIRouter(tags=["artifacts"])


def _get_artifact_or_404(db: Session, artifact_id: uuid.UUID) -> Artifact:
    artifact = db.get(Artifact, artifact_id)
    if artifact is None:
        raise ApiError(
            ErrorCode.ARTIFACT_NOT_FOUND,
            "Artifact was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"artifact_id": str(artifact_id)},
        )
    return artifact


@router.get("/artifacts/{artifact_id}/download")
def download_artifact(artifact_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    artifact = _get_artifact_or_404(db, artifact_id)
    try:
        content = get_artifact_bytes(artifact.storage_key)
    except ObjectStorageError as exc:
        if artifact.artifact_metadata.get("mock") is not True:
            raise ApiError(
                exc.code,
                exc.message,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                details={"artifact_id": str(artifact_id), "storage_key": artifact.storage_key},
            ) from exc
        content = mock_artifact_content(artifact.id, artifact.kind)

    return Response(
        content=content,
        media_type=artifact.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{_download_filename(artifact)}"'},
    )


def _download_filename(artifact: Artifact) -> str:
    return artifact.storage_key.rstrip("/").split("/")[-1] or f"{artifact.id}"
