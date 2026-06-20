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
# Passive anti-spoof (MiniVision Silent-Face, ONNX) — bundled, optional.
# ---------------------------------------------------------------------------
# Two models ensembled exactly like MiniVision: each takes the face crop expanded
# by its own scale, resized to 80x80 (BGR, raw 0-255 floats — MiniVision does NOT
# divide by 255), outputting a 3-class softmax where class 1 = "real". We average
# the real-probability of both models.
_ANTISPOOF_MODELS = (("antispoof_2_7.onnx", 2.7), ("antispoof_4_0.onnx", 4.0))
_ANTISPOOF_INPUT = 80


@dataclass
class PassiveResult:
    score: float          # probability the face is real [0..1]
    available: bool       # False when no model is installed (score is neutral)


def _crop_for_antispoof(img: np.ndarray, bbox, scale: float, out_size: int) -> np.ndarray:
    """Replicate MiniVision's CropImage: a centered crop expanded by ``scale`` and
    clamped to the image, resized to ``out_size`` square. ``bbox`` is [x, y, w, h];
    BGR is kept (the model was trained on BGR)."""
    import cv2

    src_h, src_w = img.shape[:2]
    x, y, w, h = bbox
    if w <= 0 or h <= 0:
        return cv2.resize(img, (out_size, out_size))
    scale = min((src_h - 1) / h, (src_w - 1) / w, scale)
    new_w, new_h = w * scale, h * scale
    cx, cy = x + w / 2.0, y + h / 2.0
    ltx, lty = cx - new_w / 2.0, cy - new_h / 2.0
    rbx, rby = cx + new_w / 2.0, cy + new_h / 2.0
    if ltx < 0:
        rbx -= ltx; ltx = 0
    if lty < 0:
        rby -= lty; lty = 0
    if rbx > src_w - 1:
        ltx -= rbx - src_w + 1; rbx = src_w - 1
    if rby > src_h - 1:
        lty -= rby - src_h + 1; rby = src_h - 1
    crop = img[int(lty):int(rby) + 1, int(ltx):int(rbx) + 1]
    if crop.size == 0:
        return cv2.resize(img, (out_size, out_size))
    return cv2.resize(crop, (out_size, out_size))


class PassiveLiveness:
    """MiniVision Silent-Face anti-spoof ensemble (ONNX). Degrades gracefully to
    'unavailable' (neutral score) if the model files aren't present."""

    def __init__(self) -> None:
        self._sessions: list = []   # (session, input_name, scale)
        self._tried = False

    def _ensure_loaded(self) -> bool:
        if self._tried:
            return bool(self._sessions)
        self._tried = True
        try:
            import onnxruntime as ort
        except Exception:
            return False
        for name, scale in _ANTISPOOF_MODELS:
            path = config.antispoof_model_path(name)
            if not path:
                continue
            try:
                sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
                self._sessions.append((sess, sess.get_inputs()[0].name, scale))
            except Exception:
                pass
        return bool(self._sessions)

    def score(self, frame_bgr: np.ndarray, bbox) -> PassiveResult:
        """Score the face at ``bbox`` (x1, y1, x2, y2) in the full frame as real."""
        if not self._ensure_loaded():
            return PassiveResult(score=1.0, available=False)
        try:
            x1, y1, x2, y2 = (int(v) for v in bbox[:4])
            mv_bbox = [x1, y1, x2 - x1, y2 - y1]
            total = 0.0
            for sess, input_name, scale in self._sessions:
                crop = _crop_for_antispoof(frame_bgr, mv_bbox, scale, _ANTISPOOF_INPUT)
                # MiniVision feeds raw 0-255 floats (no /255 normalization).
                blob = crop.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)
                out = sess.run(None, {input_name: blob})[0]
                probs = _softmax(np.asarray(out).ravel())
                total += float(probs[1])  # class 1 = real
            return PassiveResult(score=total / len(self._sessions), available=True)
        except Exception:
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
