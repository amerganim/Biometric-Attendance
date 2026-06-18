"""Settings: work hours, recognition/liveness thresholds, and admin password."""
from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from app.db.repositories import SettingsRepository
from app.security.auth import change_password

# (key, label, hint)
_FIELDS = [
    ("work_start_time", "Work start time (HH:MM)", "Check-ins after this + grace are late"),
    ("late_grace_minutes", "Late grace (minutes)", "Minutes of grace before 'late'"),
    ("recognition_threshold", "Recognition threshold", "Max face distance to accept (lower = stricter)"),
    ("liveness_threshold", "Liveness threshold", "Min anti-spoof score to accept (0–1)"),
    ("duplicate_window_minutes", "Duplicate window (minutes)", "Ignore repeat scans within this window"),
    ("enroll_frames", "Enrollment samples", "Face frames captured per enrollment"),
]


class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, app) -> None:
        super().__init__(parent)
        self.app = app
        if not app.require_admin():
            return

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(20, 6))
        ctk.CTkButton(header, text="← Dashboard", width=110, fg_color="transparent",
                      border_width=1, command=app.show_dashboard).pack(side="left")
        ctk.CTkLabel(header, text="Settings", font=("", 24, "bold")).pack(side="left", padx=16)

        body = ctk.CTkScrollableFrame(self)
        body.pack(fill="both", expand=True, padx=30, pady=10)

        # --- App settings ---
        ctk.CTkLabel(body, text="Attendance Rules", font=("", 18, "bold")).pack(
            anchor="w", pady=(8, 4))
        self.entries: dict[str, ctk.CTkEntry] = {}
        for key, label, hint in _FIELDS:
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", pady=6)
            col = ctk.CTkFrame(row, fg_color="transparent")
            col.pack(side="left")
            ctk.CTkLabel(col, text=label, anchor="w", width=240).pack(anchor="w")
            ctk.CTkLabel(col, text=hint, anchor="w", text_color="gray60",
                         font=("", 11)).pack(anchor="w")
            entry = ctk.CTkEntry(row, width=140)
            entry.insert(0, SettingsRepository.get(key, "") or "")
            entry.pack(side="left", padx=10)
            self.entries[key] = entry

        self.challenge = ctk.CTkCheckBox(body, text="Require active liveness challenge "
                                         "(blink / head-turn) at the kiosk")
        self.challenge.pack(anchor="w", pady=(8, 4))
        if SettingsRepository.get_bool("active_challenge_enabled", True):
            self.challenge.select()

        self.settings_status = ctk.CTkLabel(body, text="", text_color="#98c379")
        self.settings_status.pack(anchor="w", pady=4)
        ctk.CTkButton(body, text="Save Settings", width=160,
                      command=self._save_settings).pack(anchor="w", pady=(2, 18))

        # --- Change password ---
        ctk.CTkLabel(body, text="Change Admin Password", font=("", 18, "bold")).pack(
            anchor="w", pady=(8, 6))
        self.old_pw = self._pw_entry(body, "Current password")
        self.new_pw = self._pw_entry(body, "New password")
        self.confirm_pw = self._pw_entry(body, "Confirm new password")
        self.pw_status = ctk.CTkLabel(body, text="", text_color="#e06c75")
        self.pw_status.pack(anchor="w", pady=4)
        ctk.CTkButton(body, text="Update Password", width=160,
                      command=self._change_password).pack(anchor="w", pady=(2, 10))

    def _pw_entry(self, parent, placeholder) -> ctk.CTkEntry:
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder, show="•", width=300)
        entry.pack(anchor="w", pady=4)
        return entry

    # ------------------------------------------------------------------
    def _save_settings(self) -> None:
        for key, _label, _hint in _FIELDS:
            SettingsRepository.set(key, self.entries[key].get().strip())
        SettingsRepository.set("active_challenge_enabled", "1" if self.challenge.get() else "0")
        self.settings_status.configure(text="Settings saved ✓")

    def _change_password(self) -> None:
        old, new, confirm = self.old_pw.get(), self.new_pw.get(), self.confirm_pw.get()
        if not new or new != confirm:
            self.pw_status.configure(text="New passwords do not match.", text_color="#e06c75")
            return
        if len(new) < 6:
            self.pw_status.configure(text="Use at least 6 characters.", text_color="#e06c75")
            return
        if change_password(self.app.current_admin, old, new):
            self.pw_status.configure(text="Password updated ✓", text_color="#98c379")
            for e in (self.old_pw, self.new_pw, self.confirm_pw):
                e.delete(0, "end")
        else:
            self.pw_status.configure(text="Current password is incorrect.", text_color="#e06c75")
