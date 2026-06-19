"""Admin authentication: password hashing (bcrypt) and login.

Passwords are never stored in plain text. ``ensure_default_admin`` seeds the first
admin account on a fresh database; the password should be changed from Settings.
"""
from __future__ import annotations

import bcrypt

import config
from app.db.repositories import AdminRepository, SettingsRepository


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def authenticate(username: str, password: str) -> bool:
    """Return True if the username/password pair is valid."""
    admin = AdminRepository.get_by_username(username)
    if admin is None:
        return False
    return verify_password(password, admin["password_hash"])


def change_password(username: str, old_password: str, new_password: str) -> bool:
    """Change an admin password after verifying the old one."""
    if not authenticate(username, old_password):
        return False
    AdminRepository.update_password(username, hash_password(new_password))
    return True


def has_setup_password() -> bool:
    """True once a developer/setup password has been configured."""
    return bool(SettingsRepository.get("setup_password_hash", ""))


def set_setup_password(password: str) -> None:
    """Set (or change) the developer password that locks cloud settings."""
    SettingsRepository.set("setup_password_hash", hash_password(password))


def verify_setup_password(password: str) -> bool:
    h = SettingsRepository.get("setup_password_hash", "")
    return bool(h) and verify_password(password, h)


def ensure_default_admin() -> None:
    """Seed the default admin + default settings on a fresh database."""
    SettingsRepository.seed_defaults()
    if AdminRepository.count() == 0:
        AdminRepository.create(
            config.DEFAULT_ADMIN_USERNAME,
            hash_password(config.DEFAULT_ADMIN_PASSWORD),
        )
