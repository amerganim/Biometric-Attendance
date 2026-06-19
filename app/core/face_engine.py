"""Face detection + recognition via insightface (ArcFace embeddings on ONNX CPU).

Wraps insightface's ``FaceAnalysis`` model pack (``buffalo_l`` = RetinaFace detector
+ ArcFace r50 recognizer). Embeddings are L2-normalized 512-float vectors, so cosine
*similarity* is just a dot product and cosine *distance* is ``1 - similarity``.

The model loads lazily on first use (the first call downloads/caches the pack under
the insightface home dir) so importing this module stays cheap.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

import config


@dataclass
class DetectedFace:
    bbox: np.ndarray            # [x1, y1, x2, y2]
    kps: np.ndarray             # 5 facial landmarks
    embedding: np.ndarray       # L2-normalized 512-float vector
    det_score: float            # detector confidence


@dataclass
class MatchResult:
    teacher_id: str
    distance: float             # cosine distance to the closest enrolled sample


class FaceEngine:
    """Singleton-ish wrapper; construct once and reuse across the app."""

    _instance: Optional["FaceEngine"] = None

    def __init__(self) -> None:
        self._app = None  # insightface FaceAnalysis, loaded lazily
        self._load_lock = threading.Lock()

    @classmethod
    def instance(cls) -> "FaceEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _ensure_loaded(self) -> None:
        if self._app is not None:
            return
        # The kiosk worker thread and the enrollment screen can both reach here;
        # the lock + double-check makes the heavy load happen exactly once.
        with self._load_lock:
            if self._app is not None:
                return
            from insightface.app import FaceAnalysis  # heavy import, deferred

            # Load ONLY the detection + recognition models. We use the bounding
            # box, 5 keypoints, and embedding — never the 2D/3D landmark or
            # age/gender models. Skipping them is faster, lighter, and avoids a
            # landmark-model crash that surfaced in the packaged build.
            app = FaceAnalysis(
                name=config.INSIGHTFACE_MODEL_PACK,
                providers=["CPUExecutionProvider"],
                allowed_modules=["detection", "recognition"],
            )
            app.prepare(ctx_id=-1, det_size=(640, 640))  # ctx_id=-1 -> CPU
            self._app = app

    # ------------------------------------------------------------------
    # Detection / embedding
    # ------------------------------------------------------------------
    def detect(self, frame_bgr: np.ndarray) -> list[DetectedFace]:
        """Detect all faces in a BGR frame."""
        self._ensure_loaded()
        faces = self._app.get(frame_bgr)
        results: list[DetectedFace] = []
        for f in faces:
            results.append(
                DetectedFace(
                    bbox=f.bbox,
                    kps=f.kps,
                    embedding=f.normed_embedding,
                    det_score=float(f.det_score),
                )
            )
        return results

    def largest_face(self, frame_bgr: np.ndarray) -> Optional[DetectedFace]:
        """Return the largest detected face, or None. Useful for kiosk/enroll where
        we expect exactly one person at the camera."""
        faces = self.detect(frame_bgr)
        if not faces:
            return None
        return max(faces, key=_bbox_area)


# ---------------------------------------------------------------------------
# Matching helpers (pure functions; no model needed)
# ---------------------------------------------------------------------------
def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine distance for L2-normalized vectors (0 = identical, 2 = opposite)."""
    return float(1.0 - np.dot(a, b))


def match_embedding(
    embedding: np.ndarray,
    enrolled: Sequence[tuple[str, list[list[float]]]],
    threshold: float,
) -> Optional[MatchResult]:
    """Match a query embedding against enrolled teachers.

    ``enrolled`` is a sequence of ``(teacher_id, [vector, ...])`` pairs. Each teacher
    may have several enrollment samples; we take the closest one. Returns the best
    match whose distance is within ``threshold``, else None.
    """
    best: Optional[MatchResult] = None
    for teacher_id, vectors in enrolled:
        for vec in vectors:
            dist = cosine_distance(embedding, np.asarray(vec, dtype=np.float32))
            if best is None or dist < best.distance:
                best = MatchResult(teacher_id=teacher_id, distance=dist)
    if best is not None and best.distance <= threshold:
        return best
    return None


def _bbox_area(face: DetectedFace) -> float:
    x1, y1, x2, y2 = face.bbox[:4]
    return float((x2 - x1) * (y2 - y1))
