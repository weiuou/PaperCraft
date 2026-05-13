import json
import math
import time
from dataclasses import dataclass
from typing import Any

from app.domain.enums import ArtifactKind


class ExportFailed(Exception):
    pass


@dataclass(frozen=True)
class ExportArtifactPayload:
    kind: ArtifactKind
    filename: str
    mime_type: str
    content: bytes
    metadata: dict[str, object]


@dataclass(frozen=True)
class AssemblyMetadataPayload:
    page_count: int
    part_count: int
    difficulty_score: int
    estimated_build_minutes: int
    metadata: dict[str, object]


@dataclass(frozen=True)
class ExportResult:
    artifact: ExportArtifactPayload
    assembly: AssemblyMetadataPayload
    metadata: dict[str, object]


def export_papercraft_pdf(
    *,
    net_json_content: bytes,
    net_json_metadata: dict[str, object],
    net_svg_content: bytes,
    net_svg_metadata: dict[str, object],
    paper_size: str,
    build_difficulty_mode: str,
) -> ExportResult:
    started_at = time.perf_counter()
    net = _parse_net_json(net_json_content)
    pages = _validated_pages(net)
    net_page_count = len(pages)
    part_count = sum(len(page["parts"]) for page in pages)
    if part_count <= 0:
        raise ExportFailed("Paper net has no parts to export.")

    fold_line_count = _metadata_int(net.get("metadata"), "fold_line_count", _sum_part_field(pages, "fold_lines"))
    glue_flap_count = _metadata_int(net.get("metadata"), "glue_flap_count", _sum_part_field(pages, "glue_flaps"))
    difficulty_score = _difficulty_score(
        part_count=part_count,
        page_count=net_page_count,
        glue_flap_count=glue_flap_count,
        build_difficulty_mode=build_difficulty_mode,
    )
    estimated_build_minutes = _estimated_build_minutes(
        part_count=part_count,
        glue_flap_count=glue_flap_count,
        difficulty_score=difficulty_score,
    )
    pdf_pages = _render_pdf_pages(
        pages=pages,
        requested_paper_size=paper_size,
        part_count=part_count,
        fold_line_count=fold_line_count,
        glue_flap_count=glue_flap_count,
        difficulty_score=difficulty_score,
        estimated_build_minutes=estimated_build_minutes,
    )
    pdf_content = _build_pdf(pdf_pages)
    metadata = {
        "mock": False,
        "real_stage": "exporting",
        "source_stage": net_json_metadata.get("real_stage"),
        "svg_source_stage": net_svg_metadata.get("real_stage"),
        "paper_size": paper_size,
        "page_count": len(pdf_pages),
        "net_page_count": net_page_count,
        "part_count": part_count,
        "fold_line_count": fold_line_count,
        "glue_flap_count": glue_flap_count,
        "pair_numbering": True,
        "instruction_sheet": True,
        "net_svg_bytes": len(net_svg_content),
        "processing_duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
    }
    assembly_metadata = {
        **metadata,
        "build_difficulty_mode": build_difficulty_mode,
        "estimated_build_minutes": estimated_build_minutes,
        "build_notes": [
            "Print at 100% scale on the selected paper size.",
            "Cut solid outlines before scoring fold lines.",
            "Match pair numbers before gluing flaps.",
        ],
    }
    return ExportResult(
        artifact=ExportArtifactPayload(
            kind=ArtifactKind.EXPORT_PDF,
            filename="papercraft-export.pdf",
            mime_type="application/pdf",
            content=pdf_content,
            metadata={**metadata, "artifact_role": "export_pdf"},
        ),
        assembly=AssemblyMetadataPayload(
            page_count=len(pdf_pages),
            part_count=part_count,
            difficulty_score=difficulty_score,
            estimated_build_minutes=estimated_build_minutes,
            metadata=assembly_metadata,
        ),
        metadata=metadata,
    )


