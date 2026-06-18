"""Attendance reports: filter by date range / teacher and export to CSV or Excel."""
from __future__ import annotations

from datetime import date, timedelta
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.db.repositories import AttendanceRepository, TeacherRepository
from app.utils import exporter


class ReportsView(ctk.CTkFrame):
    def __init__(self, parent, app) -> None:
        super().__init__(parent)
        self.app = app
        if not app.require_admin():
            return

        self._rows = []
        # teacher name -> id (plus "All teachers")
        self._teachers = {"All teachers": None}
        for t in TeacherRepository.list_all():
            self._teachers[t["full_name"]] = t["id"]

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(20, 6))
        ctk.CTkButton(header, text="← Dashboard", width=110, fg_color="transparent",
                      border_width=1, command=app.show_dashboard).pack(side="left")
        ctk.CTkLabel(header, text="Attendance Reports",
                     font=("", 24, "bold")).pack(side="left", padx=16)

        # Filter bar.
        bar = ctk.CTkFrame(self)
        bar.pack(fill="x", padx=30, pady=8)
        ctk.CTkLabel(bar, text="From").pack(side="left", padx=(14, 4), pady=12)
        self.start_entry = ctk.CTkEntry(bar, width=120)
        self.start_entry.insert(0, (date.today() - timedelta(days=30)).isoformat())
        self.start_entry.pack(side="left", padx=4)
        ctk.CTkLabel(bar, text="To").pack(side="left", padx=(12, 4))
        self.end_entry = ctk.CTkEntry(bar, width=120)
        self.end_entry.insert(0, date.today().isoformat())
        self.end_entry.pack(side="left", padx=4)

        self.teacher_menu = ctk.CTkOptionMenu(bar, values=list(self._teachers.keys()), width=180)
        self.teacher_menu.set("All teachers")
        self.teacher_menu.pack(side="left", padx=12)

        ctk.CTkButton(bar, text="Apply", width=90, command=self._refresh).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="Export Excel", width=110,
                      command=lambda: self._export("xlsx")).pack(side="right", padx=(6, 14))
        ctk.CTkButton(bar, text="Export CSV", width=100, fg_color="transparent",
                      border_width=1, command=lambda: self._export("csv")).pack(side="right")

        self.summary = ctk.CTkLabel(self, text="", text_color="gray70")
        self.summary.pack(anchor="w", padx=34)

        # Result table headers.
        cols = ctk.CTkFrame(self, fg_color="transparent")
        cols.pack(fill="x", padx=34)
        for text, w in (("Teacher", 200), ("Dept", 130), ("Type", 70),
                        ("Status", 90), ("Time", 180), ("Liveness", 90)):
            ctk.CTkLabel(cols, text=text, width=w, anchor="w",
                         text_color="gray70", font=("", 12, "bold")).pack(side="left")

        self.table = ctk.CTkScrollableFrame(self)
        self.table.pack(fill="both", expand=True, padx=30, pady=(4, 16))
        self._refresh()

    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        teacher_id = self._teachers.get(self.teacher_menu.get())
        self._rows = AttendanceRepository.query(
            start_date=self.start_entry.get().strip() or None,
            end_date=self.end_entry.get().strip() or None,
            teacher_id=teacher_id,
        )
        for child in self.table.winfo_children():
            child.destroy()

        late = sum(1 for r in self._rows if r["status"] == "late")
        self.summary.configure(text=f"{len(self._rows)} records · {late} late")

        if not self._rows:
            ctk.CTkLabel(self.table, text="No records for this filter.",
                         text_color="gray60").pack(pady=30)
            return
        for r in self._rows:
            self._row(r)

    def _row(self, r) -> None:
        row = ctk.CTkFrame(self.table)
        row.pack(fill="x", pady=2)
        live = f"{r['liveness_score']:.2f}" if r["liveness_score"] is not None else "—"
        status_color = "#e5c07b" if r["status"] == "late" else "#98c379"
        ctk.CTkLabel(row, text=r["full_name"], width=200, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=r["department"] or "—", width=130, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=r["check_type"].upper(), width=70, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=r["status"], width=90, anchor="w",
                     text_color=status_color).pack(side="left")
        ctk.CTkLabel(row, text=r["timestamp"].replace("T", "  "), width=180,
                     anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=live, width=90, anchor="w").pack(side="left")

    # ------------------------------------------------------------------
    def _export(self, fmt: str) -> None:
        if not self._rows:
            messagebox.showinfo("Export", "Nothing to export for the current filter.")
            return
        ext = "xlsx" if fmt == "xlsx" else "csv"
        path = filedialog.asksaveasfilename(
            defaultextension=f".{ext}",
            initialfile=f"attendance_{date.today().isoformat()}.{ext}",
            filetypes=[(ext.upper(), f"*.{ext}")],
        )
        if not path:
            return
        try:
            if fmt == "xlsx":
                exporter.export_excel(self._rows, path)
            else:
                exporter.export_csv(self._rows, path)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))
            return
        messagebox.showinfo("Export complete", f"Saved {len(self._rows)} records to:\n{path}")
