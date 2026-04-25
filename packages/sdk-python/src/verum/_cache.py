"""In-memory TTL cache for deployment configs with fresh and stale lookup support."""
from __future__ import annotations

import time
from typing import Any


class DeploymentConfigCache:
    """Cache that distinguishes between a fresh TTL and a longer stale TTL.

    The fresh TTL (default 60s) is used for normal hits. The stale TTL
    (default 24h) allows serving a cached value even after the fresh window
    expires, so callers can fall back to stale data instead of failing.
    """

    # Internal store shape: key → (value, fresh_expires_at, stale_expires_at)
    _store: dict[str, tuple[Any, float, float]]

    def __init__(self, ttl: float = 60.0, stale_ttl: float = 86400.0) -> None:
        self._ttl = ttl
        self._stale_ttl = stale_ttl
        self._store = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, key: str) -> Any | None:
        """Return value if within the fresh TTL window, else None.

        Backward-compatible alias for :meth:`get_fresh`.

        Args:
            key: Cache key.

        Returns:
            Cached value when fresh, None otherwise.
        """
        return self.get_fresh(key)

    def get_fresh(self, key: str) -> Any | None:
        """Return value only if it is still within the fresh TTL.

        Args:
            key: Cache key.

        Returns:
            Cached value when fresh, None when expired or absent.
        """
        entry = self._store.get(key)
        if entry is None:
            return None
        value, fresh_expires_at, stale_expires_at = entry
        now = time.monotonic()
        if now > stale_expires_at:
            del self._store[key]
            return None
        if now > fresh_expires_at:
            return None
        return value

    def get_stale(self, key: str) -> Any | None:
        """Return value if within the stale TTL, even if the fresh TTL has passed.

        Args:
            key: Cache key.

        Returns:
            Cached value when within stale window, None when fully expired or absent.
        """
        entry = self._store.get(key)
        if entry is None:
            return None
        value, _fresh_expires_at, stale_expires_at = entry
        if time.monotonic() > stale_expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        """Store a value with both fresh and stale expiry timestamps.

        Args:
            key: Cache key.
            value: Value to cache.
        """
        now = time.monotonic()
        self._store[key] = (value, now + self._ttl, now + self._stale_ttl)
