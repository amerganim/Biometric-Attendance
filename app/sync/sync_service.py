"""One-way cloud sync: push unsynced teachers + attendance to Supabase.

Design:
* ``perform_sync()`` is a self-contained, thread-safe function: it opens its own
  SQLite connection, reads the cloud settings, upserts pending rows, marks them
  synced locally, and records a status. A module lock prevents two syncs overlapping.
* ``SyncService`` is just a background scheduler that calls ``perform_sync()`` on an
  interval (and immediately when woken). Both the timer and the Settings "Sync now"
  button funnel through the same ``perform_sync()``.

Only text data is sent — never embeddings or photo paths. Network/HTTP failures are
caught so the kiosk keeps working offline; unsynced rows are retried next time.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime

from app.db import database
from app.db.repositories import AttendanceRepository, TeacherRepository
from app.sync.supabase_client import SupabaseClient, SupabaseError

log = logging.getLogger(__name__)

_sync_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Settings access on a given connection (kept local to avoid cross-thread reuse
# of the app-wide connection).
# ---------------------------------------------------------------------------
def _get(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def _set(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


# ---------------------------------------------------------------------------
# Row -> cloud payload (excludes embedding / photo_path / thumbnail_path)
# ---------------------------------------------------------------------------
def _teacher_payload(t: sqlite3.Row) -> dict:
    return {
        "id": t["id"],
        "full_name": t["full_name"],
        "employee_code": t["employee_code"],
        "email": t["email"],
        "phone": t["phone"],
        "department": t["department"],
        "active": bool(t["active"]),
        "consent_signed": bool(t["consent_signed"]),
        "created_at": t["created_at"],
        "updated_at": t["updated_at"],
    }


def _attendance_payload(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "teacher_id": r["teacher_id"],
        "check_type": r["check_type"],
        "timestamp": r["timestamp"],
        "status": r["status"],
        "liveness_score": r["liveness_score"],
        "created_at": r["created_at"],
    }


def perform_sync() -> tuple[bool, str]:
    """Run one sync pass. Returns (ok, human-readable status)."""
    if not _sync_lock.acquire(blocking=False):
        return False, "Sync already in progress"
    conn = database.new_connection()
    try:
        client = SupabaseClient(_get(conn, "supabase_url"), _get(conn, "supabase_service_key"))
        if not client.configured:
            return False, "Cloud sync is not configured"

        # Teachers first (attendance references them), then attendance.
        teachers = TeacherRepository.unsynced(conn)
        client.upsert("teachers", [_teacher_payload(t) for t in teachers])
        TeacherRepository.mark_synced([t["id"] for t in teachers], conn)

        records = AttendanceRepository.unsynced(conn)
        client.upsert("attendance", [_attendance_payload(r) for r in records])
        AttendanceRepository.mark_synced([r["id"] for r in records], conn)

        status = f"Synced {len(teachers)} teacher(s), {len(records)} record(s)"
        _set(conn, "last_sync_at", datetime.now().isoformat(timespec="seconds"))
        _set(conn, "last_sync_status", status)
        log.info(status)
        return True, status
    except SupabaseError as exc:
        status = f"Sync failed: {exc}"
        _set(conn, "last_sync_status", status)
        log.warning(status)
        return False, status
    finally:
        conn.close()
        _sync_lock.release()


class SyncService:
    """Background scheduler that calls :func:`perform_sync` on an interval."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="sync")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def request_sync(self) -> None:
        """Wake the scheduler to sync as soon as possible."""
        self._wake.set()

    def _run(self) -> None:
        conn = database.new_connection()
        try:
            while not self._stop.is_set():
                if _get(conn, "sync_enabled", "0") == "1":
                    perform_sync()
                try:
                    interval = max(1, int(_get(conn, "sync_interval_minutes", "15")))
                except ValueError:
                    interval = 15
                self._wake.wait(timeout=interval * 60)
                self._wake.clear()
        finally:
            conn.close()
