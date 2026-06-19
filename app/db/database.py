"""SQLite connection management and schema creation.

A single connection is shared across the app (the UI is single-threaded; the camera
loop reads frames but writes go through the main thread). Foreign keys are enabled
and rows come back as ``sqlite3.Row`` for dict-style access.

The schema is designed so Phase 2 cloud sync drops in cleanly: every syncable row
carries a UUID ``id``, an ``updated_at`` timestamp, and a ``synced`` flag.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

import config

_connection: Optional[sqlite3.Connection] = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS teachers (
    id              TEXT PRIMARY KEY,            -- UUID
    full_name       TEXT NOT NULL,
    employee_code   TEXT UNIQUE,
    email           TEXT,
    phone           TEXT,
    department      TEXT,
    embedding       TEXT,                        -- JSON: list of 512-float vectors
    photo_path      TEXT,                        -- enrollment thumbnail
    consent_signed  INTEGER NOT NULL DEFAULT 0,  -- bool
    active          INTEGER NOT NULL DEFAULT 1,  -- bool
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    synced          INTEGER NOT NULL DEFAULT 0   -- bool, for Phase 2
);

CREATE TABLE IF NOT EXISTS attendance (
    id              TEXT PRIMARY KEY,            -- UUID
    teacher_id      TEXT NOT NULL,
    check_type      TEXT NOT NULL,               -- 'in' | 'out'
    timestamp       TEXT NOT NULL,               -- ISO8601 local time of the scan
    status          TEXT NOT NULL DEFAULT 'present', -- 'present' | 'late'
    liveness_score  REAL,
    thumbnail_path  TEXT,
    created_at      TEXT NOT NULL,
    synced          INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admins (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attendance_teacher ON attendance(teacher_id);
CREATE INDEX IF NOT EXISTS idx_attendance_time ON attendance(timestamp);
CREATE INDEX IF NOT EXISTS idx_attendance_synced ON attendance(synced);
"""


def get_connection() -> sqlite3.Connection:
    """Return the shared SQLite connection, creating it on first use."""
    global _connection
    if _connection is None:
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _connection = sqlite3.connect(
            config.DB_PATH, check_same_thread=False, isolation_level=None
        )
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA foreign_keys = ON;")
        _connection.execute("PRAGMA journal_mode = WAL;")
    return _connection


def new_connection() -> sqlite3.Connection:
    """Open a fresh, independent connection to the same database file.

    Used by the background sync service so it never shares the single app-wide
    connection across threads. WAL mode (enabled below) lets this connection read
    and write concurrently with the main one safely.
    """
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


def init_db() -> None:
    """Create required directories, the schema, and seed defaults.

    Seeding (default admin + default settings) lives in app.security.auth and
    app.db.repositories to avoid an import cycle; this only builds the tables.
    """
    for directory in config.REQUIRED_DIRS:
        directory.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    conn.executescript(SCHEMA)


def close_connection() -> None:
    """Close the shared connection (used on app shutdown)."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None
