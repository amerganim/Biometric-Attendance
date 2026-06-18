"""Admin home: navigation hub with quick stats."""
from __future__ import annotations

from datetime import date

import customtkinter as ctk

from app.db.repositories import AttendanceRepository, TeacherRepository


class AdminDashboard(ctk.CTkFrame):
    def __init__(self, parent, app) -> None:
        super().__init__(parent)
        self.app = app
        if not app.require_admin():
            return

        # Header.
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(24, 10))
        ctk.CTkLabel(header, text="Admin Dashboard", font=("", 26, "bold")).pack(side="left")
        ctk.CTkButton(header, text="Logout", width=90, fg_color="transparent",
                      border_width=1, command=app.logout).pack(side="right")
        ctk.CTkButton(header, text="Open Kiosk", width=120,
                      command=app.show_kiosk).pack(side="right", padx=8)

        # Stats row.
        stats = ctk.CTkFrame(self, fg_color="transparent")
        stats.pack(fill="x", padx=30, pady=8)
        teachers = TeacherRepository.list_all()
        enrolled = TeacherRepository.list_enrolled()
        today_rows = AttendanceRepository.query(
            start_date=date.today().isoformat(), end_date=date.today().isoformat()
        )
        self._stat(stats, "Teachers", str(len(teachers)))
        self._stat(stats, "Enrolled faces", str(len(enrolled)))
        self._stat(stats, "Check-ins today", str(len(today_rows)))

        # Navigation tiles.
        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(fill="both", expand=True, padx=30, pady=20)
        nav.grid_columnconfigure((0, 1), weight=1, uniform="nav")
        tiles = [
            ("👥  Teachers", "Add, edit, enroll, or remove teachers", app.show_teachers),
            ("📋  Reports", "View, filter, and export attendance", app.show_reports),
            ("⚙️  Settings", "Work hours, thresholds, password", app.show_settings),
            ("🖥️  Kiosk", "Open the attendance station", app.show_kiosk),
        ]
        for i, (title, subtitle, command) in enumerate(tiles):
            self._tile(nav, title, subtitle, command, i // 2, i % 2)

    def _stat(self, parent, label, value) -> None:
        card = ctk.CTkFrame(parent, corner_radius=12)
        card.pack(side="left", expand=True, fill="x", padx=6)
        ctk.CTkLabel(card, text=value, font=("", 30, "bold")).pack(pady=(16, 0))
        ctk.CTkLabel(card, text=label, text_color="gray70").pack(pady=(0, 14))

    def _tile(self, parent, title, subtitle, command, row, col) -> None:
        # A clickable card. We bind <Button-1> on the frame AND every child so a
        # click anywhere on the tile (including the text) triggers the action —
        # a plain button with overlaid labels would let the labels swallow clicks.
        idle = ("gray85", "gray20")
        hover = ("gray80", "gray25")
        card = ctk.CTkFrame(parent, corner_radius=14, height=120, fg_color=idle)
        card.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)
        card.grid_propagate(False)
        parent.grid_rowconfigure(row, weight=1)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.place(relx=0.05, rely=0.5, anchor="w")
        ctk.CTkLabel(inner, text=title, font=("", 20, "bold")).pack(anchor="w")
        ctk.CTkLabel(inner, text=subtitle, text_color="gray70").pack(anchor="w", pady=(4, 0))

        def on_enter(_e=None):
            card.configure(fg_color=hover)

        def on_leave(_e=None):
            card.configure(fg_color=idle)

        widgets = [card, inner] + list(inner.winfo_children())
        for w in widgets:
            w.bind("<Button-1>", lambda _e: command())
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.configure(cursor="hand2")
