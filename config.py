"""Central configuration: paths, constants, and default settings.

Everything is local for Phase 1. Paths are resolved relative to this file so the
app works regardless of the current working directory.
"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
THUMBNAIL_DIR = DATA_DIR / "thumbnails"
MODELS_DIR = DATA_DIR / "models"          # cached ONNX models (anti-spoof, etc.)
LOG_DIR = DATA_DIR / "logs"
DB_PATH = DATA_DIR / "attendance.db"

# Created on startup (see app.db.database.init_db).
REQUIRED_DIRS = (DATA_DIR, THUMBNAIL_DIR, MODELS_DIR, LOG_DIR)

# ---------------------------------------------------------------------------
# Default admin (seeded on first run; password should be changed in Settings)
# ---------------------------------------------------------------------------
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"

# ---------------------------------------------------------------------------
# Default app settings (stored in the `settings` table; editable in the UI).
# Values are strings because the settings table stores TEXT.
# ---------------------------------------------------------------------------
DEFAULT_SETTINGS: dict[str, str] = {
    "work_start_time": "09:00",        # HH:MM — check-ins after this (+grace) are late
    "late_grace_minutes": "10",        # minutes of grace before "late"
    "recognition_threshold": "0.42",   # max cosine DISTANCE to accept a match (lower = stricter)
    "liveness_threshold": "0.50",      # min passive anti-spoof score to accept as real
    "duplicate_window_minutes": "2",   # ignore repeat scans within this window
    "enroll_frames": "5",              # face frames captured per enrollment
    "active_challenge_enabled": "1",   # 1 = require blink/turn challenge at kiosk
    # --- Cloud sync (Phase 2; configured in Settings → Cloud Sync) ---
    "supabase_url": "",                # https://<project>.supabase.co
    "supabase_service_key": "",        # service_role key (local, trusted device only)
    "sync_enabled": "0",               # 1 = push to cloud in the background
    "sync_interval_minutes": "15",     # how often the background sync runs
    "last_sync_at": "",                # ISO timestamp of last successful sync
    "last_sync_status": "",            # short human-readable status
}

# ---------------------------------------------------------------------------
# Face recognition / vision
# ---------------------------------------------------------------------------
# insightface model pack ("buffalo_l" = RetinaFace detector + ArcFace r50 embeddings).
INSIGHTFACE_MODEL_PACK = "buffalo_l"
EMBEDDING_DIM = 512
CAMERA_INDEX = 0
