from app.domain.enums import ArtifactKind, ProjectCategory
from app.services.mesh_generation import generate_base_mesh
from app.services.paperability import decimate_mesh, optimize_paperability


def _base_mesh() -> bytes:
    result = generate_base_mesh(
        category=ProjectCategory.PET.value,
        target_poly_count=300,
        preprocessing_metadata={
            "crop_size": {"width": 64, "height": 80},
            "mask_coverage": 0.28,
            "view_hints": {"likely_view": "front"},
        },
    )
    return next(artifact.content for artifact in result.artifacts if artifact.kind == ArtifactKind.BASE_MESH)


def test_optimize_paperability_outputs_repaired_mesh_metadata() -> None:
    result = optimize_paperability(
        base_mesh_content=_base_mesh(),
        base_mesh_metadata={"mesh_strategy": "pet_body_head"},
    )

    assert result.artifact.kind == ArtifactKind.REPAIRED_MESH
    assert result.artifact.content.startswith(b"# AI PaperCraft paperability mesh")
    assert result.metadata["real_stage"] == "paperability_optimizing"
    assert result.metadata["source_mesh_strategy"] == "pet_body_head"
    assert result.metadata["face_count"] > 0
    assert result.metadata["repair_actions"]


def test_decimate_mesh_outputs_low_poly_mesh_with_budget_metadata() -> None:
    repaired = optimize_paperability(
        base_mesh_content=_base_mesh(),
        base_mesh_metadata={"mesh_strategy": "pet_body_head"},
    )

    result = decimate_mesh(
        repaired_mesh_content=repaired.artifact.content,
        repaired_mesh_metadata=repaired.artifact.metadata,
        target_poly_count=24,
        max_pages=2,
    )

    assert result.artifact.kind == ArtifactKind.LOW_POLY_MESH
    assert result.metadata["real_stage"] == "decimating"
    assert result.metadata["face_count"] <= 24
    assert result.metadata["page_budget_faces"] == 48
