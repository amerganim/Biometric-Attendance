"""Settings: work hours, recognition/liveness thresholds, cloud sync, password."""
from __future__ import annotations

import threading
from tkinter import messagebox

import customtkinter as ctk

from app.db.repositories import SettingsRepository
from app.security.auth import (
    change_password,
    has_setup_password,
    set_setup_password,
    verify_setup_password,
)
from app.sync.sync_service import perform_sync

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

        # --- Cloud sync ---
        # The URL + service key are locked behind a separate "developer password"
        # so the college admin can't accidentally change them. Locked whenever a
        # developer password has been set (and not yet unlocked this visit).
        self._cloud_locked = has_setup_password()

        ctk.CTkLabel(body, text="Cloud Sync", font=("", 18, "bold")).pack(
            anchor="w", pady=(8, 2))
        ctk.CTkLabel(body, text="Push attendance to Supabase so it can be viewed in the "
                     "web dashboard. See supabase/README.md for setup.",
                     text_color="gray60", font=("", 11), justify="left").pack(
            anchor="w", pady=(0, 8))

        # Lock status + unlock / set-password controls.
        lock_row = ctk.CTkFrame(body, fg_color="transparent")
        lock_row.pack(anchor="w", pady=(0, 8), fill="x")
        self.lock_label = ctk.CTkLabel(lock_row, text="", font=("", 12))
        self.lock_label.pack(side="left")
        self.unlock_btn = ctk.CTkButton(lock_row, text="Unlock", width=90,
                                        command=self._unlock_cloud)
        self.unlock_btn.pack(side="left", padx=8)
        self.devpw_btn = ctk.CTkButton(lock_row, text="Set developer password",
                                       width=190, fg_color="transparent",
                                       border_width=1, command=self._set_dev_password)
        self.devpw_btn.pack(side="left", padx=4)

        ctk.CTkLabel(body, text="Supabase Project URL", anchor="w").pack(
            anchor="w", padx=2)
        self.sb_url = ctk.CTkEntry(body, width=460,
                                   placeholder_text="https://xxxx.supabase.co")
        self.sb_url.insert(0, SettingsRepository.get("supabase_url", "") or "")
        self.sb_url.pack(anchor="w", pady=(0, 6))

        ctk.CTkLabel(body, text="service_role key (kept on this laptop only)",
                     anchor="w").pack(anchor="w", padx=2)
        self.sb_key = ctk.CTkEntry(body, width=460, show="•",
                                   placeholder_text="paste the service_role key")
        self.sb_key.insert(0, SettingsRepository.get("supabase_service_key", "") or "")
        self.sb_key.pack(anchor="w", pady=(0, 6))

        self.sync_enabled = ctk.CTkCheckBox(body, text="Enable automatic cloud sync")
        self.sync_enabled.pack(anchor="w", pady=(4, 4))
        if SettingsRepository.get_bool("sync_enabled", False):
            self.sync_enabled.select()

        sync_row = ctk.CTkFrame(body, fg_color="transparent")
        sync_row.pack(anchor="w", pady=(2, 2), fill="x")
        self.save_cloud_btn = ctk.CTkButton(sync_row, text="Save Cloud Settings",
                                            width=170, command=self._save_cloud)
        self.save_cloud_btn.pack(side="left")
        # "Sync now" stays available to the admin even when settings are locked.
        self.sync_now_btn = ctk.CTkButton(sync_row, text="Sync now", width=120,
                                          command=self._sync_now)
        self.sync_now_btn.pack(side="left", padx=8)

        last = SettingsRepository.get("last_sync_status", "") or "Never synced"
        self.sync_status = ctk.CTkLabel(body, text=last, text_color="gray70")
        self.sync_status.pack(anchor="w", pady=(2, 18))

        self._apply_cloud_lock()

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

    # ------------------------------------------------------------------
    # Cloud settings lock (developer password)
    # ------------------------------------------------------------------
    def _apply_cloud_lock(self) -> None:
        """Enable/disable the cloud credential fields based on lock state."""
        editable = not self._cloud_locked
        state = "normal" if editable else "disabled"
        self.sb_url.configure(state=state)
        self.sb_key.configure(state=state)
        self.save_cloud_btn.configure(state=state)
        if not has_setup_password():
            self.lock_label.configure(
                text="⚠ Not protected — set a developer password before handover",
                text_color="#e5c07b")
            self.unlock_btn.configure(state="disabled")
            self.devpw_btn.configure(text="Set developer password")
        elif self._cloud_locked:
            self.lock_label.configure(text="🔒 Locked (developer only)",
                                      text_color="gray70")
            self.unlock_btn.configure(state="normal")
            self.devpw_btn.configure(state="disabled")
        else:
            self.lock_label.configure(text="🔓 Unlocked", text_color="#98c379")
            self.unlock_btn.configure(state="disabled")
            self.devpw_btn.configure(state="normal", text="Change developer password")

    def _ask_password(self, title: str) -> str | None:
        dlg = ctk.CTkInputDialog(text=f"{title}:", title="Developer Password")
        value = dlg.get_input()
        return value.strip() if value else None

    def _unlock_cloud(self) -> None:
        pw = self._ask_password("Enter developer password to unlock")
        if pw is None:
            return
        if verify_setup_password(pw):
            self._cloud_locked = False
            self._apply_cloud_lock()
        else:
            self.sync_status.configure(text="Wrong developer password.",
                                       text_color="#e06c75")

    def _set_dev_password(self) -> None:
        # If one already exists, require it before changing.
        if has_setup_password():
            current = self._ask_password("Enter CURRENT developer password")
            if current is None:
                return
            if not verify_setup_password(current):
                self.sync_status.configure(text="Wrong developer password.",
                                           text_color="#e06c75")
                return
        new = self._ask_password("Set a NEW developer password (min 6 chars)")
        if new is None:
            return
        if len(new) < 6:
            self.sync_status.configure(text="Developer password too short (min 6).",
                                       text_color="#e06c75")
            return
        set_setup_password(new)
        self._cloud_locked = True  # lock immediately after setting
        self._apply_cloud_lock()
        self.sync_status.configure(text="Developer password set — cloud settings locked ✓",
                                   text_color="#98c379")

    def _save_cloud(self) -> None:
        if self._cloud_locked:
            return  # guarded; fields are disabled anyway
        SettingsRepository.set("supabase_url", self.sb_url.get().strip())
        SettingsRepository.set("supabase_service_key", self.sb_key.get().strip())
        SettingsRepository.set("sync_enabled", "1" if self.sync_enabled.get() else "0")
        self.sync_status.configure(text="Cloud settings saved ✓", text_color="#98c379")
        # Nudge the background scheduler to pick up the new settings immediately.
        if getattr(self.app, "sync_service", None) is not None:
            self.app.sync_service.request_sync()

    def _sync_now(self) -> None:
        # Save first so the sync uses the current field values.
        self._save_cloud()
        self.sync_now_btn.configure(state="disabled", text="Syncing…")
        self.sync_status.configure(text="Syncing…", text_color="gray70")

        def worker():
            ok, status = perform_sync()
            color = "#98c379" if ok else "#e06c75"

            def done():
                self.sync_status.configure(text=status, text_color=color)
                self.sync_now_btn.configure(state="normal", text="Sync now")

            try:
                self.after(0, done)
            except RuntimeError:
                pass  # view closed

        threading.Thread(target=worker, daemon=True).start()

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
