import pytest

from app.domain.enums import ArtifactKind, ProjectCategory
from app.services.mesh_generation import MeshGenerationFailed, generate_base_mesh


@pytest.mark.parametrize(
    ("category", "expected_strategy"),
    [
        (ProjectCategory.PET.value, "pet_body_head"),
        (ProjectCategory.BUST.value, "bust_head_shoulders"),
        (ProjectCategory.SIMPLE_OBJECT.value, "simple_object_prism"),
    ],
)
def test_generate_base_mesh_creates_obj_and_preview_artifacts(category: str, expected_strategy: str) -> None:
    result = generate_base_mesh(
        category=category,
        target_poly_count=300,
        preprocessing_metadata={
            "crop_size": {"width": 64, "height": 80},
            "mask_coverage": 0.28,
            "view_hints": {"likely_view": "front"},
        },
    )

    assert {artifact.kind for artifact in result.artifacts} == {
        ArtifactKind.BASE_MESH,
        ArtifactKind.PREVIEW_MODEL,
    }
    base_mesh = next(artifact for artifact in result.artifacts if artifact.kind == ArtifactKind.BASE_MESH)
    assert base_mesh.content.startswith(b"# AI PaperCraft generated base mesh")
    assert b"\nv " in base_mesh.content
    assert b"\nf " in base_mesh.content
    assert base_mesh.metadata["real_stage"] == "model_generating"
    assert base_mesh.metadata["mesh_strategy"] == expected_strategy
    assert base_mesh.metadata["face_count"] > 0


def test_generate_base_mesh_rejects_missing_preprocessing_metadata() -> None:
    with pytest.raises(MeshGenerationFailed):
        generate_base_mesh(
            category=ProjectCategory.SIMPLE_OBJECT.value,
            target_poly_count=300,
            preprocessing_metadata={"crop_size": {"width": 64, "height": 80}},
        )
