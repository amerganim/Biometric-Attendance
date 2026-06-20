"""Attendance business logic: recognition + liveness -> a saved attendance record.

This is the "brain" the kiosk worker thread calls each frame. It is deliberately
free of any UI so it can be unit-tested headlessly. Two stages:

* ``identify(frame)`` — detect the largest face, run passive anti-spoof, and match
  it to an enrolled teacher. Returns a rich result the kiosk uses to drive its state
  machine (and to know whether to start the active challenge).
* ``record(...)`` — apply in/out + late + duplicate rules and persist the row plus an
  audit thumbnail.

The enrolled-teacher list is cached and must be refreshed (``reload_enrolled``) after
enrollment changes.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional

import numpy as np

from app.core.face_engine import DetectedFace, FaceEngine, MatchResult, match_embedding
from app.core.liveness import PassiveLiveness, PassiveResult
from app.db.repositories import (
    AttendanceRepository,
    SettingsRepository,
    TeacherRepository,
)
from app.utils import images


class IdentifyStatus(enum.Enum):
    NO_FACE = "no_face"
    SPOOF = "spoof"            # passive anti-spoof rejected the face
    UNKNOWN = "unknown"       # live face but not matched to any teacher
    RECOGNIZED = "recognized"


@dataclass
class IdentifyResult:
    status: IdentifyStatus
    face: Optional[DetectedFace] = None
    teacher_id: Optional[str] = None
    teacher_name: Optional[str] = None
    distance: Optional[float] = None
    passive: Optional[PassiveResult] = None


class RecordStatus(enum.Enum):
    SAVED = "saved"
    DUPLICATE = "duplicate"   # within the duplicate window; ignored


@dataclass
class RecordResult:
    status: RecordStatus
    check_type: Optional[str] = None      # 'in' | 'out'
    late: bool = False
    message: str = ""


class AttendanceService:
    def __init__(self) -> None:
        self.engine = FaceEngine.instance()
        self.passive = PassiveLiveness()
        self._enrolled: list[tuple[str, list[list[float]], str]] = []
        self.reload_enrolled()

    # ------------------------------------------------------------------
    def reload_enrolled(self) -> None:
        """Refresh the in-memory cache of (teacher_id, vectors, name)."""
        rows = TeacherRepository.list_enrolled()
        self._enrolled = [
            (r["id"], TeacherRepository.parse_embedding(r), r["full_name"]) for r in rows
        ]

    @property
    def enrolled_count(self) -> int:
        return len(self._enrolled)

    def _name_for(self, teacher_id: str) -> Optional[str]:
        for tid, _vecs, name in self._enrolled:
            if tid == teacher_id:
                return name
        return None

    # ------------------------------------------------------------------
    def identify(self, frame_bgr: np.ndarray) -> IdentifyResult:
        """Detect + anti-spoof + match the largest face in a frame."""
        face = self.engine.largest_face(frame_bgr)
        if face is None:
            return IdentifyResult(status=IdentifyStatus.NO_FACE)

        liveness_threshold = SettingsRepository.get_float("liveness_threshold", 0.5)
        passive = self.passive.score(frame_bgr, face.bbox)
        if passive.available and passive.score < liveness_threshold:
            return IdentifyResult(status=IdentifyStatus.SPOOF, face=face, passive=passive)

        threshold = SettingsRepository.get_float("recognition_threshold", 0.42)
        pairs = [(tid, vecs) for tid, vecs, _name in self._enrolled]
        match: Optional[MatchResult] = match_embedding(face.embedding, pairs, threshold)
        if match is None:
            return IdentifyResult(
                status=IdentifyStatus.UNKNOWN, face=face, passive=passive
            )
        return IdentifyResult(
            status=IdentifyStatus.RECOGNIZED,
            face=face,
            teacher_id=match.teacher_id,
            teacher_name=self._name_for(match.teacher_id),
            distance=match.distance,
            passive=passive,
        )

    # ------------------------------------------------------------------
    def record(
        self,
        teacher_id: str,
        frame_bgr: np.ndarray,
        face: Optional[DetectedFace],
        liveness_score: Optional[float],
    ) -> RecordResult:
        """Apply in/out, late, and duplicate rules, then persist the record."""
        now = datetime.now()
        today = now.date().isoformat()
        name = self._name_for(teacher_id) or "Teacher"

        # Duplicate suppression.
        window = SettingsRepository.get_int("duplicate_window_minutes", 2)
        last = AttendanceRepository.last_for_teacher_on(teacher_id, today)
        if last is not None and window > 0:
            last_ts = datetime.fromisoformat(last["timestamp"])
            if now - last_ts < timedelta(minutes=window):
                return RecordResult(
                    status=RecordStatus.DUPLICATE,
                    message=f"{name}: already recorded a moment ago",
                )

        # in/out: first scan of the day is 'in'; otherwise toggle from the last one.
        if last is None:
            check_type = "in"
        else:
            check_type = "out" if last["check_type"] == "in" else "in"

        # Late only applies to check-in.
        late = check_type == "in" and self._is_late(now)
        status = "late" if late else "present"

        # Audit thumbnail (face crop if we have a box, else full frame).
        crop = images.crop_face(frame_bgr, face.bbox) if face is not None else frame_bgr
        thumb_path = images.save_thumbnail(crop, prefix=teacher_id[:8])

        AttendanceRepository.create(
            teacher_id=teacher_id,
            check_type=check_type,
            status=status,
            liveness_score=liveness_score,
            thumbnail_path=thumb_path,
        )
        verb = "checked IN" if check_type == "in" else "checked OUT"
        suffix = " (LATE)" if late else ""
        return RecordResult(
            status=RecordStatus.SAVED,
            check_type=check_type,
            late=late,
            message=f"{name} {verb}{suffix}",
        )

    # ------------------------------------------------------------------
    def _is_late(self, now: datetime) -> bool:
        start_str = SettingsRepository.get("work_start_time", "09:00")
        grace = SettingsRepository.get_int("late_grace_minutes", 0)
        try:
            hh, mm = (int(x) for x in start_str.split(":"))
            deadline = datetime.combine(now.date(), time(hh, mm)) + timedelta(minutes=grace)
        except (ValueError, AttributeError):
            return False
        return now > deadline
