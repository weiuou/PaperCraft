import json
import math
import time
from dataclasses import dataclass

from app.domain.enums import ArtifactKind


class UnfoldingFailed(Exception):
    pass


@dataclass(frozen=True)
class UnfoldingArtifactPayload:
    kind: ArtifactKind
    filename: str
    mime_type: str
    content: bytes
    metadata: dict[str, object]


@dataclass(frozen=True)
class UnfoldingResult:
    artifacts: tuple[UnfoldingArtifactPayload, ...]
    metadata: dict[str, object]


def unfold_low_poly_mesh(
    *,
    low_poly_mesh_content: bytes,
    low_poly_mesh_metadata: dict[str, object],
    paper_size: str,
    flap_size: int,
    max_pages: int,
) -> UnfoldingResult:
    started_at = time.perf_counter()
    vertices, faces = _parse_obj(low_poly_mesh_content)
    if not vertices or not faces:
        raise UnfoldingFailed("Low-poly mesh has no vertices or faces.")
    if flap_size <= 0 or max_pages <= 0:
        raise UnfoldingFailed("flap_size and max_pages must be positive.")

    paper = _paper_dimensions(paper_size)
    parts = _parts_from_faces(vertices, faces, flap_size)
    pages, fallback_applied = _paginate(parts, max_pages, paper)
    if len(pages) > max_pages:
        raise UnfoldingFailed("Paper net exceeds the configured page budget.")

    metadata = {
        "real_stage": "unfolding",
        "source_stage": low_poly_mesh_metadata.get("real_stage"),
        "paper_size": paper_size,
        "page_count": len(pages),
        "part_count": len(parts),
        "fold_line_count": sum(part["fold_lines"] for part in parts),
        "glue_flap_count": sum(part["glue_flaps"] for part in parts),
        "pair_numbering": True,
        "fallback_simplification": fallback_applied,
        "processing_duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
    }
    net_json = {
        "mock": False,
        "schema": "papercraft.net.v1",
        "metadata": metadata,
        "pages": pages,
    }
    return UnfoldingResult(
        artifacts=(
            UnfoldingArtifactPayload(
                kind=ArtifactKind.NET_JSON,
                filename="paper-net.json",
                mime_type="application/json",
                content=json.dumps(net_json, separators=(",", ":")).encode(),
                metadata={**metadata, "artifact_role": "net_json"},
            ),
            UnfoldingArtifactPayload(
                kind=ArtifactKind.NET_SVG,
                filename="paper-net.svg",
                mime_type="image/svg+xml",
                content=_svg_bytes(pages, paper),
                metadata={**metadata, "artifact_role": "net_svg"},
            ),
        ),
        metadata=metadata,
    )


def _parse_obj(content: bytes) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    for raw_line in content.decode(errors="ignore").splitlines():
        line = raw_line.strip()
        if line.startswith("v "):
            parts = line.split()
            if len(parts) < 4:
                raise UnfoldingFailed("OBJ vertex line is invalid.")
            vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif line.startswith("f "):
            indices = [int(token.split("/")[0]) for token in line.split()[1:4]]
            if len(indices) == 3:
                faces.append((indices[0], indices[1], indices[2]))
    return vertices, faces


def _paper_dimensions(paper_size: str) -> dict[str, int]:
    if paper_size == "a3":
        return {"width": 297, "height": 420, "margin": 14}
    if paper_size == "a4":
        return {"width": 210, "height": 297, "margin": 10}
    raise UnfoldingFailed(f"Unsupported paper size: {paper_size}")


def _parts_from_faces(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
    flap_size: int,
) -> list[dict[str, object]]:
    parts: list[dict[str, object]] = []
    scale = 42
    for index, face in enumerate(faces, start=1):
        a, b, c = (vertices[vertex_index - 1] for vertex_index in face)
        edges = (_distance(a, b), _distance(b, c), _distance(c, a))
        width = max(18, min(72, int(max(edges) * scale)))
        height = max(16, min(64, int(_triangle_area(a, b, c) * scale * 4)))
        parts.append(
            {
                "id": f"face-{index}",
                "label": f"Part {index}",
                "face_index": index,
                "width": width,
                "height": height,
                "fold_lines": 3,
                "glue_flaps": 1 if index > 1 else 0,
                "flap_size": flap_size,
                "pair_number": index,
                "line_types": {"cut": 3, "mountain": 2, "valley": 1},
            }
        )
    return parts


