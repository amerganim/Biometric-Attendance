"""Root application window and view navigation.

The app boots into the **kiosk** (the attendance station teachers use). A small
"Admin" button leads to login; once authenticated, the admin can reach teacher
management, enrollment, reports, and settings. Views are simple ``CTkFrame``
subclasses; the active one is swapped in/out and may define ``on_show``/``on_hide``
hooks (used to start/stop the shared camera).
"""
from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

import config
from app.core.camera import Camera
from app.db.database import close_connection
from app.sync.sync_service import SyncService


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Biometric Attendance")
        self.geometry("1120x720")
        self.minsize(940, 620)
        if config.ICON_PATH:
            # CTk re-applies its own icon shortly after creation, so set ours after.
            try:
                self.iconbitmap(config.ICON_PATH)
                self.after(300, lambda: self.iconbitmap(config.ICON_PATH))
            except Exception:
                pass

        # Shared resources.
        self.camera = Camera()
        self.current_admin: Optional[str] = None  # username when logged in

        # Background cloud sync (no-op until configured + enabled in Settings).
        self.sync_service = SyncService()
        self.sync_service.start()

        self._container = ctk.CTkFrame(self, corner_radius=0)
        self._container.pack(fill="both", expand=True)
        self._current_view: Optional[ctk.CTkFrame] = None

        # Fullscreen / kiosk toggle (F11 to enter, Escape to leave).
        self._fullscreen = False
        self.bind("<F11>", self._toggle_fullscreen)
        self.bind("<Escape>", self._exit_fullscreen)

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_kiosk()

    # ------------------------------------------------------------------
    def _toggle_fullscreen(self, _event=None) -> None:
        self._fullscreen = not self._fullscreen
        self.attributes("-fullscreen", self._fullscreen)

    def _exit_fullscreen(self, _event=None) -> None:
        if self._fullscreen:
            self._fullscreen = False
            self.attributes("-fullscreen", False)

    # ------------------------------------------------------------------
    # View management
    # ------------------------------------------------------------------
    def _swap(self, factory: Callable[..., ctk.CTkFrame]) -> None:
        if self._current_view is not None:
            on_hide = getattr(self._current_view, "on_hide", None)
            if callable(on_hide):
                on_hide()
            self._current_view.destroy()
        self._current_view = factory(self._container, self)
        self._current_view.pack(fill="both", expand=True)
        on_show = getattr(self._current_view, "on_show", None)
        if callable(on_show):
            on_show()

    def show_kiosk(self) -> None:
        from app.ui.kiosk_view import KioskView

        self._swap(KioskView)

    def show_login(self) -> None:
        from app.ui.login_view import LoginView

        self._swap(LoginView)

    def show_dashboard(self) -> None:
        from app.ui.admin_dashboard import AdminDashboard

        self._swap(AdminDashboard)

    def show_teachers(self) -> None:
        from app.ui.teachers_view import TeachersView

        self._swap(TeachersView)

    def show_enroll(self, teacher_id: str) -> None:
        from app.ui.enroll_view import EnrollView

        self._swap(lambda parent, app: EnrollView(parent, app, teacher_id))

    def show_reports(self) -> None:
        from app.ui.reports_view import ReportsView

        self._swap(ReportsView)

    def show_settings(self) -> None:
        from app.ui.settings_view import SettingsView

        self._swap(SettingsView)

    # ------------------------------------------------------------------
    def require_admin(self) -> bool:
        """Guard for admin-only screens; bounces to login if not authenticated."""
        if self.current_admin is None:
            self.show_login()
            return False
        return True

    def logout(self) -> None:
        self.current_admin = None
        self.show_kiosk()

    # ------------------------------------------------------------------
    def on_close(self) -> None:
        if self._current_view is not None:
            on_hide = getattr(self._current_view, "on_hide", None)
            if callable(on_hide):
                on_hide()
        self.sync_service.stop()
        self.camera.stop()
        close_connection()
        self.destroy()
