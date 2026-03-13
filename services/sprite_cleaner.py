"""
Sprite background removal pipeline.

Primary path: rembg (AI segmentation) -> alpha-threshold crop -> save as RGBA PNG.
Fallback path: chroma key on magenta (#ff00ff) for styles where rembg over-removes.
"""

import io
import logging

import numpy as np
from PIL import Image
from rembg import remove

logger = logging.getLogger(__name__)

MAGENTA = (255, 0, 255)
CROP_PADDING = 8
ALPHA_THRESHOLD = 10


def remove_background(image_data: bytes) -> Image.Image:
    """Remove background via rembg, then alpha-crop. Falls back to chroma key on failure."""
    img = Image.open(io.BytesIO(image_data)).convert("RGBA")

    try:
        cleaned = remove(img)
        if _has_meaningful_content(cleaned):
            return _alpha_crop(cleaned)
        logger.warning("rembg removed too much content, falling back to chroma key")
    except Exception as e:
        logger.warning("rembg failed (%s), falling back to chroma key", e)

    return chroma_key_remove(img)


def chroma_key_remove(
    img: Image.Image,
    key_color: tuple[int, int, int] = MAGENTA,
    tolerance: int = 50,
) -> Image.Image:
    """Remove a solid background color via chroma key with smooth edges."""
    img = img.convert("RGBA")
    data = np.array(img, dtype=np.float32)
    rgb = data[:, :, :3]

    key = np.array(key_color, dtype=np.float32)
    distance = np.sqrt(np.sum((rgb - key) ** 2, axis=2))

    inner = tolerance * 0.6
    alpha = np.clip((distance - inner) / (tolerance - inner + 1e-6), 0, 1) * 255
    data[:, :, 3] = alpha.astype(np.uint8)

    result = Image.fromarray(data.astype(np.uint8), "RGBA")
    return _alpha_crop(result)


def _has_meaningful_content(img: Image.Image, min_ratio: float = 0.05) -> bool:
    """Check that at least min_ratio of pixels survived background removal."""
    alpha = np.array(img.split()[3])
    opaque_pixels = np.count_nonzero(alpha > ALPHA_THRESHOLD)
    total_pixels = alpha.size
    return (opaque_pixels / total_pixels) >= min_ratio


def _alpha_crop(img: Image.Image) -> Image.Image:
    """Crop to the bounding box of non-transparent pixels with padding."""
    alpha = img.split()[3]
    mask = alpha.point(lambda a: 255 if a > ALPHA_THRESHOLD else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return img

    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - CROP_PADDING)
    y0 = max(0, y0 - CROP_PADDING)
    x1 = min(img.width, x1 + CROP_PADDING)
    y1 = min(img.height, y1 + CROP_PADDING)

    return img.crop((x0, y0, x1, y1))
