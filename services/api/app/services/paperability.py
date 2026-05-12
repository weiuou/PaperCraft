import math
import time
from dataclasses import dataclass

from app.domain.enums import ArtifactKind


class PaperabilityOptimizationFailed(Exception):
    pass


class MeshDecimationFailed(Exception):
    pass


@dataclass(frozen=True)
class MeshArtifactPayload:
    kind: ArtifactKind
    filename: str
    mime_type: str
    content: bytes
    metadata: dict[str, object]


@dataclass(frozen=True)
class PaperabilityResult:
    artifact: MeshArtifactPayload
    metadata: dict[str, object]


@dataclass(frozen=True)
class DecimationResult:
    artifact: MeshArtifactPayload
    metadata: dict[str, object]


def optimize_paperability(
    *,
    base_mesh_content: bytes,
    base_mesh_metadata: dict[str, object],
    min_edge_length: float = 0.08,
    min_face_area: float = 0.003,
) -> PaperabilityResult:
    started_at = time.perf_counter()
    vertices, faces = _parse_obj(base_mesh_content)
    if not vertices or not faces:
        raise PaperabilityOptimizationFailed("Base mesh has no vertices or faces.")

    repaired_vertices, repaired_faces, repair_actions = _repair_mesh(vertices, faces)
    edge_lengths = _edge_lengths(repaired_vertices, repaired_faces)
    face_areas = _face_areas(repaired_vertices, repaired_faces)
    thin_edges = sum(1 for length in edge_lengths if length < min_edge_length)
    tiny_faces = sum(1 for area in face_areas if area < min_face_area)
    fragile = thin_edges > max(2, len(edge_lengths) * 0.08) or tiny_faces > max(1, len(face_areas) * 0.08)

    if fragile:
        repaired_vertices, repaired_faces = _scale_mesh(repaired_vertices, repaired_faces, 1.08)
        repair_actions.append("uniform_reinforcement_scale")

    metadata = {
        "real_stage": "paperability_optimizing",
        "source_mesh_strategy": base_mesh_metadata.get("mesh_strategy"),
        "vertex_count": len(repaired_vertices),
        "face_count": len(repaired_faces),
        "min_edge_length": round(min(edge_lengths), 5) if edge_lengths else None,
        "min_face_area": round(min(face_areas), 5) if face_areas else None,
        "thin_edge_count": thin_edges,
        "tiny_face_count": tiny_faces,
        "fragile_structure": fragile,
        "repair_actions": repair_actions,
        "processing_duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
    }
    return PaperabilityResult(
        artifact=MeshArtifactPayload(
            kind=ArtifactKind.REPAIRED_MESH,
            filename="repaired-mesh.obj",
            mime_type="model/obj",
            content=_obj_bytes(repaired_vertices, repaired_faces, "papercraft_repaired_mesh"),
            metadata={**metadata, "artifact_role": "repaired_mesh"},
        ),
        metadata=metadata,
    )


