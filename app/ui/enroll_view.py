"""Face enrollment: capture several good frames of a teacher and store embeddings.

Capture runs on the Tk main loop, spaced a few hundred ms apart, so the preview
stays responsive while each frame is run through the face engine. A frame is only
accepted when exactly one sufficiently large, confident face is present.
"""
from __future__ import annotations

import threading
import time

import customtkinter as ctk

import config
from app.core.face_engine import FaceEngine
from app.db.repositories import SettingsRepository, TeacherRepository
from app.ui._widgets import bgr_to_ctk_image, placeholder_image
from app.utils import images

PREVIEW_SIZE = (640, 480)
MIN_DET_SCORE = 0.6
MIN_FACE_FRACTION = 0.12      # face box width must be >= 12% of frame width
CAPTURE_INTERVAL_S = 0.4


class EnrollView(ctk.CTkFrame):
    def __init__(self, parent, app, teacher_id: str) -> None:
        super().__init__(parent)
        self.app = app
        if not app.require_admin():
            return

        self.teacher = TeacherRepository.get(teacher_id)
        self.engine = FaceEngine.instance()
        self.target_frames = SettingsRepository.get_int("enroll_frames", 5)

        self._capturing = False
        self._last_capture = 0.0
        self._vectors: list[list[float]] = []
        self._best_crop = None
        self._preview_job = None

        # Header.
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(20, 6))
        ctk.CTkButton(header, text="← Teachers", width=110, fg_color="transparent",
                      border_width=1, command=app.show_teachers).pack(side="left")
        name = self.teacher["full_name"] if self.teacher else "Unknown"
        ctk.CTkLabel(header, text=f"Enroll Face — {name}",
                     font=("", 22, "bold")).pack(side="left", padx=16)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=30, pady=10)

        # Camera preview.
        self.preview = ctk.CTkLabel(body, text="", image=placeholder_image(PREVIEW_SIZE))
        self.preview.pack(side="left")

        # Side panel.
        panel = ctk.CTkFrame(body, width=320)
        panel.pack(side="left", fill="both", expand=True, padx=(20, 0))
        ctk.CTkLabel(panel, text="Instructions", font=("", 18, "bold")).pack(
            anchor="w", padx=20, pady=(20, 6))
        ctk.CTkLabel(
            panel, justify="left", text_color="gray75",
            text=("• Face the camera in good lighting.\n"
                  "• Look straight ahead, neutral expression.\n"
                  f"• Click Capture and hold still while we take\n  {self.target_frames} samples."),
        ).pack(anchor="w", padx=20)

        self.progress = ctk.CTkProgressBar(panel, width=260)
        self.progress.set(0)
        self.progress.pack(anchor="w", padx=20, pady=(24, 6))
        self.count_label = ctk.CTkLabel(panel, text=f"0 / {self.target_frames} samples")
        self.count_label.pack(anchor="w", padx=20)

        self.status = ctk.CTkLabel(panel, text="Ready.", text_color="gray70")
        self.status.pack(anchor="w", padx=20, pady=(16, 0))

        self.capture_btn = ctk.CTkButton(panel, text="● Capture", height=44,
                                         command=self._start_capture)
        self.capture_btn.pack(fill="x", padx=20, pady=(24, 8))
        self.save_btn = ctk.CTkButton(panel, text="Save Enrollment", height=44,
                                      state="disabled", command=self._save)
        self.save_btn.pack(fill="x", padx=20)
        if self.teacher and self.teacher["embedding"]:
            ctk.CTkLabel(panel, text="This teacher is already enrolled.\nRe-capturing "
                         "will replace the existing face.", text_color="#e5c07b",
                         justify="left").pack(anchor="w", padx=20, pady=(16, 0))

    # ------------------------------------------------------------------
    def on_show(self) -> None:
        if not self.app.camera.start():
            self.status.configure(text="Camera unavailable.", text_color="#e06c75")
            self.capture_btn.configure(state="disabled")
            return
        self._tick()
        # Pre-load the face model in the background so the first Capture click is
        # instant instead of freezing for a few seconds while the model loads.
        if self.engine._app is None:
            self.capture_btn.configure(state="disabled", text="Preparing…")
            self.status.configure(text="Preparing face recognition…", text_color="gray70")
            threading.Thread(target=self._warmup, daemon=True).start()

    def _warmup(self) -> None:
        try:
            self.engine._ensure_loaded()
        except Exception:
            pass
        # Re-enable Capture on the main thread once the model is ready.
        try:
            self.after(0, self._on_ready)
        except RuntimeError:
            pass  # view destroyed during warmup

    def _on_ready(self) -> None:
        self.capture_btn.configure(state="normal", text="● Capture")
        self.status.configure(text="Ready.", text_color="gray70")

    def on_hide(self) -> None:
        if self._preview_job is not None:
            self.after_cancel(self._preview_job)
            self._preview_job = None
        self.app.camera.stop()

    # ------------------------------------------------------------------
    def _tick(self) -> None:
        frame = self.app.camera.read()
        if frame is not None:
            self.preview.configure(image=bgr_to_ctk_image(frame, PREVIEW_SIZE))
            if self._capturing and (time.time() - self._last_capture) >= CAPTURE_INTERVAL_S:
                self._try_capture(frame)
        self._preview_job = self.after(33, self._tick)

    def _start_capture(self) -> None:
        self._capturing = True
        self._vectors.clear()
        self._best_crop = None
        self.progress.set(0)
        self.count_label.configure(text=f"0 / {self.target_frames} samples")
        self.save_btn.configure(state="disabled")
        self.capture_btn.configure(state="disabled", text="Capturing…")
        self.status.configure(text="Hold still…", text_color="gray70")

    def _try_capture(self, frame) -> None:
        self._last_capture = time.time()
        faces = self.engine.detect(frame)
        if len(faces) != 1:
            self.status.configure(
                text="Make sure exactly one face is visible.", text_color="#e5c07b")
            return
        face = faces[0]
        frame_w = frame.shape[1]
        face_w = face.bbox[2] - face.bbox[0]
        if face.det_score < MIN_DET_SCORE or face_w < MIN_FACE_FRACTION * frame_w:
            self.status.configure(text="Move a bit closer to the camera.",
                                  text_color="#e5c07b")
            return

        self._vectors.append([float(x) for x in face.embedding])
        self._best_crop = images.crop_face(frame, face.bbox)
        done = len(self._vectors)
        self.progress.set(done / self.target_frames)
        self.count_label.configure(text=f"{done} / {self.target_frames} samples")
        self.status.configure(text="Captured ✓", text_color="#98c379")

        if done >= self.target_frames:
            self._capturing = False
            self.capture_btn.configure(state="normal", text="● Re-capture")
            self.save_btn.configure(state="normal")
            self.status.configure(text="Done — click Save Enrollment.",
                                  text_color="#98c379")

    def _save(self) -> None:
        if not self._vectors or self._best_crop is None or not self.teacher:
            return
        thumb = images.save_thumbnail(self._best_crop, prefix="enroll_" + self.teacher["id"][:8])
        TeacherRepository.set_embedding(self.teacher["id"], self._vectors, thumb)
        self.status.configure(text="Enrollment saved.", text_color="#98c379")
        self.save_btn.configure(state="disabled")
        self.after(700, self.app.show_teachers)
