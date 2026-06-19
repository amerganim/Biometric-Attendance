"""Data-access helpers (CRUD) over the SQLite connection.

Grouped by table into small classes of static methods. Embeddings are stored as
JSON (a list of 512-float vectors) so a teacher can have several enrollment samples.
Timestamps are ISO8601 local time.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Iterable, Optional

import config
from app.db.database import get_connection


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_id() -> str:
    return str(uuid.uuid4())


def _conn(conn: Optional[sqlite3.Connection] = None) -> sqlite3.Connection:
    """Return the given connection, or the shared app connection by default.

    The background sync service passes its own dedicated connection so it never
    shares the single app-wide connection across threads.
    """
    return conn if conn is not None else get_connection()


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
class SettingsRepository:
    @staticmethod
    def seed_defaults() -> None:
        """Insert any default settings that are missing (idempotent)."""
        conn = get_connection()
        for key, value in config.DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )

    @staticmethod
    def get(key: str, default: Optional[str] = None) -> Optional[str]:
        row = get_connection().execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    @staticmethod
    def get_int(key: str, default: int = 0) -> int:
        value = SettingsRepository.get(key)
        try:
            return int(value) if value is not None else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def get_float(key: str, default: float = 0.0) -> float:
        value = SettingsRepository.get(key)
        try:
            return float(value) if value is not None else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def get_bool(key: str, default: bool = False) -> bool:
        value = SettingsRepository.get(key)
        if value is None:
            return default
        return value.strip() in ("1", "true", "True", "yes")

    @staticmethod
    def set(key: str, value: str) -> None:
        get_connection().execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )

    @staticmethod
    def all() -> dict[str, str]:
        rows = get_connection().execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}


# ---------------------------------------------------------------------------
# Admins
# ---------------------------------------------------------------------------
class AdminRepository:
    @staticmethod
    def get_by_username(username: str) -> Optional[sqlite3.Row]:
        return get_connection().execute(
            "SELECT * FROM admins WHERE username = ?", (username,)
        ).fetchone()

    @staticmethod
    def count() -> int:
        return get_connection().execute(
            "SELECT COUNT(*) AS n FROM admins"
        ).fetchone()["n"]

    @staticmethod
    def create(username: str, password_hash: str) -> None:
        get_connection().execute(
            "INSERT INTO admins (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, password_hash, _now()),
        )

    @staticmethod
    def update_password(username: str, password_hash: str) -> None:
        get_connection().execute(
            "UPDATE admins SET password_hash = ? WHERE username = ?",
            (password_hash, username),
        )


# ---------------------------------------------------------------------------
# Teachers
# ---------------------------------------------------------------------------
class TeacherRepository:
    @staticmethod
    def create(
        full_name: str,
        employee_code: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        department: Optional[str] = None,
        consent_signed: bool = False,
    ) -> str:
        teacher_id = new_id()
        now = _now()
        get_connection().execute(
            """INSERT INTO teachers
               (id, full_name, employee_code, email, phone, department,
                consent_signed, active, created_at, updated_at, synced)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 0)""",
            (teacher_id, full_name, employee_code, email, phone, department,
             1 if consent_signed else 0, now, now),
        )
        return teacher_id

    @staticmethod
    def update(teacher_id: str, **fields) -> None:
        """Update arbitrary teacher columns; always bumps updated_at + unsyncs."""
        allowed = {
            "full_name", "employee_code", "email", "phone", "department",
            "consent_signed", "active", "photo_path",
        }
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return
        sets["updated_at"] = _now()
        sets["synced"] = 0
        assignments = ", ".join(f"{k} = ?" for k in sets)
        get_connection().execute(
            f"UPDATE teachers SET {assignments} WHERE id = ?",
            (*sets.values(), teacher_id),
        )

    @staticmethod
    def set_embedding(teacher_id: str, vectors: list[list[float]], photo_path: str) -> None:
        get_connection().execute(
            "UPDATE teachers SET embedding = ?, photo_path = ?, updated_at = ?, "
            "synced = 0 WHERE id = ?",
            (json.dumps(vectors), photo_path, _now(), teacher_id),
        )

    @staticmethod
    def get(teacher_id: str) -> Optional[sqlite3.Row]:
        return get_connection().execute(
            "SELECT * FROM teachers WHERE id = ?", (teacher_id,)
        ).fetchone()

    @staticmethod
    def list_all(include_inactive: bool = True) -> list[sqlite3.Row]:
        sql = "SELECT * FROM teachers"
        if not include_inactive:
            sql += " WHERE active = 1"
        sql += " ORDER BY full_name COLLATE NOCASE"
        return get_connection().execute(sql).fetchall()

    @staticmethod
    def list_enrolled() -> list[sqlite3.Row]:
        """Active teachers that have a face embedding (used by the kiosk)."""
        return get_connection().execute(
            "SELECT * FROM teachers WHERE active = 1 AND embedding IS NOT NULL "
            "ORDER BY full_name COLLATE NOCASE"
        ).fetchall()

    @staticmethod
    def delete(teacher_id: str) -> None:
        get_connection().execute("DELETE FROM teachers WHERE id = ?", (teacher_id,))

    @staticmethod
    def parse_embedding(row: sqlite3.Row) -> list[list[float]]:
        raw = row["embedding"]
        return json.loads(raw) if raw else []

    @staticmethod
    def unsynced(conn: Optional[sqlite3.Connection] = None) -> list[sqlite3.Row]:
        """Teachers pending upload to the cloud (used by the sync service)."""
        return _conn(conn).execute(
            "SELECT * FROM teachers WHERE synced = 0 ORDER BY created_at"
        ).fetchall()

    @staticmethod
    def mark_synced(ids: Iterable[str], conn: Optional[sqlite3.Connection] = None) -> None:
        ids = list(ids)
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        _conn(conn).execute(
            f"UPDATE teachers SET synced = 1 WHERE id IN ({placeholders})", ids
        )


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------
class AttendanceRepository:
    @staticmethod
    def create(
        teacher_id: str,
        check_type: str,
        status: str = "present",
        liveness_score: Optional[float] = None,
        thumbnail_path: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> str:
        record_id = new_id()
        ts = timestamp or _now()
        get_connection().execute(
            """INSERT INTO attendance
               (id, teacher_id, check_type, timestamp, status,
                liveness_score, thumbnail_path, created_at, synced)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (record_id, teacher_id, check_type, ts, status,
             liveness_score, thumbnail_path, _now()),
        )
        return record_id

    @staticmethod
    def last_for_teacher_on(teacher_id: str, day: str) -> Optional[sqlite3.Row]:
        """Most recent record for a teacher on a given YYYY-MM-DD (local) date."""
        # rowid tiebreak keeps ordering deterministic when several records share the
        # same second-resolution timestamp.
        return get_connection().execute(
            "SELECT * FROM attendance WHERE teacher_id = ? AND date(timestamp) = ? "
            "ORDER BY timestamp DESC, rowid DESC LIMIT 1",
            (teacher_id, day),
        ).fetchone()

    @staticmethod
    def count_for_teacher_on(teacher_id: str, day: str) -> int:
        return get_connection().execute(
            "SELECT COUNT(*) AS n FROM attendance "
            "WHERE teacher_id = ? AND date(timestamp) = ?",
            (teacher_id, day),
        ).fetchone()["n"]

    @staticmethod
    def query(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        teacher_id: Optional[str] = None,
    ) -> list[sqlite3.Row]:
        """Filtered attendance log joined with teacher names (newest first)."""
        sql = [
            "SELECT a.*, t.full_name, t.employee_code, t.department",
            "FROM attendance a JOIN teachers t ON t.id = a.teacher_id",
            "WHERE 1=1",
        ]
        params: list = []
        if start_date:
            sql.append("AND date(a.timestamp) >= ?")
            params.append(start_date)
        if end_date:
            sql.append("AND date(a.timestamp) <= ?")
            params.append(end_date)
        if teacher_id:
            sql.append("AND a.teacher_id = ?")
            params.append(teacher_id)
        sql.append("ORDER BY a.timestamp DESC")
        return get_connection().execute(" ".join(sql), params).fetchall()

    @staticmethod
    def unsynced(conn: Optional[sqlite3.Connection] = None) -> list[sqlite3.Row]:
        """Records pending upload — used by the sync service."""
        return _conn(conn).execute(
            "SELECT * FROM attendance WHERE synced = 0 ORDER BY timestamp"
        ).fetchall()

    @staticmethod
    def mark_synced(ids: Iterable[str], conn: Optional[sqlite3.Connection] = None) -> None:
        ids = list(ids)
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        _conn(conn).execute(
            f"UPDATE attendance SET synced = 1 WHERE id IN ({placeholders})", ids
        )
