"""Minimal Supabase (PostgREST) REST client for one-way upserts.

Only what the sync service needs: bulk-upsert rows into a table using the
``service_role`` key. We talk to PostgREST directly with ``requests`` rather than
pulling in the full supabase SDK — it's one endpoint and keeps dependencies light.
"""
from __future__ import annotations

from typing import Optional

import requests


class SupabaseError(RuntimeError):
    """Raised when an upsert request fails (network or HTTP error)."""


class SupabaseClient:
    def __init__(self, url: str, service_key: str, timeout: float = 15.0) -> None:
        self.base = url.rstrip("/")
        self.service_key = service_key
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.base) and bool(self.service_key)

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
            # Upsert on the primary key; don't return the rows back.
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }

    def upsert(self, table: str, rows: list[dict]) -> None:
        """Insert-or-update ``rows`` into ``table`` (no-op for an empty list)."""
        if not rows:
            return
        if not self.configured:
            raise SupabaseError("Supabase URL or service key is not set")
        endpoint = f"{self.base}/rest/v1/{table}"
        try:
            resp = requests.post(
                endpoint, json=rows, headers=self._headers(), timeout=self.timeout
            )
        except requests.RequestException as exc:  # offline / DNS / timeout
            raise SupabaseError(f"network error: {exc}") from exc
        if not (200 <= resp.status_code < 300):
            raise SupabaseError(f"HTTP {resp.status_code}: {resp.text[:300]}")

    def check_connection(self) -> Optional[str]:
        """Return None if reachable+authorized, else a short error message."""
        if not self.configured:
            return "URL or service key is not set"
        try:
            resp = requests.get(
                f"{self.base}/rest/v1/teachers",
                headers={**self._headers(), "Range": "0-0"},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            return f"network error: {exc}"
        if resp.status_code in (200, 206):
            return None
        return f"HTTP {resp.status_code}: {resp.text[:200]}"
