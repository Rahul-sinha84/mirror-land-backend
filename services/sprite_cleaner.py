"""
Sprite background removal pipeline.

rembg (AI segmentation) -> alpha-threshold crop -> RGBA PNG.
"""

import io

from PIL import Image
from rembg import remove

CROP_PADDING = 8
ALPHA_THRESHOLD = 10


def remove_background(image_data: bytes) -> Image.Image:
    """Remove background via rembg, then alpha-crop."""
    img = Image.open(io.BytesIO(image_data)).convert("RGBA")
    cleaned = remove(img)
    return _alpha_crop(cleaned)


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
