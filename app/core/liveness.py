"""Liveness detection: layered anti-spoofing.

Two independent layers that fail differently:

1. **Passive anti-spoof** (``PassiveLiveness``) — a Silent-Face style ONNX model that
   scores a face crop as real vs. a presentation attack (printed photo / phone
   screen) without asking the user to do anything. If no model file is installed it
   degrades gracefully: it reports ``available = False`` and a neutral score, and the
   attendance service falls back to the active challenge alone. Drop a converted
   Silent-Face ONNX model at ``data/models/antispoof.onnx`` to enable it.

2. **Active challenge** (``ActiveChallenge``) — randomly asks the user to BLINK or
   TURN their head, verified via mediapipe FaceMesh landmarks. Because the prompt is
   random, a pre-recorded video of someone else won't satisfy it.
"""
from __future__ import annotations

import enum
import random
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
# Active challenge (mediapipe FaceMesh)
# ---------------------------------------------------------------------------
# FaceMesh landmark indices for Eye Aspect Ratio (EAR).
_RIGHT_EYE = [33, 160, 158, 133, 153, 144]
_LEFT_EYE = [362, 385, 387, 263, 373, 380]

# Blink/turn detection is adaptive (relative to each person), so these are ratios
# rather than absolute thresholds — far more reliable across cameras and faces.
BLINK_CLOSE_RATIO = 0.72        # eye counts as "closed" below this fraction of its open size
MIN_OPEN_EAR = 0.15             # need a plausibly-open eye before a blink can count
TURN_DELTA = 0.10               # change in nose-offset that counts as a head turn
WARMUP_FRAMES = 3               # frames to establish the open-eye / centered baseline


class ChallengeType(enum.Enum):
    BLINK = "blink"
    TURN = "turn"


class _FaceMesh:
    """Lazy mediapipe FaceMesh wrapper returning normalized landmark arrays."""

    def __init__(self) -> None:
        self._mesh = None

    def _ensure(self) -> None:
        if self._mesh is None:
            import mediapipe as mp

            self._mesh = mp.solutions.face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )

    def landmarks(self, frame_bgr: np.ndarray) -> Optional[np.ndarray]:
        """Return (468+, 3) normalized landmarks for the first face, or None.

        Never raises — any mediapipe failure yields None so the kiosk worker keeps
        running instead of dying mid-challenge.
        """
        try:
            self._ensure()
            import cv2

            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            result = self._mesh.process(rgb)
            if not result.multi_face_landmarks:
                return None
            lm = result.multi_face_landmarks[0].landmark
            return np.array([[p.x, p.y, p.z] for p in lm], dtype=np.float32)
        except Exception:
            return None


def eye_aspect_ratio(landmarks: np.ndarray, eye: list[int]) -> float:
    p = landmarks[eye][:, :2]
    vert = np.linalg.norm(p[1] - p[5]) + np.linalg.norm(p[2] - p[4])
    horiz = 2.0 * np.linalg.norm(p[0] - p[3])
    return float(vert / horiz) if horiz > 0 else 0.0


def head_turn_ratio(landmarks: np.ndarray) -> float:
    """How far the nose sits toward one eye, 0.5 = centered, ->0/1 = turned.

    Uses nose tip (1) projected between the outer eye corners (33, 263).
    """
    left = landmarks[33][0]
    right = landmarks[263][0]
    nose = landmarks[1][0]
    span = right - left
    if abs(span) < 1e-6:
        return 0.5
    return float((nose - left) / span)


class ActiveChallenge:
    """Stateful single-challenge verifier. Feed it frames via ``update``.

    Detection is **adaptive**: it first observes a few frames to learn the person's
    open-eye size / centered head position, then looks for a relative change (an eye
    closing, or the head turning). This works reliably across different faces,
    cameras, and lighting without hand-tuned absolute thresholds.
    """

    def __init__(self, challenge_type: Optional[ChallengeType] = None) -> None:
        self.type = challenge_type or random.choice(list(ChallengeType))
        self._mesh = _FaceMesh()
        self.passed = False
        self.saw_face = False        # True once landmarks have been detected at all
        self._frames = 0
        self._ear_open = 0.0         # running max open-eye EAR (the baseline)
        self._yaw_base: Optional[float] = None

    @property
    def prompt(self) -> str:
        return "blink" if self.type is ChallengeType.BLINK else "turn your head"

    def update(self, frame_bgr: np.ndarray) -> bool:
        """Process one frame; returns True once the challenge has been satisfied."""
        if self.passed:
            return True
        landmarks = self._mesh.landmarks(frame_bgr)
        if landmarks is None:
            return False
        self.saw_face = True
        self._frames += 1

        try:
            if self.type is ChallengeType.BLINK:
                ear = (
                    eye_aspect_ratio(landmarks, _LEFT_EYE)
                    + eye_aspect_ratio(landmarks, _RIGHT_EYE)
                ) / 2.0
                # Learn the open-eye size, then detect a clear drop (a blink).
                self._ear_open = max(self._ear_open, ear)
                if (
                    self._frames >= WARMUP_FRAMES
                    and self._ear_open >= MIN_OPEN_EAR
                    and ear < BLINK_CLOSE_RATIO * self._ear_open
                ):
                    self.passed = True
            else:  # TURN
                ratio = head_turn_ratio(landmarks)
                if self._yaw_base is None:
                    self._yaw_base = ratio
                if self._frames >= WARMUP_FRAMES and abs(ratio - self._yaw_base) >= TURN_DELTA:
                    self.passed = True
        except Exception:
            return False

        return self.passed
