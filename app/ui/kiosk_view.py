"""Kiosk / attendance station — the screen teachers walk up to.

The camera is read on the Tk main loop (single reader) and the latest frame is
shared with a background worker thread that runs the heavy recognition + liveness
pipeline, so the live preview never stutters. The worker drives a small state
machine and pushes all UI updates back to the main thread via ``after``.

Flow shown to the user:
    1. Step up            -> "Step up to mark attendance"
    2. Recognized         -> "Hi <name> — please blink to confirm"
    3. Liveness verified  -> record attendance
    4. Done               -> "Attendance recorded · Checked IN · 09:05 AM"
"""
from __future__ import annotations

import enum
import logging
import threading
import time
from datetime import datetime

import customtkinter as ctk

from app.core.attendance_service import AttendanceService, IdentifyStatus, RecordStatus
from app.core.liveness import ActiveChallenge
from app.db.repositories import SettingsRepository
from app.ui._widgets import bgr_to_ctk_image, placeholder_image

log = logging.getLogger(__name__)

PREVIEW_SIZE = (720, 405)
CHALLENGE_TIMEOUT_S = 12.0
RESULT_HOLD_S = 4.0
SCAN_INTERVAL_S = 0.2

# Status card colors (background, primary-text).
_COLORS = {
    "idle": ("#1f2630", "#d6dee9"),
    "info": ("#22344f", "#cfe0ff"),
    "warn": ("#4a3a1f", "#ffe0a3"),
    "bad": ("#4a2222", "#ffb3b3"),
    "good": ("#15401f", "#b6ffc6"),
}


class _State(enum.Enum):
    SCANNING = "scanning"
    CHALLENGE = "challenge"
    RESULT = "result"


