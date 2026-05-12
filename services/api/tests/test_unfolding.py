import json

from app.domain.enums import ArtifactKind, ProjectCategory
from app.services.mesh_generation import generate_base_mesh
from app.services.paperability import decimate_mesh, optimize_paperability
from app.services.unfolding import unfold_low_poly_mesh


def _low_poly_mesh() -> tuple[bytes, dict[str, object]]:
    base = generate_base_mesh(
        category=ProjectCategory.PET.value,
        target_poly_count=96,
        preprocessing_metadata={
            "crop_size": {"width": 64, "height": 80},
            "mask_coverage": 0.28,
            "view_hints": {"likely_view": "front"},
        },
    )
    base_mesh = next(artifact for artifact in base.artifacts if artifact.kind == ArtifactKind.BASE_MESH)
    repaired = optimize_paperability(
        base_mesh_content=base_mesh.content,
        base_mesh_metadata=base_mesh.metadata,
    )
    low_poly = decimate_mesh(
        repaired_mesh_content=repaired.artifact.content,
        repaired_mesh_metadata=repaired.artifact.metadata,
        target_poly_count=24,
        max_pages=2,
    )
    return low_poly.artifact.content, low_poly.artifact.metadata


def test_unfold_low_poly_mesh_generates_net_json_and_svg() -> None:
    content, metadata = _low_poly_mesh()

    result = unfold_low_poly_mesh(
        low_poly_mesh_content=content,
        low_poly_mesh_metadata=metadata,
        paper_size="a4",
        flap_size=5,
        max_pages=4,
    )

    assert {artifact.kind for artifact in result.artifacts} == {
        ArtifactKind.NET_JSON,
        ArtifactKind.NET_SVG,
    }
    net_json = next(artifact for artifact in result.artifacts if artifact.kind == ArtifactKind.NET_JSON)
    payload = json.loads(net_json.content)
    assert payload["mock"] is False
    assert payload["metadata"]["real_stage"] == "unfolding"
    assert payload["pages"][0]["parts"][0]["fold_lines"] == 3
    assert payload["pages"][0]["parts"][0]["pair_number"] == 1
    net_svg = next(artifact for artifact in result.artifacts if artifact.kind == ArtifactKind.NET_SVG)
    assert net_svg.content.startswith(b"<svg")
    assert result.metadata["part_count"] > 0
