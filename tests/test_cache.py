"""Tests for TTLCache — set, get, invalidate, TTL expiry, LRU eviction, prefix.

Run with:  python -m pytest tests/test_cache.py -q
"""
import time
from unittest.mock import patch

import pytest

from app.utils.cache import TTLCache, cache, cached


# ---------------------------------------------------------------------------
# Basic get/set
# ---------------------------------------------------------------------------

class TestBasicOperations:
    def test_set_and_get(self):
        c = TTLCache(default_ttl=60)
        c.set("key", "value")
        assert c.get("key") == "value"

    def test_get_missing_key(self):
        c = TTLCache(default_ttl=60)
        assert c.get("nonexistent") is None

    def test_overwrite_key(self):
        c = TTLCache(default_ttl=60)
        c.set("k", 1)
        c.set("k", 2)
        assert c.get("k") == 2

    def test_none_value(self):
        c = TTLCache(default_ttl=60)
        c.set("k", None)
        # None is a valid value, should not be treated as missing
        assert c.get("k") is None

    def test_complex_value(self):
        c = TTLCache(default_ttl=60)
        data = {"nested": [1, 2, 3], "flag": True}
        c.set("complex", data)
        assert c.get("complex") == data


# ---------------------------------------------------------------------------
# TTL expiry
# ---------------------------------------------------------------------------

class TestTTLExpiry:
    def test_entry_expires(self):
        c = TTLCache(default_ttl=0.1)
        c.set("ephemeral", "data")
        assert c.get("ephemeral") == "data"
        time.sleep(0.15)
        assert c.get("ephemeral") is None

    def test_per_key_ttl(self):
        c = TTLCache(default_ttl=60)
        c.set("short", "data", ttl=0.1)
        c.set("long", "data", ttl=60)
        time.sleep(0.15)
        assert c.get("short") is None
        assert c.get("long") == "data"

    def test_refresh_on_set(self):
        c = TTLCache(default_ttl=0.2)
        c.set("k", "v1")
        time.sleep(0.15)
        c.set("k", "v2")  # refresh
        time.sleep(0.1)
        # Still valid because we refreshed
        assert c.get("k") == "v2"


# ---------------------------------------------------------------------------
# Invalidate
# ---------------------------------------------------------------------------

class TestInvalidate:
    def test_invalidate_single(self):
        c = TTLCache(default_ttl=60)
        c.set("k", "v")
        c.invalidate("k")
        assert c.get("k") is None

    def test_invalidate_nonexistent(self):
        c = TTLCache(default_ttl=60)
        c.invalidate("ghost")  # should not raise

    def test_invalidate_prefix(self):
        c = TTLCache(default_ttl=60)
        c.set("recent_invoices:5", [1, 2])
        c.set("recent_invoices:10", [3, 4])
        c.set("other_key", "keep")
        c.invalidate_prefix("recent_")
        assert c.get("recent_invoices:5") is None
        assert c.get("recent_invoices:10") is None
        assert c.get("other_key") == "keep"

    def test_clear_all(self):
        c = TTLCache(default_ttl=60)
        c.set("a", 1)
        c.set("b", 2)
        c.clear()
        assert c.get("a") is None
        assert c.get("b") is None


# ---------------------------------------------------------------------------
# LRU eviction
# ---------------------------------------------------------------------------

class TestLRUEviction:
    def test_evicts_lru_when_full(self):
        c = TTLCache(default_ttl=60, max_size=3)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        # Access "a" to make it recently used
        c.get("a")
        # Adding "d" should evict "b" (least recently used)
        c.set("d", 4)
        assert c.get("a") == 1  # still there
        assert c.get("b") is None  # evicted
        assert c.get("c") == 3
        assert c.get("d") == 4

    def test_lru_order_on_get(self):
        c = TTLCache(default_ttl=60, max_size=2)
        c.set("old", 1)
        c.set("new", 2)
        c.get("old")  # make old recently used
        c.set("third", 3)  # should evict "new"
        assert c.get("old") == 1
        assert c.get("new") is None


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_stats_size(self):
        c = TTLCache(default_ttl=60, max_size=100)
        c.set("a", 1)
        c.set("b", 2)
        assert c.stats["size"] == 2
        assert c.stats["max_size"] == 100

    def test_stats_after_clear(self):
        c = TTLCache(default_ttl=60, max_size=100)
        c.set("a", 1)
        c.clear()
        assert c.stats["size"] == 0


# ---------------------------------------------------------------------------
# cached decorator
# ---------------------------------------------------------------------------

class TestCachedDecorator:
    def test_caches_result(self):
        call_count = 0

        @cached("my_func", ttl=60)
        def my_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert my_func(5) == 10
        assert call_count == 1
        assert my_func(5) == 10  # cached
        assert call_count == 1  # not called again

    def test_different_args_different_cache(self):
        call_count = 0

        @cached("multi", ttl=60)
        def multi(x):
            nonlocal call_count
            call_count += 1
            return x + 1

        assert multi(1) == 2
        assert multi(2) == 3
        assert call_count == 2


# ---------------------------------------------------------------------------
# Global cache instance
# ---------------------------------------------------------------------------

class TestGlobalCache:
    def test_global_cache_works(self):
        cache.set("test_global", 42)
        assert cache.get("test_global") == 42
        cache.invalidate("test_global")
        assert cache.get("test_global") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