class KioskView(ctk.CTkFrame):
    def __init__(self, parent, app) -> None:
        super().__init__(parent)
        self.app = app

        self._frame_lock = threading.Lock()
        self._latest = None
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._preview_job = None
        self.service: AttendanceService | None = None

        # Top bar.
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=24, pady=(14, 0))
        ctk.CTkLabel(top, text="📷  Attendance Station",
                     font=("", 20, "bold")).pack(side="left")
        self.clock = ctk.CTkLabel(top, text="", font=("", 15), text_color="gray70")
        self.clock.pack(side="left", padx=18)
        ctk.CTkButton(top, text="Admin", width=90, fg_color="transparent",
                      border_width=1, command=app.show_login).pack(side="right")

        # Status card (two lines: primary + secondary).
        self.card = ctk.CTkFrame(self, height=140, corner_radius=16)
        self.card.pack(fill="x", padx=24, pady=14)
        self.card.pack_propagate(False)
        self.primary = ctk.CTkLabel(self.card, text="Starting…", font=("", 30, "bold"))
        self.primary.pack(expand=True, pady=(22, 0))
        self.secondary = ctk.CTkLabel(self.card, text="", font=("", 16))
        self.secondary.pack(expand=True, pady=(0, 20))

        # Camera preview.
        self.preview = ctk.CTkLabel(self, text="", image=placeholder_image(PREVIEW_SIZE))
        self.preview.pack(pady=(0, 14))

        self._show("Starting…", "Please wait", "idle")
        self._update_clock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_show(self) -> None:
        if not self.app.camera.start():
            self._show("Camera unavailable", "Check that the webcam is connected", "bad")
            return
        self._stop.clear()
        self._tick()
        self._worker = threading.Thread(target=self._run_worker, daemon=True)
        self._worker.start()

    def on_hide(self) -> None:
        self._stop.set()
        if self._preview_job is not None:
            self.after_cancel(self._preview_job)
            self._preview_job = None
        if self._worker is not None:
            self._worker.join(timeout=2.0)
            self._worker = None
        self.app.camera.stop()

    # ------------------------------------------------------------------
    # Main-thread loops
    # ------------------------------------------------------------------
    def _tick(self) -> None:
        frame = self.app.camera.read()
        if frame is not None:
            with self._frame_lock:
                self._latest = frame
            self.preview.configure(image=bgr_to_ctk_image(frame, PREVIEW_SIZE))
        self._preview_job = self.after(33, self._tick)

    def _update_clock(self) -> None:
        self.clock.configure(text=datetime.now().strftime("%a %d %b · %I:%M:%S %p"))
        self.after(1000, self._update_clock)

    def _snapshot(self):
        with self._frame_lock:
            return None if self._latest is None else self._latest.copy()

    # Thread-safe UI helpers (scheduled onto the main loop).
    def _ui(self, fn, *args) -> None:
        try:
            self.after(0, lambda: fn(*args))
        except RuntimeError:
            pass  # window closing

    def _show(self, primary: str, secondary: str, kind: str) -> None:
        bg, fg = _COLORS[kind]
        self.card.configure(fg_color=bg)
        self.primary.configure(text=primary, text_color=fg)
        self.secondary.configure(text=secondary, text_color=fg)

    # ------------------------------------------------------------------
    # Worker thread: recognition + liveness state machine
    # ------------------------------------------------------------------
    def _run_worker(self) -> None:
        self._ui(self._show, "Please wait", "Loading face recognition…", "info")
        try:
            self.service = AttendanceService()
            frame = self._wait_for_frame()
            if frame is not None:
                self.service.identify(frame)  # warm up so the first scan is fast
        except Exception:
            log.exception("Failed to initialise attendance service")
            self._ui(self._show, "Setup error", "Could not load face models", "bad")
            return

        if self.service.enrolled_count == 0:
            self._ui(self._show, "No teachers enrolled yet",
                     "Ask the administrator to register faces", "warn")
        else:
            self._ui(self._show, "👋 Step up to mark attendance",
                     "Look directly at the camera", "idle")

        state = _State.SCANNING
        challenge: ActiveChallenge | None = None
        candidate = None
        deadline = 0.0

        while not self._stop.is_set():
            frame = self._snapshot()
            if frame is None:
                time.sleep(0.05)
                continue
            try:
                if state is _State.SCANNING:
                    candidate, challenge, state, deadline = self._scan(frame)
                elif state is _State.CHALLENGE:
                    state, deadline = self._challenge(frame, challenge, candidate, deadline)
                    if state is _State.SCANNING:
                        challenge, candidate = None, None
                elif state is _State.RESULT:
                    if time.time() > deadline:
                        state = _State.SCANNING
                        challenge, candidate = None, None
                        self._ui(self._show, "👋 Step up to mark attendance",
                                 "Look directly at the camera", "idle")
                    else:
                        time.sleep(0.1)
            except Exception:
                log.exception("Kiosk worker iteration failed; recovering")
                state, challenge, candidate = _State.SCANNING, None, None
                time.sleep(0.5)

    # ------------------------------------------------------------------
    def _scan(self, frame):
        """SCANNING: look for a live, recognized face. Returns next-state tuple."""
        result = self.service.identify(frame)
        next_state = _State.SCANNING
        challenge = None
        candidate = None
        deadline = 0.0

        if result.status is IdentifyStatus.NO_FACE:
            self._ui(self._show, "👋 Step up to mark attendance",
                     "Look directly at the camera", "idle")
        elif result.status is IdentifyStatus.SPOOF:
            self._ui(self._show, "Liveness check failed",
                     "Please use your real face, not a photo or screen", "bad")
        elif result.status is IdentifyStatus.UNKNOWN:
            self._ui(self._show, "Face not recognized",
                     "Please contact the administrator to enroll", "warn")
        else:  # RECOGNIZED
            candidate = result
            if SettingsRepository.get_bool("active_challenge_enabled", True):
                challenge = ActiveChallenge()
                deadline = time.time() + CHALLENGE_TIMEOUT_S
                next_state = _State.CHALLENGE
                self._ui(self._show, f"Hi {result.teacher_name}!",
                         f"Please {challenge.prompt} to confirm", "info")
            else:
                self._commit(candidate, frame)
                next_state = _State.RESULT
                deadline = time.time() + RESULT_HOLD_S

        time.sleep(SCAN_INTERVAL_S)
        return candidate, challenge, next_state, deadline

    def _challenge(self, frame, challenge, candidate, deadline):
        """CHALLENGE: verify the active liveness response. Returns (state, deadline).

        Uses a fast detection-only pass (keypoints only, no recognition embedding)
        so a normal-speed head turn is sampled often enough to register — no need
        to move slowly.
        """
        kps = self.service.engine.largest_face_kps(frame)
        if challenge.update_kps(kps):
            log.info("Liveness passed for %s (%s)", candidate.teacher_name, challenge.summary())
            self._commit(candidate, frame)
            return _State.RESULT, time.time() + RESULT_HOLD_S
        if time.time() > deadline:
            log.info("Liveness timed out for %s (%s)", candidate.teacher_name, challenge.summary())
            self._ui(self._show, "Let's try again",
                     "Look at the camera and follow the prompt", "warn")
            time.sleep(1.2)
            return _State.SCANNING, 0.0
        time.sleep(0.02)  # detection-only is fast; sample frequently to catch quick turns
        return _State.CHALLENGE, deadline

    # ------------------------------------------------------------------
    def _commit(self, candidate, frame) -> None:
        liveness = candidate.passive.score if candidate.passive else None
        outcome = self.service.record(
            candidate.teacher_id, frame, candidate.face, liveness
        )
        name = candidate.teacher_name or "Teacher"
        now = datetime.now().strftime("%I:%M %p").lstrip("0")

        if outcome.status is RecordStatus.DUPLICATE:
            self._ui(self._show, "You're already checked in",
                     f"{name}, you're all set — see you later!", "info")
            return

        # New record saved — push it to the cloud right away (if sync is enabled),
        # instead of waiting for the periodic timer.
        sync = getattr(self.app, "sync_service", None)
        if sync is not None:
            sync.request_sync()

        action = "Checked IN" if outcome.check_type == "in" else "Checked OUT"
        if outcome.late:
            self._ui(self._show, "✓ Attendance recorded (Late)",
                     f"{name} · {action} · {now}", "warn")
        else:
            self._ui(self._show, "✓ Attendance recorded",
                     f"{name} · {action} · {now}", "good")

    def _wait_for_frame(self, timeout: float = 3.0):
        end = time.time() + timeout
        while time.time() < end and not self._stop.is_set():
            frame = self._snapshot()
            if frame is not None:
                return frame
            time.sleep(0.05)
        return None
