import json
import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.errors import ApiError
from app.db.models import Artifact
from app.domain.enums import ArtifactKind, ErrorCode

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
    if artifact.artifact_metadata.get("mock") is not True:
        raise ApiError(
            ErrorCode.STORAGE_READ_FAILED,
            "Artifact content is not available from local mock storage.",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            details={"artifact_id": str(artifact_id), "storage_key": artifact.storage_key},
        )

    return Response(
        content=_mock_artifact_content(artifact),
        media_type=artifact.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{_download_filename(artifact)}"'},
    )


def _mock_artifact_content(artifact: Artifact) -> bytes:
    if artifact.kind == ArtifactKind.NET_JSON.value:
        return json.dumps(
            {
                "mock": True,
                "artifact_id": str(artifact.id),
                "pages": [
                    {
                        "page": 1,
                        "paper_size": "a4",
                        "parts": [
                            {"id": "body-1", "label": "Body 1", "fold_lines": 4, "glue_flaps": 3},
                            {"id": "head-1", "label": "Head 1", "fold_lines": 3, "glue_flaps": 2},
                        ],
                    }
                ],
            },
            separators=(",", ":"),
        ).encode()
    if artifact.kind == ArtifactKind.EXPORT_PDF.value:
        return (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Count 1 /Kids [3 0 R] >> endobj\n"
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >> endobj\n"
            b"trailer << /Root 1 0 R >>\n%%EOF\n"
        )
    if artifact.kind == ArtifactKind.PREVIEW_MODEL.value:
        return b"glTF mock preview model placeholder\n"
    return f"mock artifact {artifact.id}\n".encode()


def _download_filename(artifact: Artifact) -> str:
    return artifact.storage_key.rstrip("/").split("/")[-1] or f"{artifact.id}"
