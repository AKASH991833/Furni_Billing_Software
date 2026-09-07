"""Fast time-based cache with LRU eviction.

Uses ``collections.OrderedDict`` for O(1) LRU tracking and per-key TTL
expiry.  The cache has a configurable maximum size (default 512 keys);
when the limit is hit the least-recently-used entry is evicted first.
"""
from __future__ import annotations

import collections
import time
from collections.abc import Callable
from typing import Any


class TTLCache:
    """In-memory cache with per-key TTL and LRU eviction.

    Intended for single-threaded (Qt event-loop) use; not thread-safe.
    """

    def __init__(self, default_ttl: float = 30.0, max_size: int = 512):
        self._default_ttl = default_ttl
        self._max_size = max_size
        # OrderedDict keeps insertion order — we move-to-end on access
        # so the first key is always the LRU candidate.
        self._store: collections.OrderedDict[str, tuple[Any, float]] = (
            collections.OrderedDict()
        )

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        # Move to end (most-recently-used) — O(1) on OrderedDict
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl: float | None = None):
        expires_at = time.monotonic() + (ttl if ttl is not None else self._default_ttl)
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (value, expires_at)
        # Evict LRU entries when over capacity
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)

    def invalidate(self, key: str):
        self._store.pop(key, None)

    def invalidate_prefix(self, prefix: str):
        keys_to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._store[k]

    def clear(self):
        self._store.clear()

    @property
    def stats(self) -> dict:
        """Return cache statistics for debugging."""
        return {"size": len(self._store), "max_size": self._max_size}


# Global cache instance — 30s default TTL, 512 max keys
cache = TTLCache(default_ttl=30.0, max_size=512)


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
