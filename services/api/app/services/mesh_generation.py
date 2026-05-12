import math
import time
from dataclasses import dataclass

from app.domain.enums import ArtifactKind, ProjectCategory


class MeshGenerationFailed(Exception):
    pass


@dataclass(frozen=True)
class MeshArtifactPayload:
    kind: ArtifactKind
    filename: str
    mime_type: str
    content: bytes
    metadata: dict[str, object]


@dataclass(frozen=True)
class MeshGenerationResult:
    artifacts: tuple[MeshArtifactPayload, ...]
    metadata: dict[str, object]


def generate_base_mesh(
    *,
    category: str,
    target_poly_count: int,
    preprocessing_metadata: dict[str, object],
) -> MeshGenerationResult:
    started_at = time.perf_counter()
    crop_size = preprocessing_metadata.get("crop_size")
    view_hints = preprocessing_metadata.get("view_hints")
    if not isinstance(crop_size, dict) or not isinstance(view_hints, dict):
        raise MeshGenerationFailed("Preprocessing metadata is missing crop size or view hints.")

    crop_width = _positive_number(crop_size.get("width"), "crop width")
    crop_height = _positive_number(crop_size.get("height"), "crop height")
    aspect_ratio = crop_width / crop_height
    segments = _segments_for_target(target_poly_count)

    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    category_value = ProjectCategory(category)
    if category_value == ProjectCategory.PET:
        _append_ellipsoid(vertices, faces, center=(0, -0.08, 0), radius=(0.45 * aspect_ratio, 0.34, 0.32), segments=segments)
        _append_ellipsoid(vertices, faces, center=(0, 0.34, 0), radius=(0.26, 0.24, 0.24), segments=max(8, segments - 2))
        strategy = "pet_body_head"
    elif category_value == ProjectCategory.BUST:
        _append_ellipsoid(vertices, faces, center=(0, 0.26, 0), radius=(0.28, 0.32, 0.25), segments=segments)
        _append_ellipsoid(vertices, faces, center=(0, -0.24, 0), radius=(0.5 * aspect_ratio, 0.22, 0.22), segments=max(8, segments - 2))
        strategy = "bust_head_shoulders"
    else:
        _append_box(vertices, faces, width=max(0.45, min(1.1, aspect_ratio)), height=0.78, depth=0.42)
        strategy = "simple_object_prism"

    obj = _obj_bytes(vertices, faces)
    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    metadata = {
        "real_stage": "model_generating",
        "mesh_strategy": strategy,
        "category": category,
        "target_poly_count": target_poly_count,
        "vertex_count": len(vertices),
        "face_count": len(faces),
        "source_preprocessing": {
            "crop_size": crop_size,
            "mask_coverage": preprocessing_metadata.get("mask_coverage"),
            "view_hints": view_hints,
        },
        "processing_duration_ms": duration_ms,
    }
    return MeshGenerationResult(
        artifacts=(
            MeshArtifactPayload(
                kind=ArtifactKind.BASE_MESH,
                filename="base-mesh.obj",
                mime_type="model/obj",
                content=obj,
                metadata={**metadata, "artifact_role": "base_mesh"},
            ),
            MeshArtifactPayload(
                kind=ArtifactKind.PREVIEW_MODEL,
                filename="base-mesh-preview.gltf",
                mime_type="model/gltf+json",
                content=_preview_gltf_bytes(len(vertices), len(faces)),
                metadata={**metadata, "artifact_role": "preview_model"},
            ),
        ),
        metadata=metadata,
    )


def _positive_number(value: object, name: str) -> float:
    if not isinstance(value, int | float) or value <= 0:
        raise MeshGenerationFailed(f"Preprocessing metadata has invalid {name}.")
    return float(value)


def _segments_for_target(target_poly_count: int) -> int:
    if target_poly_count <= 0:
        raise MeshGenerationFailed("target_poly_count must be positive.")
    return max(8, min(18, int(math.sqrt(target_poly_count / 2))))


def _append_ellipsoid(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
    *,
    center: tuple[float, float, float],
    radius: tuple[float, float, float],
    segments: int,
) -> None:
    rings = max(4, segments // 2)
    offset = len(vertices) + 1
    for ring in range(rings + 1):
        phi = math.pi * ring / rings
        for segment in range(segments):
            theta = 2 * math.pi * segment / segments
            vertices.append(
                (
                    center[0] + radius[0] * math.sin(phi) * math.cos(theta),
                    center[1] + radius[1] * math.cos(phi),
                    center[2] + radius[2] * math.sin(phi) * math.sin(theta),
                )
            )

    for ring in range(rings):
        for segment in range(segments):
            current = offset + ring * segments + segment
            next_segment = offset + ring * segments + (segment + 1) % segments
            below = offset + (ring + 1) * segments + segment
            below_next = offset + (ring + 1) * segments + (segment + 1) % segments
            faces.append((current, below, next_segment))
            faces.append((next_segment, below, below_next))


def _append_box(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
    *,
    width: float,
    height: float,
    depth: float,
) -> None:
    offset = len(vertices) + 1
    half_width = width / 2
    half_height = height / 2
    half_depth = depth / 2
    vertices.extend(
        [
            (-half_width, -half_height, -half_depth),
            (half_width, -half_height, -half_depth),
            (half_width, half_height, -half_depth),
            (-half_width, half_height, -half_depth),
            (-half_width, -half_height, half_depth),
            (half_width, -half_height, half_depth),
            (half_width, half_height, half_depth),
            (-half_width, half_height, half_depth),
        ]
    )
    faces.extend(
        (tuple(index + offset - 1 for index in face) for face in (
            (1, 2, 3),
            (1, 3, 4),
            (5, 7, 6),
            (5, 8, 7),
            (1, 5, 6),
            (1, 6, 2),
            (2, 6, 7),
            (2, 7, 3),
            (3, 7, 8),
            (3, 8, 4),
            (4, 8, 5),
            (4, 5, 1),
        ))
    )


def _obj_bytes(vertices: list[tuple[float, float, float]], faces: list[tuple[int, int, int]]) -> bytes:
    lines = ["# AI PaperCraft generated base mesh", "o papercraft_base_mesh"]
    lines.extend(f"v {x:.5f} {y:.5f} {z:.5f}" for x, y, z in vertices)
    lines.extend(f"f {a} {b} {c}" for a, b, c in faces)
    return ("\n".join(lines) + "\n").encode()


def _preview_gltf_bytes(vertex_count: int, face_count: int) -> bytes:
    return (
        "{\n"
        '  "asset": {"version": "2.0", "generator": "AI PaperCraft M3 deterministic mesh"},\n'
        f'  "extras": {{"preview_placeholder": true, "vertex_count": {vertex_count}, "face_count": {face_count}}}\n'
        "}\n"
    ).encode()
