"""Image helpers: save check-in thumbnails and crop faces.

Frames from OpenCV are BGR numpy arrays. Thumbnails are saved as JPEGs under
``config.THUMBNAIL_DIR`` with a timestamped name so each check-in has its own audit
photo.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

import cv2
import numpy as np

import config


def crop_face(frame: np.ndarray, bbox: Sequence[float], margin: float = 0.2) -> np.ndarray:
    """Crop a face region from a BGR frame given a [x1, y1, x2, y2] bbox.

    A margin is added around the box and the crop is clamped to the frame bounds.
    """
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = [int(v) for v in bbox[:4]]
    bw, bh = x2 - x1, y2 - y1
    mx, my = int(bw * margin), int(bh * margin)
    x1 = max(0, x1 - mx)
    y1 = max(0, y1 - my)
    x2 = min(w, x2 + mx)
    y2 = min(h, y2 + my)
    if x2 <= x1 or y2 <= y1:
        return frame
    return frame[y1:y2, x1:x2]


def save_thumbnail(
    image: np.ndarray,
    prefix: str = "checkin",
    max_size: int = 240,
) -> str:
    """Save a BGR image as a JPEG thumbnail and return its absolute path string."""
    config.THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
    thumb = _resize_max(image, max_size)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = config.THUMBNAIL_DIR / f"{prefix}_{stamp}.jpg"
    cv2.imwrite(str(path), thumb, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return str(path)


def _resize_max(image: np.ndarray, max_size: int) -> np.ndarray:
    h, w = image.shape[:2]
    scale = max_size / max(h, w)
    if scale >= 1:
        return image
    return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


def load_bgr(path: str) -> Optional[np.ndarray]:
    """Load an image file as a BGR array, or None if it can't be read."""
    if not path or not Path(path).exists():
        return None
    return cv2.imread(path)
