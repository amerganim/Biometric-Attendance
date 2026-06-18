"""Admin login screen."""
from __future__ import annotations

import customtkinter as ctk

from app.security.auth import authenticate


class LoginView(ctk.CTkFrame):
    def __init__(self, parent, app) -> None:
        super().__init__(parent)
        self.app = app

        card = ctk.CTkFrame(self, width=380, corner_radius=16)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="Admin Login", font=("", 24, "bold")).grid(
            row=0, column=0, padx=40, pady=(34, 6)
        )
        ctk.CTkLabel(card, text="Sign in to manage teachers and reports",
                     text_color="gray70").grid(row=1, column=0, padx=40, pady=(0, 20))

        self.username = ctk.CTkEntry(card, placeholder_text="Username", width=300, height=40)
        self.username.grid(row=2, column=0, padx=40, pady=8)
        self.username.insert(0, "admin")

        self.password = ctk.CTkEntry(card, placeholder_text="Password", show="•",
                                     width=300, height=40)
        self.password.grid(row=3, column=0, padx=40, pady=8)
        self.password.bind("<Return>", lambda _e: self._submit())

        self.error = ctk.CTkLabel(card, text="", text_color="#e06c75")
        self.error.grid(row=4, column=0, padx=40, pady=(4, 0))

        ctk.CTkButton(card, text="Login", width=300, height=42,
                      command=self._submit).grid(row=5, column=0, padx=40, pady=(10, 8))
        ctk.CTkButton(card, text="← Back to attendance", width=300, height=36,
                      fg_color="transparent", border_width=1,
                      command=self.app.show_kiosk).grid(row=6, column=0, padx=40, pady=(0, 30))

        self.after(100, self.password.focus_set)

    def _submit(self) -> None:
        username = self.username.get().strip()
        password = self.password.get()
        if authenticate(username, password):
            self.app.current_admin = username
            self.app.show_dashboard()
        else:
            self.error.configure(text="Invalid username or password")
            self.password.delete(0, "end")
