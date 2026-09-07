"""Lightweight in-memory rate limiter for activation endpoints.

A full external rate limiter (Redis/slowapi) can be swapped in for
production; this simple token-bucket is dependency-free and sufficient for
the desktop-licensing use case.
"""
from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock


class InMemoryRateLimiter:
    def __init__(self, max_per_minute: int = 10) -> None:
        self.max_per_minute = max_per_minute
        self._calls: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, key: str) -> bool:
        """Return True if the key has capacity; otherwise False."""
        now = time.monotonic()
        cutoff = now - 60
        with self._lock:
            window = [ts for ts in self._calls[key] if ts > cutoff]
            self._calls[key] = window
            if len(window) >= self.max_per_minute:
                return False
            window.append(now)
            self._calls[key] = window
            return True


rate_limiter = InMemoryRateLimiter()