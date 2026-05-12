import time
import uuid
from dataclasses import dataclass
from io import BytesIO
from statistics import median

from PIL import Image, ImageChops, ImageFilter, ImageOps, UnidentifiedImageError

from app.domain.enums import ArtifactKind


class PreprocessingSubjectNotFound(Exception):
    pass


class PreprocessingFailed(Exception):
    pass


@dataclass(frozen=True)
class PreprocessingArtifactPayload:
    kind: ArtifactKind
    filename: str
    mime_type: str
    content: bytes
    metadata: dict[str, object]


@dataclass(frozen=True)
class PreprocessingResult:
    artifacts: tuple[PreprocessingArtifactPayload, ...]
    metadata: dict[str, object]


def preprocess_source_image(
    *,
    source_image_id: uuid.UUID,
    source_storage_key: str,
    content: bytes,
) -> PreprocessingResult:
    started_at = time.perf_counter()
    try:
        image = _load_rgba(content)
        mask, background_metadata = _subject_mask(image)
    except PreprocessingSubjectNotFound:
        raise
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        raise PreprocessingFailed("Source image could not be preprocessed.") from exc

    bbox = mask.getbbox()
    if bbox is None:
        raise PreprocessingSubjectNotFound("No subject could be detected in the source image.")

    bbox = _pad_box(bbox, image.size)
    mask = _clean_mask(mask)
    mask_coverage = _mask_coverage(mask)
    if mask_coverage < 0.01:
        raise PreprocessingSubjectNotFound("Detected subject is too small for preprocessing.")
    if background_metadata["strategy"] != "alpha" and mask_coverage > 0.96:
        raise PreprocessingSubjectNotFound("Source image does not expose a separable subject.")

    crop = image.crop(bbox)
    crop.putalpha(mask.crop(bbox))

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    metadata = {
        "real_stage": "preprocessing",
        "source_image_id": str(source_image_id),
        "source_storage_key": source_storage_key,
        "original_size": {"width": image.width, "height": image.height},
        "crop_box": {"left": bbox[0], "top": bbox[1], "right": bbox[2], "bottom": bbox[3]},
        "crop_size": {"width": bbox[2] - bbox[0], "height": bbox[3] - bbox[1]},
        "mask_coverage": round(mask_coverage, 4),
        "processing_duration_ms": duration_ms,
        "background": background_metadata,
        "view_hints": _view_hints(bbox, image.size, background_metadata["strategy"]),
    }

    mask_bytes = _png_bytes(mask)
    crop_bytes = _png_bytes(crop)
    return PreprocessingResult(
        artifacts=(
            PreprocessingArtifactPayload(
                kind=ArtifactKind.PREPROCESS_MASK,
                filename="preprocess-mask.png",
                mime_type="image/png",
                content=mask_bytes,
                metadata={**metadata, "artifact_role": "mask"},
            ),
            PreprocessingArtifactPayload(
                kind=ArtifactKind.PREPROCESS_CROP,
                filename="preprocess-crop.png",
                mime_type="image/png",
                content=crop_bytes,
                metadata={**metadata, "artifact_role": "crop"},
            ),
        ),
        metadata=metadata,
    )


def _load_rgba(content: bytes) -> Image.Image:
    with Image.open(BytesIO(content)) as image:
        return ImageOps.exif_transpose(image).convert("RGBA")


def _subject_mask(image: Image.Image) -> tuple[Image.Image, dict[str, object]]:
    alpha = image.getchannel("A")
    alpha_mask = alpha.point(lambda value: 255 if value > 20 else 0)
    alpha_coverage = _mask_coverage(alpha_mask)
    if alpha.getextrema()[0] < 250 and 0.01 <= alpha_coverage <= 0.99:
        return _clean_mask(alpha_mask), {
            "strategy": "alpha",
            "transparent_background": True,
            "plain_background": False,
        }

    border_color = _estimate_border_color(image)
    rgb_image = image.convert("RGB")
    background = Image.new("RGB", image.size, border_color)
    difference = ImageChops.difference(rgb_image, background).convert("L")
    threshold = max(24, int(_border_difference_median(difference) * 2.5))
    mask = difference.point(lambda value: 255 if value > threshold else 0)
    coverage = _mask_coverage(mask)
    if coverage < 0.01:
        raise PreprocessingSubjectNotFound("No subject could be separated from the background.")

    return _clean_mask(mask), {
        "strategy": "border_color",
        "transparent_background": False,
        "plain_background": _border_difference_median(difference) <= 12,
        "estimated_color_rgb": list(border_color),
        "threshold": threshold,
    }


def _estimate_border_color(image: Image.Image) -> tuple[int, int, int]:
    rgb_image = image.convert("RGB")
    width, height = rgb_image.size
    step = max(1, min(width, height) // 40)
    samples: list[tuple[int, int, int]] = []
    for x in range(0, width, step):
        samples.append(rgb_image.getpixel((x, 0)))
        samples.append(rgb_image.getpixel((x, height - 1)))
    for y in range(0, height, step):
        samples.append(rgb_image.getpixel((0, y)))
        samples.append(rgb_image.getpixel((width - 1, y)))
    return (
        int(median(pixel[0] for pixel in samples)),
        int(median(pixel[1] for pixel in samples)),
        int(median(pixel[2] for pixel in samples)),
    )


def _border_difference_median(difference: Image.Image) -> float:
    width, height = difference.size
    step = max(1, min(width, height) // 40)
    samples: list[int] = []
    for x in range(0, width, step):
        samples.append(difference.getpixel((x, 0)))
        samples.append(difference.getpixel((x, height - 1)))
    for y in range(0, height, step):
        samples.append(difference.getpixel((0, y)))
        samples.append(difference.getpixel((width - 1, y)))
    return float(median(samples))


def _clean_mask(mask: Image.Image) -> Image.Image:
    return mask.filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))


def _mask_coverage(mask: Image.Image) -> float:
    histogram = mask.histogram()
    total = mask.width * mask.height
    return (total - histogram[0]) / total


def _pad_box(box: tuple[int, int, int, int], size: tuple[int, int]) -> tuple[int, int, int, int]:
    left, top, right, bottom = box
    width, height = size
    pad = max(2, int(max(right - left, bottom - top) * 0.06))
    return (
        max(0, left - pad),
        max(0, top - pad),
        min(width, right + pad),
        min(height, bottom + pad),
    )


def _view_hints(box: tuple[int, int, int, int], size: tuple[int, int], background_strategy: str) -> dict[str, object]:
    left, top, right, bottom = box
    image_width, image_height = size
    crop_width = right - left
    crop_height = bottom - top
    aspect_ratio = crop_width / crop_height if crop_height else 0
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    offset_x = round((center_x - image_width / 2) / image_width, 4)
    offset_y = round((center_y - image_height / 2) / image_height, 4)
    likely_view = "unknown"
    if abs(offset_x) <= 0.18 and 0.65 <= aspect_ratio <= 1.35:
        likely_view = "front"
    elif aspect_ratio > 1.35:
        likely_view = "side"

    return {
        "subject_aspect_ratio": round(aspect_ratio, 4),
        "center_offset": {"x": offset_x, "y": offset_y},
        "position": "centered" if abs(offset_x) <= 0.18 and abs(offset_y) <= 0.18 else "off_center",
        "likely_view": likely_view,
        "background_hint": "transparent" if background_strategy == "alpha" else "plain_or_border",
    }


def _png_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
