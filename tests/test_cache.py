"""Tests for the file-based cache system."""

import json
import time

import pytest

from zaza.cache.store import FileCache


@pytest.fixture
def cache(tmp_path):
    return FileCache(cache_dir=tmp_path)


def test_make_key_basic(cache):
    key = cache.make_key("get_prices", ticker="AAPL", start="2024-01-01")
    assert "get_prices" in key
    assert "AAPL" in key
    assert "2024-01-01" in key


def test_make_key_deterministic(cache):
    k1 = cache.make_key("get_prices", ticker="AAPL", start="2024-01-01")
    k2 = cache.make_key("get_prices", start="2024-01-01", ticker="AAPL")
    assert k1 == k2  # sorted params


def test_make_key_skips_none(cache):
    k1 = cache.make_key("get_prices", ticker="AAPL", end=None)
    k2 = cache.make_key("get_prices", ticker="AAPL")
    assert k1 == k2


def test_set_and_get(cache):
    data = {"price": 150.0, "volume": 1000000}
    cache.set("test_key", "prices", data)
    result = cache.get("test_key", "prices")
    assert result == data


def test_cache_miss(cache):
    result = cache.get("nonexistent", "prices")
    assert result is None


def test_cache_expiry(cache):
    data = {"price": 150.0}
    cache.set("test_key", "prices", data)
    # Manually set cached_at to past
    path = cache._path("test_key")
    raw = json.loads(path.read_text())
    raw["cached_at"] = time.time() - 7200  # 2 hours ago, prices TTL is 1h
    path.write_text(json.dumps(raw))
    result = cache.get("test_key", "prices")
    assert result is None


def test_corrupt_file_handling(cache):
    path = cache._path("corrupt_key")
    path.write_text("not valid json{{{")
    result = cache.get("corrupt_key", "prices")
    assert result is None
    assert not path.exists()  # corrupt file removed


def test_invalidate(cache):
    cache.set("test_key", "prices", {"price": 150.0})
    cache.invalidate("test_key")
    assert cache.get("test_key", "prices") is None


def test_clear_all(cache):
    cache.set("key1", "prices", {"a": 1})
    cache.set("key2", "fundamentals", {"b": 2})
    count = cache.clear()
    assert count == 2
    assert cache.get("key1", "prices") is None
    assert cache.get("key2", "fundamentals") is None


def test_clear_category(cache):
    cache.set("key1", "prices", {"a": 1})
    cache.set("key2", "fundamentals", {"b": 2})
    count = cache.clear("prices")
    assert count == 1
    assert cache.get("key1", "prices") is None
    assert cache.get("key2", "fundamentals") is not None


def test_cache_stores_lists(cache):
    data = [{"date": "2024-01-01", "price": 150.0}]
    cache.set("test_list", "prices", data)
    result = cache.get("test_list", "prices")
    assert result == data