def decimate_mesh(
    *,
    repaired_mesh_content: bytes,
    repaired_mesh_metadata: dict[str, object],
    target_poly_count: int,
    max_pages: int,
) -> DecimationResult:
    started_at = time.perf_counter()
    vertices, faces = _parse_obj(repaired_mesh_content)
    if not vertices or not faces:
        raise MeshDecimationFailed("Repaired mesh has no vertices or faces.")
    if target_poly_count <= 0 or max_pages <= 0:
        raise MeshDecimationFailed("target_poly_count and max_pages must be positive.")

    page_budget_faces = max_pages * 24
    target_faces = max(12, min(len(faces), target_poly_count, page_budget_faces))
    selected_faces = _select_evenly_spaced_faces(faces, target_faces)
    compact_vertices, compact_faces = _compact_vertices(vertices, selected_faces)
    if not compact_faces:
        raise MeshDecimationFailed("Decimation removed all faces.")

    metadata = {
        "real_stage": "decimating",
        "source_stage": repaired_mesh_metadata.get("real_stage"),
        "target_poly_count": target_poly_count,
        "max_pages": max_pages,
        "source_face_count": len(faces),
        "face_count": len(compact_faces),
        "vertex_count": len(compact_vertices),
        "reduction_ratio": round(1 - (len(compact_faces) / len(faces)), 4),
        "page_budget_faces": page_budget_faces,
        "processing_duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
    }
    return DecimationResult(
        artifact=MeshArtifactPayload(
            kind=ArtifactKind.LOW_POLY_MESH,
            filename="low-poly-mesh.obj",
            mime_type="model/obj",
            content=_obj_bytes(compact_vertices, compact_faces, "papercraft_low_poly_mesh"),
            metadata={**metadata, "artifact_role": "low_poly_mesh"},
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
                raise PaperabilityOptimizationFailed("OBJ vertex line is invalid.")
            vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif line.startswith("f "):
            indices = []
            for token in line.split()[1:4]:
                indices.append(int(token.split("/")[0]))
            if len(indices) == 3:
                faces.append((indices[0], indices[1], indices[2]))
    return vertices, faces


def _repair_mesh(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]], list[str]]:
    actions: list[str] = []
    unique_vertices: list[tuple[float, float, float]] = []
    vertex_map: dict[tuple[float, float, float], int] = {}
    old_to_new: dict[int, int] = {}
    for old_index, vertex in enumerate(vertices, start=1):
        rounded = tuple(round(axis, 5) for axis in vertex)
        if rounded not in vertex_map:
            vertex_map[rounded] = len(unique_vertices) + 1
            unique_vertices.append(rounded)
        old_to_new[old_index] = vertex_map[rounded]
    if len(unique_vertices) != len(vertices):
        actions.append("deduplicated_vertices")

    repaired_faces: list[tuple[int, int, int]] = []
    seen_faces: set[tuple[int, int, int]] = set()
    for face in faces:
        remapped = tuple(old_to_new[index] for index in face)
        if len(set(remapped)) < 3:
            actions.append("removed_degenerate_face")
            continue
        canonical = tuple(sorted(remapped))
        if canonical in seen_faces:
            actions.append("removed_duplicate_face")
            continue
        seen_faces.add(canonical)
        repaired_faces.append(remapped)

    if not repaired_faces:
        raise PaperabilityOptimizationFailed("Mesh repair removed every face.")
    if not actions:
        actions.append("validated_manifold_candidate")
    return unique_vertices, repaired_faces, actions


def _edge_lengths(vertices: list[tuple[float, float, float]], faces: list[tuple[int, int, int]]) -> list[float]:
    edges: set[tuple[int, int]] = set()
    for a, b, c in faces:
        edges.update({tuple(sorted((a, b))), tuple(sorted((b, c))), tuple(sorted((c, a)))})
    return [_distance(vertices[a - 1], vertices[b - 1]) for a, b in edges]


def _face_areas(vertices: list[tuple[float, float, float]], faces: list[tuple[int, int, int]]) -> list[float]:
    return [_triangle_area(vertices[a - 1], vertices[b - 1], vertices[c - 1]) for a, b, c in faces]


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


def _scale_mesh(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
    factor: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    return [(x * factor, y * factor, z * factor) for x, y, z in vertices], faces


def _select_evenly_spaced_faces(faces: list[tuple[int, int, int]], target_faces: int) -> list[tuple[int, int, int]]:
    if target_faces >= len(faces):
        return faces
    step = len(faces) / target_faces
    selected: list[tuple[int, int, int]] = []
    used_indexes: set[int] = set()
    for index in range(target_faces):
        face_index = min(len(faces) - 1, int(index * step))
        while face_index in used_indexes and face_index + 1 < len(faces):
            face_index += 1
        used_indexes.add(face_index)
        selected.append(faces[face_index])
    return selected


def _compact_vertices(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    used = sorted({index for face in faces for index in face})
    mapping = {old_index: new_index for new_index, old_index in enumerate(used, start=1)}
    compact_vertices = [vertices[old_index - 1] for old_index in used]
    compact_faces = [tuple(mapping[index] for index in face) for face in faces]
    return compact_vertices, compact_faces


def _obj_bytes(vertices: list[tuple[float, float, float]], faces: list[tuple[int, int, int]], name: str) -> bytes:
    lines = ["# AI PaperCraft paperability mesh", f"o {name}"]
    lines.extend(f"v {x:.5f} {y:.5f} {z:.5f}" for x, y, z in vertices)
    lines.extend(f"f {a} {b} {c}" for a, b, c in faces)
    return ("\n".join(lines) + "\n").encode()