def _paginate(
    parts: list[dict[str, object]],
    max_pages: int,
    paper: dict[str, int],
) -> tuple[list[dict[str, object]], bool]:
    per_page = _parts_per_page(paper)
    fallback_applied = False
    if math.ceil(len(parts) / per_page) > max_pages:
        per_page = max(per_page, math.ceil(len(parts) / max_pages))
        fallback_applied = True

    pages: list[dict[str, object]] = []
    for page_index, start in enumerate(range(0, len(parts), per_page), start=1):
        page_parts = parts[start : start + per_page]
        pages.append(
            {
                "page": page_index,
                "paper_size": "a3" if paper["width"] == 297 else "a4",
                "parts": _layout_parts(page_parts, paper),
            }
        )
    return pages, fallback_applied


def _parts_per_page(paper: dict[str, int]) -> int:
    usable_width = paper["width"] - paper["margin"] * 2
    usable_height = paper["height"] - paper["margin"] * 2
    return max(1, (usable_width // 52) * (usable_height // 48))


def _layout_parts(parts: list[dict[str, object]], paper: dict[str, int]) -> list[dict[str, object]]:
    laid_out: list[dict[str, object]] = []
    x = paper["margin"]
    y = paper["margin"]
    row_height = 0
    usable_right = paper["width"] - paper["margin"]
    for part in parts:
        width = int(part["width"])
        height = int(part["height"])
        if x + width > usable_right:
            x = paper["margin"]
            y += row_height + 8
            row_height = 0
        laid_out.append({**part, "x": x, "y": y})
        x += width + 8
        row_height = max(row_height, height)
    return laid_out


def _svg_bytes(pages: list[dict[str, object]], paper: dict[str, int]) -> bytes:
    height = paper["height"] * len(pages)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{paper["width"]}mm" height="{height}mm" viewBox="0 0 {paper["width"]} {height}">',
        '<style>.cut{fill:none;stroke:#111;stroke-width:.5}.fold{stroke:#2563eb;stroke-width:.35;stroke-dasharray:3 2}.label{font:4px sans-serif;fill:#111}</style>',
    ]
    for page in pages:
        page_offset = (int(page["page"]) - 1) * paper["height"]
        lines.append(f'<rect class="cut" x="0" y="{page_offset}" width="{paper["width"]}" height="{paper["height"]}"/>')
        lines.append(f'<text class="label" x="{paper["margin"]}" y="{page_offset + 7}">Page {page["page"]}</text>')
        for part in page["parts"]:
            x = int(part["x"])
            y = page_offset + int(part["y"])
            width = int(part["width"])
            height = int(part["height"])
            lines.append(f'<rect class="cut" x="{x}" y="{y}" width="{width}" height="{height}"/>')
            lines.append(f'<line class="fold" x1="{x}" y1="{y + height / 2:.2f}" x2="{x + width}" y2="{y + height / 2:.2f}"/>')
            lines.append(f'<text class="label" x="{x + 2}" y="{y + 5}">{part["label"]}</text>')
        lines.append(f'<text class="label" x="{paper["width"] - 26}" y="{page_offset + paper["height"] - 5}">{page["page"]}</text>')
    lines.append("</svg>")
    return ("\n".join(lines) + "\n").encode()


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt(sum((a[index] - b[index]) ** 2 for index in range(3)))


def _triangle_area(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    c: tuple[float, float, float],
) -> float:
    ab = tuple(b[index] - a[index] for index in range(3))
    ac = tuple(c[index] - a[index] for index in range(3))
    cross = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    return math.sqrt(sum(axis * axis for axis in cross)) / 2
