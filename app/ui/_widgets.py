"""Small shared UI helpers."""
from __future__ import annotations

from typing import Optional

import cv2
import customtkinter as ctk
import numpy as np
from PIL import Image


def bgr_to_ctk_image(frame_bgr: np.ndarray, size: tuple[int, int]) -> ctk.CTkImage:
    """Convert an OpenCV BGR frame to a CTkImage fitted (letterboxed) into ``size``.

    The frame is mirrored horizontally so the preview behaves like a mirror, which
    feels natural to the person standing at the camera.
    """
    w, h = size
    frame = cv2.flip(frame_bgr, 1)
    fh, fw = frame.shape[:2]
    scale = min(w / fw, h / fh)
    new_size = (max(1, int(fw * scale)), max(1, int(fh * scale)))
    frame = cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    return ctk.CTkImage(light_image=pil, dark_image=pil, size=new_size)


def placeholder_image(size: tuple[int, int], text_color=(60, 60, 60)) -> ctk.CTkImage:
    """A blank dark image used when the camera is unavailable."""
    w, h = size
    arr = np.full((h, w, 3), 30, dtype=np.uint8)
    pil = Image.fromarray(arr)
    return ctk.CTkImage(light_image=pil, dark_image=pil, size=(w, h))
