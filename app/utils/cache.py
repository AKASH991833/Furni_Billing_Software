"""Simple time-based cache for DB queries.

Avoids repeated expensive lookups for data that changes infrequently
(profile, areas, items). Cache entries expire after a configurable TTL.
"""
from __future__ import annotations

import time
from typing import Any, Callable


class TTLCache:
    """Thread-safe in-memory cache with per-key time-to-live expiry."""

    def __init__(self, default_ttl: float = 30.0):
        self._default_ttl = default_ttl
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: float | None = None):
        expires_at = time.monotonic() + (ttl if ttl is not None else self._default_ttl)
        self._store[key] = (value, expires_at)

    def invalidate(self, key: str):
        self._store.pop(key, None)

    def invalidate_prefix(self, prefix: str):
        keys_to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._store[k]

    def clear(self):
        self._store.clear()


# Global cache instance — 30s default TTL
cache = TTLCache(default_ttl=30.0)


def cached(key: str, ttl: float | None = None):
    """Decorator that caches a function's return value by key."""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            full_key = key
            if args:
                full_key += ":" + ":".join(str(a) for a in args)
            if kwargs:
                full_key += ":" + ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))

            result = cache.get(full_key)
            if result is not None:
                return result

            result = func(*args, **kwargs)
            cache.set(full_key, result, ttl=ttl)
            return result
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator
