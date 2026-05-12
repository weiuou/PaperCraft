import json
import uuid

from app.domain.enums import ArtifactKind


def mock_artifact_content(artifact_id: uuid.UUID, kind: str) -> bytes:
    if kind == ArtifactKind.NET_JSON.value:
        return json.dumps(
            {
                "mock": True,
                "artifact_id": str(artifact_id),
                "pages": [
                    {
                        "page": 1,
                        "paper_size": "a4",
                        "parts": [
                            {"id": "body-1", "label": "Body 1", "fold_lines": 4, "glue_flaps": 3},
                            {"id": "head-1", "label": "Head 1", "fold_lines": 3, "glue_flaps": 2},
                        ],
                    },
                    {
                        "page": 2,
                        "paper_size": "a4",
                        "parts": [
                            {"id": "left-side", "label": "Left side", "fold_lines": 5, "glue_flaps": 4},
                            {"id": "right-side", "label": "Right side", "fold_lines": 5, "glue_flaps": 4},
                        ],
                    },
                    {
                        "page": 3,
                        "paper_size": "a4",
                        "parts": [
                            {"id": "base-1", "label": "Base", "fold_lines": 6, "glue_flaps": 5},
                            {"id": "tail-1", "label": "Tail", "fold_lines": 3, "glue_flaps": 2},
                        ],
                    },
                ],
            },
            separators=(",", ":"),
        ).encode()
    if kind == ArtifactKind.EXPORT_PDF.value:
        return (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Count 1 /Kids [3 0 R] >> endobj\n"
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >> endobj\n"
            b"trailer << /Root 1 0 R >>\n%%EOF\n"
        )
    if kind == ArtifactKind.PREVIEW_MODEL.value:
        return b"glTF mock preview model placeholder\n"
    return f"mock artifact {artifact_id}\n".encode()
