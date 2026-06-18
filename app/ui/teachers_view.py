"""Teacher management: list, add, edit, enroll face, deactivate/delete."""
from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from app.db.repositories import TeacherRepository


class TeachersView(ctk.CTkFrame):
    def __init__(self, parent, app) -> None:
        super().__init__(parent)
        self.app = app
        if not app.require_admin():
            return

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(24, 8))
        ctk.CTkButton(header, text="← Dashboard", width=110, fg_color="transparent",
                      border_width=1, command=app.show_dashboard).pack(side="left")
        ctk.CTkLabel(header, text="Teachers", font=("", 24, "bold")).pack(side="left", padx=16)
        ctk.CTkButton(header, text="+ Add Teacher", width=140,
                      command=self._add).pack(side="right")

        # Column headers.
        cols = ctk.CTkFrame(self, fg_color="transparent")
        cols.pack(fill="x", padx=34, pady=(6, 0))
        for text, w in (("Name", 220), ("Code", 90), ("Department", 150),
                        ("Enrolled", 90), ("Status", 80), ("Actions", 260)):
            ctk.CTkLabel(cols, text=text, width=w, anchor="w",
                         text_color="gray70", font=("", 12, "bold")).pack(side="left")

        self.list_frame = ctk.CTkScrollableFrame(self)
        self.list_frame.pack(fill="both", expand=True, padx=30, pady=10)
        self._refresh()

    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()
        teachers = TeacherRepository.list_all()
        if not teachers:
            ctk.CTkLabel(self.list_frame, text="No teachers yet. Click “+ Add Teacher”.",
                         text_color="gray60").pack(pady=40)
            return
        for t in teachers:
            self._row(t)

    def _row(self, t) -> None:
        row = ctk.CTkFrame(self.list_frame)
        row.pack(fill="x", pady=4)
        enrolled = "✅" if t["embedding"] else "—"
        status = "Active" if t["active"] else "Inactive"
        ctk.CTkLabel(row, text=t["full_name"], width=220, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=t["employee_code"] or "—", width=90, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=t["department"] or "—", width=150, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=enrolled, width=90, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=status, width=80, anchor="w").pack(side="left")

        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.pack(side="left")
        ctk.CTkButton(actions, text="Enroll", width=72,
                      command=lambda: self.app.show_enroll(t["id"])).pack(side="left", padx=3)
        ctk.CTkButton(actions, text="Edit", width=60, fg_color="transparent",
                      border_width=1, command=lambda: self._edit(t)).pack(side="left", padx=3)
        ctk.CTkButton(actions, text="Delete", width=66, fg_color="#a83232",
                      hover_color="#8a2929",
                      command=lambda: self._delete(t)).pack(side="left", padx=3)

    # ------------------------------------------------------------------
    def _add(self) -> None:
        TeacherFormDialog(self, on_saved=self._refresh)

    def _edit(self, t) -> None:
        TeacherFormDialog(self, teacher=t, on_saved=self._refresh)

    def _delete(self, t) -> None:
        if messagebox.askyesno(
            "Delete teacher",
            f"Delete {t['full_name']} and all their attendance records?\n"
            "This cannot be undone.",
        ):
            TeacherRepository.delete(t["id"])
            self._refresh()


class TeacherFormDialog(ctk.CTkToplevel):
    """Modal add/edit form for a teacher's details."""

    FIELDS = [
        ("full_name", "Full name *"),
        ("employee_code", "Employee code"),
        ("email", "Email"),
        ("phone", "Phone"),
        ("department", "Department"),
    ]

    def __init__(self, master, teacher=None, on_saved=None) -> None:
        super().__init__(master)
        self.teacher = teacher
        self.on_saved = on_saved
        self.title("Edit Teacher" if teacher else "Add Teacher")
        self.geometry("420x520")
        self.resizable(False, False)
        # Make it a proper on-top modal. grab_set must wait until the window is
        # actually viewable, otherwise CTkToplevel raises "grab failed: window not
        # viewable" and the dialog never opens.
        self.transient(master.winfo_toplevel())
        self.lift()
        self.after(120, self._make_modal)

        ctk.CTkLabel(self, text=self.title(), font=("", 20, "bold")).pack(pady=(20, 10))

        self.entries: dict[str, ctk.CTkEntry] = {}
        for key, label in self.FIELDS:
            ctk.CTkLabel(self, text=label, anchor="w").pack(fill="x", padx=40, pady=(8, 0))
            entry = ctk.CTkEntry(self, width=340, height=38)
            entry.pack(padx=40)
            if teacher and teacher[key]:
                entry.insert(0, teacher[key])
            self.entries[key] = entry

        self.consent = ctk.CTkCheckBox(self, text="Consent form signed")
        self.consent.pack(padx=40, pady=14, anchor="w")
        if teacher and teacher["consent_signed"]:
            self.consent.select()

        self.error = ctk.CTkLabel(self, text="", text_color="#e06c75")
        self.error.pack()

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(pady=10)
        ctk.CTkButton(buttons, text="Cancel", width=120, fg_color="transparent",
                      border_width=1, command=self.destroy).pack(side="left", padx=6)
        ctk.CTkButton(buttons, text="Save", width=120, command=self._save).pack(side="left", padx=6)

    def _make_modal(self) -> None:
        try:
            self.grab_set()
            self.focus_force()
        except Exception:
            # If the window isn't viewable yet, try again shortly.
            self.after(120, self._make_modal)

    def _save(self) -> None:
        values = {key: self.entries[key].get().strip() for key, _ in self.FIELDS}
        if not values["full_name"]:
            self.error.configure(text="Full name is required")
            return
        consent = bool(self.consent.get())
        try:
            if self.teacher:
                TeacherRepository.update(self.teacher["id"], consent_signed=consent, **values)
            else:
                TeacherRepository.create(
                    full_name=values["full_name"],
                    employee_code=values["employee_code"] or None,
                    email=values["email"] or None,
                    phone=values["phone"] or None,
                    department=values["department"] or None,
                    consent_signed=consent,
                )
        except Exception as exc:  # e.g. duplicate employee_code
            self.error.configure(text=f"Could not save: {exc}")
            return
        if self.on_saved:
            self.on_saved()
        self.destroy()
