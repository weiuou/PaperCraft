import json

import pytest

from app.domain.enums import ArtifactKind
from app.services.exporting import ExportFailed, export_papercraft_pdf


def _net_json() -> bytes:
    return json.dumps(
        {
            "mock": False,
            "schema": "papercraft.net.v1",
            "metadata": {
                "real_stage": "unfolding",
                "page_count": 1,
                "part_count": 2,
                "fold_line_count": 6,
                "glue_flap_count": 1,
            },
            "pages": [
                {
                    "page": 1,
                    "paper_size": "a4",
                    "parts": [
                        {
                            "id": "face-1",
                            "label": "Part 1",
                            "width": 40,
                            "height": 32,
                            "x": 10,
                            "y": 16,
                            "fold_lines": 3,
                            "glue_flaps": 0,
                            "pair_number": 1,
                        },
                        {
                            "id": "face-2",
                            "label": "Part 2",
                            "width": 42,
                            "height": 30,
                            "x": 60,
                            "y": 16,
                            "fold_lines": 3,
                            "glue_flaps": 1,
                            "flap_size": 5,
                            "pair_number": 2,
                        },
                    ],
                }
            ],
        },
        separators=(",", ":"),
    ).encode()


def test_export_papercraft_pdf_generates_pdf_and_assembly_metadata() -> None:
    result = export_papercraft_pdf(
        net_json_content=_net_json(),
        net_json_metadata={"real_stage": "unfolding"},
        net_svg_content=b"<svg></svg>",
        net_svg_metadata={"real_stage": "unfolding"},
        paper_size="a4",
        build_difficulty_mode="standard",
    )

    assert result.artifact.kind == ArtifactKind.EXPORT_PDF
    assert result.artifact.mime_type == "application/pdf"
    assert result.artifact.content.startswith(b"%PDF-1.4")
    assert b"AI PaperCraft Studio Assembly Guide" in result.artifact.content
    assert result.artifact.metadata["mock"] is False
    assert result.artifact.metadata["real_stage"] == "exporting"
    assert result.artifact.metadata["instruction_sheet"]
    assert result.artifact.metadata["page_count"] == 2
    assert result.assembly.page_count == 2
    assert result.assembly.part_count == 2
    assert 1 <= result.assembly.difficulty_score <= 10
    assert result.assembly.metadata["pair_numbering"]


def test_export_papercraft_pdf_rejects_empty_net() -> None:
    with pytest.raises(ExportFailed):
        export_papercraft_pdf(
            net_json_content=b'{"pages":[]}',
            net_json_metadata={},
            net_svg_content=b"",
            net_svg_metadata={},
            paper_size="a4",
            build_difficulty_mode="standard",
        )
