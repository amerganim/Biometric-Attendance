"""Kiosk / attendance station — the screen teachers walk up to.

The camera is read on the Tk main loop (single reader) and the latest frame is
shared with a background worker thread that runs the heavy recognition + liveness
pipeline, so the live preview never stutters. The worker drives a small state
machine and pushes all UI updates back to the main thread via ``after``.

States:
    SCANNING  -> look for a live, recognized face
    CHALLENGE -> ask the recognized teacher to blink / turn (active liveness)
    RESULT    -> show the saved check-in/out for a few seconds, then cooldown
"""
from __future__ import annotations

import enum
import threading
import time
from datetime import datetime

import customtkinter as ctk

from app.core.attendance_service import AttendanceService, IdentifyStatus, RecordStatus
from app.core.liveness import ActiveChallenge
from app.db.repositories import SettingsRepository
from app.ui._widgets import bgr_to_ctk_image, placeholder_image

PREVIEW_SIZE = (820, 615)
CHALLENGE_TIMEOUT_S = 9.0
RESULT_HOLD_S = 3.5
SCAN_INTERVAL_S = 0.25

# Banner colors (background, text).
_COLORS = {
    "idle": ("#1f2630", "#9aa4b2"),
    "info": ("#2a3a52", "#cfe0ff"),
    "warn": ("#4a3a1f", "#ffe0a3"),
    "bad": ("#4a2222", "#ffb3b3"),
    "good": ("#1f4a2a", "#b3ffc4"),
}


class _State(enum.Enum):
    LOADING = "loading"
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
        top.pack(fill="x", padx=20, pady=(14, 0))
        ctk.CTkLabel(top, text="Attendance Station", font=("", 20, "bold")).pack(side="left")
        self.clock = ctk.CTkLabel(top, text="", font=("", 16))
        self.clock.pack(side="left", padx=20)
        ctk.CTkButton(top, text="Admin", width=90, fg_color="transparent",
                      border_width=1, command=app.show_login).pack(side="right")

        # Status banner.
        self.banner = ctk.CTkFrame(self, height=80, corner_radius=12)
        self.banner.pack(fill="x", padx=20, pady=12)
        self.banner.pack_propagate(False)
        self.banner_text = ctk.CTkLabel(self.banner, text="Starting…", font=("", 26, "bold"))
        self.banner_text.pack(expand=True)

        # Camera preview.
        self.preview = ctk.CTkLabel(self, text="", image=placeholder_image(PREVIEW_SIZE))
        self.preview.pack(pady=(0, 16))

        self._set_banner("Starting…", "idle")
        self._update_clock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_show(self) -> None:
        if not self.app.camera.start():
            self._set_banner("Camera unavailable — check the webcam", "bad")
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
        self.clock.configure(text=datetime.now().strftime("%a %d %b  %H:%M:%S"))
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

    def _set_banner(self, text: str, kind: str) -> None:
        bg, fg = _COLORS[kind]
        self.banner.configure(fg_color=bg)
        self.banner_text.configure(text=text, text_color=fg)

    # ------------------------------------------------------------------
    # Worker thread: recognition + liveness state machine
    # ------------------------------------------------------------------
    def _run_worker(self) -> None:
        self._ui(self._set_banner, "Loading face models…", "info")
        try:
            self.service = AttendanceService()
            # Warm up the model so the first real scan is fast.
            frame = self._wait_for_frame()
            if frame is not None:
                self.service.identify(frame)
        except Exception:  # pragma: no cover
            self._ui(self._set_banner, "Failed to load face models", "bad")
            return

        if self.service.enrolled_count == 0:
            self._ui(self._set_banner, "No teachers enrolled yet — use Admin → Teachers", "warn")
        else:
            self._ui(self._set_banner, "Look at the camera", "idle")

        state = _State.SCANNING
        challenge: ActiveChallenge | None = None
        candidate = None
        deadline = 0.0

        while not self._stop.is_set():
            frame = self._snapshot()
            if frame is None:
                time.sleep(0.05)
                continue

            if state is _State.SCANNING:
                result = self.service.identify(frame)
                if result.status is IdentifyStatus.NO_FACE:
                    self._ui(self._set_banner, "Look at the camera", "idle")
                elif result.status is IdentifyStatus.SPOOF:
                    self._ui(self._set_banner, "⚠ Spoof detected — use a real face", "bad")
                elif result.status is IdentifyStatus.UNKNOWN:
                    self._ui(self._set_banner, "Face not recognized", "warn")
                else:  # RECOGNIZED
                    candidate = result
                    if SettingsRepository.get_bool("active_challenge_enabled", True):
                        challenge = ActiveChallenge()
                        deadline = time.time() + CHALLENGE_TIMEOUT_S
                        state = _State.CHALLENGE
                        self._ui(self._set_banner,
                                 f"{result.teacher_name}: {challenge.prompt}", "info")
                    else:
                        self._commit(candidate, frame)
                        state = _State.RESULT
                        deadline = time.time() + RESULT_HOLD_S
                time.sleep(SCAN_INTERVAL_S)

            elif state is _State.CHALLENGE:
                assert challenge is not None and candidate is not None
                if challenge.update(frame):
                    self._commit(candidate, frame)
                    state = _State.RESULT
                    deadline = time.time() + RESULT_HOLD_S
                elif time.time() > deadline:
                    self._ui(self._set_banner, "Liveness check timed out — try again", "warn")
                    state = _State.SCANNING
                    challenge, candidate = None, None
                    time.sleep(1.0)

            elif state is _State.RESULT:
                if time.time() > deadline:
                    state = _State.SCANNING
                    challenge, candidate = None, None
                    self._ui(self._set_banner, "Look at the camera", "idle")
                else:
                    time.sleep(0.1)

    # ------------------------------------------------------------------
    def _commit(self, candidate, frame) -> None:
        liveness = candidate.passive.score if candidate.passive else None
        outcome = self.service.record(
            candidate.teacher_id, frame, candidate.face, liveness
        )
        if outcome.status is RecordStatus.DUPLICATE:
            self._ui(self._set_banner, outcome.message, "warn")
        else:
            kind = "warn" if outcome.late else "good"
            prefix = "✓ " if not outcome.late else "⏱ "
            self._ui(self._set_banner, prefix + outcome.message, kind)

    def _wait_for_frame(self, timeout: float = 3.0):
        end = time.time() + timeout
        while time.time() < end and not self._stop.is_set():
            frame = self._snapshot()
            if frame is not None:
                return frame
            time.sleep(0.05)
        return None
