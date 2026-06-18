"""Thin OpenCV camera wrapper.

Owns a single ``cv2.VideoCapture`` and hands out the latest BGR frame. Designed to
be started/stopped as the user moves between the kiosk/enrollment screens so the
webcam light isn't on unnecessarily. Read errors are surfaced as ``None`` frames so
the UI can show a friendly "camera unavailable" message instead of crashing.
"""
from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

import config


class Camera:
    def __init__(self, index: int = config.CAMERA_INDEX) -> None:
        self.index = index
        self._cap: Optional[cv2.VideoCapture] = None

    def start(self) -> bool:
        """Open the camera. Returns True on success."""
        if self._cap is not None and self._cap.isOpened():
            return True
        # CAP_DSHOW avoids slow startup on Windows.
        self._cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW)
        if not self._cap.isOpened():
            self._cap = None
            return False
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        return True

    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def read(self) -> Optional[np.ndarray]:
        """Return the latest BGR frame, or None if unavailable."""
        if self._cap is None:
            return None
        ok, frame = self._cap.read()
        if not ok or frame is None:
            return None
        return frame

    def stop(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self) -> "Camera":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()
