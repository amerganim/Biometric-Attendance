"""Liveness detection: layered anti-spoofing.

Two independent layers that fail differently:

1. **Passive anti-spoof** (``PassiveLiveness``) — a Silent-Face style ONNX model that
   scores a face crop as real vs. a presentation attack (printed photo / phone
   screen) without asking the user to do anything. If no model file is installed it
   degrades gracefully: it reports ``available = False`` and a neutral score, and the
   attendance service falls back to the active challenge alone. Drop a converted
   Silent-Face ONNX model at ``data/models/antispoof.onnx`` to enable it.

2. **Active challenge** (``ActiveChallenge``) — asks the user to turn/nod their head,
   verified from insightface's 5 face keypoints (the same detector used for
   recognition, so it works wherever recognition does). A held-up still photo
   produces no head movement and fails.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

import config

# ---------------------------------------------------------------------------
# Passive anti-spoof (ONNX, optional)
# ---------------------------------------------------------------------------
ANTISPOOF_MODEL_PATH = config.MODELS_DIR / "antispoof.onnx"


@dataclass
class PassiveResult:
    score: float          # probability the face is real [0..1]
    available: bool       # False when no model is installed (score is neutral)


class PassiveLiveness:
    """Runs a Silent-Face-style ONNX anti-spoof model if one is installed."""

    def __init__(self) -> None:
        self._session = None
        self._input_name: Optional[str] = None
        self._input_size = (80, 80)
        self._tried = False

    def _ensure_loaded(self) -> bool:
        if self._tried:
            return self._session is not None
        self._tried = True
        if not ANTISPOOF_MODEL_PATH.exists():
            return False
        try:
            import onnxruntime as ort

            self._session = ort.InferenceSession(
                str(ANTISPOOF_MODEL_PATH), providers=["CPUExecutionProvider"]
            )
            inp = self._session.get_inputs()[0]
            self._input_name = inp.name
            # NCHW: grab H, W if statically shaped.
            shape = inp.shape
            if len(shape) == 4 and isinstance(shape[2], int) and isinstance(shape[3], int):
                self._input_size = (shape[3], shape[2])
        except Exception:  # pragma: no cover - model/runtime issues shouldn't crash UI
            self._session = None
        return self._session is not None

    def score(self, face_bgr: np.ndarray) -> PassiveResult:
        """Score a cropped BGR face image as real (1.0) vs spoof (0.0)."""
        if not self._ensure_loaded():
            return PassiveResult(score=1.0, available=False)
        try:
            import cv2

            img = cv2.resize(face_bgr, self._input_size)
            img = img.astype(np.float32) / 255.0
            blob = np.transpose(img, (2, 0, 1))[np.newaxis, ...]  # NCHW
            out = self._session.run(None, {self._input_name: blob})[0]
            probs = _softmax(np.asarray(out).ravel())
            # Convention: last class = "real". Falls back to max if 2-class.
            real_score = float(probs[-1]) if probs.size >= 2 else float(probs[0])
            return PassiveResult(score=real_score, available=True)
        except Exception:  # pragma: no cover
            return PassiveResult(score=1.0, available=False)


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - np.max(x))
    return e / e.sum()


# ---------------------------------------------------------------------------
# Active challenge (insightface 5-point keypoints)
# ---------------------------------------------------------------------------
# We use the same detector that recognizes the teacher (insightface), so liveness
# works wherever recognition does. insightface returns 5 keypoints per face:
#   kps[0]=left eye, kps[1]=right eye, kps[2]=nose, kps[3]=left mouth, kps[4]=right
# We track the nose position relative to the eye-centre, normalized by the inter-eye
# distance (so it's invariant to distance and where you stand). A live person who
# turns or nods their head shifts this; a held-up still photo does not.
MOVE_DELTA = 0.07               # normalized nose shift that counts as head movement
WARMUP_FRAMES = 3               # frames to establish the baseline head pose


class ActiveChallenge:
    """Stateful liveness verifier fed face keypoints via ``update_kps``."""

    def __init__(self) -> None:
        self.passed = False
        self.how = ""                # which signal passed
        self.saw_face = False        # True once keypoints have been seen
        self._frames = 0
        self._base: Optional[np.ndarray] = None  # baseline (dx, dy) nose offset
        self._max_dev = 0.0          # largest deviation seen (diagnostics)

    @property
    def prompt(self) -> str:
        return "slowly turn your head left or right"

    def update_kps(self, kps: Optional[np.ndarray]) -> bool:
        """Process one set of 5 face keypoints; True once liveness is satisfied."""
        if self.passed:
            return True
        if kps is None or len(kps) < 3:
            return False
        try:
            left_eye, right_eye, nose = kps[0], kps[1], kps[2]
            eye_center = (left_eye + right_eye) / 2.0
            inter_eye = float(np.linalg.norm(right_eye - left_eye))
            if inter_eye < 1e-3:
                return False
            offset = (nose - eye_center) / inter_eye  # (dx, dy), scale-invariant

            self.saw_face = True
            self._frames += 1
            if self._base is None:
                self._base = offset.copy()
            dev = float(np.linalg.norm(offset - self._base))
            self._max_dev = max(self._max_dev, dev)

            if self._frames >= WARMUP_FRAMES and dev >= MOVE_DELTA:
                self.passed = True
                self.how = "move"
        except Exception:
            return False
        return self.passed

    def summary(self) -> str:
        """Diagnostic snapshot for the log."""
        return (
            f"saw_face={self.saw_face} frames={self._frames} "
            f"max_dev={self._max_dev:.3f} how={self.how or '-'}"
        )
