from io import BytesIO
import uuid

import pytest
from PIL import Image, ImageDraw

from app.domain.enums import ArtifactKind
from app.services.preprocessing import PreprocessingSubjectNotFound, preprocess_source_image


def _png_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_preprocess_source_image_generates_mask_crop_and_metadata() -> None:
    image = Image.new("RGB", (80, 60), color=(245, 245, 245))
    draw = ImageDraw.Draw(image)
    draw.rectangle((22, 12, 56, 48), fill=(190, 72, 52))
    source_image_id = uuid.uuid4()

    result = preprocess_source_image(
        source_image_id=source_image_id,
        source_storage_key="projects/demo/source-images/cat.png",
        content=_png_bytes(image),
    )

    assert {artifact.kind for artifact in result.artifacts} == {
        ArtifactKind.PREPROCESS_MASK,
        ArtifactKind.PREPROCESS_CROP,
    }
    assert all(artifact.content.startswith(b"\x89PNG") for artifact in result.artifacts)
    assert result.metadata["real_stage"] == "preprocessing"
    assert result.metadata["source_image_id"] == str(source_image_id)
    assert result.metadata["original_size"] == {"width": 80, "height": 60}
    assert result.metadata["mask_coverage"] > 0.1
    assert result.metadata["background"]["strategy"] == "border_color"
    assert result.metadata["view_hints"]["likely_view"] in {"front", "side", "unknown"}


def test_preprocess_source_image_rejects_blank_input() -> None:
    image = Image.new("RGB", (80, 60), color=(245, 245, 245))

    with pytest.raises(PreprocessingSubjectNotFound):
        preprocess_source_image(
            source_image_id=uuid.uuid4(),
            source_storage_key="projects/demo/source-images/blank.png",
            content=_png_bytes(image),
        )