def _parse_net_json(content: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExportFailed("Net JSON artifact is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ExportFailed("Net JSON root must be an object.")
    return payload


def _validated_pages(net: dict[str, Any]) -> list[dict[str, Any]]:
    pages = net.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ExportFailed("Net JSON must include at least one page.")
    validated: list[dict[str, Any]] = []
    for index, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            raise ExportFailed(f"Net page {index} is invalid.")
        parts = page.get("parts")
        if not isinstance(parts, list) or not parts:
            raise ExportFailed(f"Net page {index} must include parts.")
        validated.append(page)
    return validated


def _metadata_int(metadata: object, key: str, fallback: int) -> int:
    if isinstance(metadata, dict):
        value = metadata.get(key)
        if isinstance(value, int):
            return value
    return fallback


def _sum_part_field(pages: list[dict[str, Any]], field: str) -> int:
    total = 0
    for page in pages:
        for part in page["parts"]:
            if isinstance(part, dict) and isinstance(part.get(field), int):
                total += int(part[field])
    return total


def _difficulty_score(
    *,
    part_count: int,
    page_count: int,
    glue_flap_count: int,
    build_difficulty_mode: str,
) -> int:
    mode_adjustment = {"easy": -1, "standard": 0, "advanced": 1}.get(build_difficulty_mode, 0)
    raw = 1 + math.ceil(part_count / 8) + math.ceil(page_count / 3) + math.ceil(glue_flap_count / 20) + mode_adjustment
    return max(1, min(10, raw))


def _estimated_build_minutes(*, part_count: int, glue_flap_count: int, difficulty_score: int) -> int:
    return max(15, part_count * 4 + glue_flap_count * 2 + difficulty_score * 5)


def _render_pdf_pages(
    *,
    pages: list[dict[str, Any]],
    requested_paper_size: str,
    part_count: int,
    fold_line_count: int,
    glue_flap_count: int,
    difficulty_score: int,
    estimated_build_minutes: int,
) -> list[dict[str, object]]:
    rendered: list[dict[str, object]] = []
    instruction_paper = _paper_dimensions(requested_paper_size)
    rendered.append(
        {
            "width": instruction_paper["width_pt"],
            "height": instruction_paper["height_pt"],
            "content": _instruction_page_content(
                paper=instruction_paper,
                part_count=part_count,
                fold_line_count=fold_line_count,
                glue_flap_count=glue_flap_count,
                difficulty_score=difficulty_score,
                estimated_build_minutes=estimated_build_minutes,
            ),
        }
    )
    for page in pages:
        paper = _paper_dimensions(str(page.get("paper_size") or requested_paper_size))
        rendered.append(
            {
                "width": paper["width_pt"],
                "height": paper["height_pt"],
                "content": _net_page_content(page=page, paper=paper),
            }
        )
    return rendered


def _paper_dimensions(paper_size: str) -> dict[str, float]:
    if paper_size == "a3":
        width_mm, height_mm, margin_mm = 297.0, 420.0, 14.0
    elif paper_size == "a4":
        width_mm, height_mm, margin_mm = 210.0, 297.0, 10.0
    else:
        raise ExportFailed(f"Unsupported paper size: {paper_size}")
    return {
        "width_mm": width_mm,
        "height_mm": height_mm,
        "margin_mm": margin_mm,
        "width_pt": _mm_to_pt(width_mm),
        "height_pt": _mm_to_pt(height_mm),
    }


def _instruction_page_content(
    *,
    paper: dict[str, float],
    part_count: int,
    fold_line_count: int,
    glue_flap_count: int,
    difficulty_score: int,
    estimated_build_minutes: int,
) -> bytes:
    height = paper["height_pt"]
    margin = _mm_to_pt(paper["margin_mm"])
    lines = [
        "AI PaperCraft Studio Assembly Guide",
        f"Parts: {part_count}",
        f"Fold lines: {fold_line_count}",
        f"Glue flaps: {glue_flap_count}",
        f"Difficulty: {difficulty_score}/10",
        f"Estimated build time: {estimated_build_minutes} minutes",
        "1. Print every page at 100% scale.",
        "2. Cut solid outlines first.",
        "3. Score dashed fold lines before bending.",
        "4. Match pair numbers, then glue the matching flaps.",
    ]
    commands = [_text(margin, height - margin, 18, lines[0])]
    y = height - margin - 34
    for line in lines[1:]:
        commands.append(_text(margin, y, 11, line))
        y -= 18
    commands.append(_rect(margin, margin, paper["width_pt"] - margin * 2, paper["height_pt"] - margin * 2))
    return "\n".join(commands).encode("ascii")


def _net_page_content(*, page: dict[str, Any], paper: dict[str, float]) -> bytes:
    height = paper["height_pt"]
    margin = _mm_to_pt(paper["margin_mm"])
    commands = [
        _rect(margin / 2, margin / 2, paper["width_pt"] - margin, paper["height_pt"] - margin),
        _text(margin, height - margin / 1.5, 10, f"Net page {page.get('page', '?')}")
    ]
    for part in page["parts"]:
        if not isinstance(part, dict):
            continue
        x = _mm_to_pt(_number(part.get("x"), paper["margin_mm"]))
        y_top = _mm_to_pt(_number(part.get("y"), paper["margin_mm"] + 10))
        width = _mm_to_pt(_number(part.get("width"), 20))
        part_height = _mm_to_pt(_number(part.get("height"), 20))
        y = height - y_top - part_height
        label = str(part.get("label") or part.get("id") or "Part")
        pair_number = str(part.get("pair_number") or "?")

        commands.append(_rect(x, y, width, part_height))
        commands.append(_dashed_line(x, y + part_height / 2, x + width, y + part_height / 2))
        if int(part.get("glue_flaps") or 0) > 0:
            flap_height = min(_mm_to_pt(_number(part.get("flap_size"), 5)), part_height / 3)
            commands.append(_gray_rect(x, y - flap_height, width, flap_height))
            commands.append(_text(x + 3, y - flap_height + 3, 6, f"glue {pair_number}"))
        commands.append(_text(x + 3, y + part_height - 10, 7, label[:40]))
        commands.append(_text(x + width - 18, y + 4, 7, f"#{pair_number}"))
    return "\n".join(commands).encode("ascii")


def _number(value: object, fallback: float) -> float:
    if isinstance(value, int | float):
        return float(value)
    return fallback


def _mm_to_pt(value: float) -> float:
    return value * 72.0 / 25.4


def _rect(x: float, y: float, width: float, height: float) -> str:
    return f"[] 0 d 0 G {x:.2f} {y:.2f} {width:.2f} {height:.2f} re S"


def _gray_rect(x: float, y: float, width: float, height: float) -> str:
    return f"0.93 g {x:.2f} {y:.2f} {width:.2f} {height:.2f} re f 0 G"


def _dashed_line(x1: float, y1: float, x2: float, y2: float) -> str:
    return f"[4 3] 0 d 0.1 0.32 0.74 RG {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S 0 G [] 0 d"


def _text(x: float, y: float, size: int, value: str) -> str:
    return f"BT /F1 {size} Tf {x:.2f} {y:.2f} Td ({_escape_pdf_text(value)}) Tj ET"


def _escape_pdf_text(value: str) -> str:
    safe = value.encode("ascii", errors="replace").decode("ascii")
    return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf(pages: list[dict[str, object]]) -> bytes:
    if not pages:
        raise ExportFailed("PDF requires at least one page.")

    page_object_ids = [3 + index * 2 for index in range(len(pages))]
    content_object_ids = [page_id + 1 for page_id in page_object_ids]
    font_object_id = 3 + len(pages) * 2

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Count {len(pages)} /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_object_ids)}] >>".encode(
            "ascii"
        ),
    ]
    for page, page_id, content_id in zip(pages, page_object_ids, content_object_ids, strict=True):
        width = float(page["width"])
        height = float(page["height"])
        content = page["content"]
        if not isinstance(content, bytes):
            raise ExportFailed("PDF page content must be bytes.")
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width:.2f} {height:.2f}] "
                f"/Resources << /Font << /F1 {font_object_id} 0 R >> >> /Contents {content_id} 0 R >>"
            ).encode("ascii")
        )
        objects.append(b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_number} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)
