"""Export attendance query results to CSV or Excel.

Rows are sqlite3.Row objects from AttendanceRepository.query (joined with teacher
fields). Both exporters take the same rows and produce a flat table.
"""
from __future__ import annotations

import csv
import sqlite3
from typing import Sequence

from openpyxl import Workbook

COLUMNS = [
    ("full_name", "Teacher"),
    ("employee_code", "Code"),
    ("department", "Department"),
    ("check_type", "Type"),
    ("status", "Status"),
    ("timestamp", "Timestamp"),
    ("liveness_score", "Liveness"),
]


def _value(row: sqlite3.Row, key: str):
    try:
        return row[key]
    except (IndexError, KeyError):
        return ""


def export_csv(rows: Sequence[sqlite3.Row], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([header for _, header in COLUMNS])
        for row in rows:
            writer.writerow([_value(row, key) for key, _ in COLUMNS])


def export_excel(rows: Sequence[sqlite3.Row], path: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance"
    ws.append([header for _, header in COLUMNS])
    for row in rows:
        ws.append([_value(row, key) for key, _ in COLUMNS])
    # Reasonable column widths.
    for idx, (_, header) in enumerate(COLUMNS, start=1):
        ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = max(
            14, len(header) + 2
        )
    wb.save(path)
