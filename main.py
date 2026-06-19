"""Biometric-Attendance — Phase 1 entry point.

Initializes the local database, seeds the default admin + settings, then launches
the CustomTkinter app (which opens on the kiosk/attendance screen).

Run from the project root:

    python main.py
"""
from __future__ import annotations

import logging
import sys

import config
from app.db.database import init_db
from app.security.auth import ensure_default_admin


def _setup_logging() -> None:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.FileHandler(config.LOG_DIR / "app.log", encoding="utf-8")
    ]
    # When launched via pythonw.exe (the no-console desktop shortcut) there is no
    # console stream, so only add the console handler when one exists.
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def main() -> None:
    _setup_logging()
    logging.getLogger(__name__).info("Starting Biometric Attendance")

    init_db()
    ensure_default_admin()

    from app.ui.app_window import App

    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
