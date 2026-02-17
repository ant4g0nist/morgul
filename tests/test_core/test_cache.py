"""Tests for ContentCache — content-addressed cache keyed on function bytes hash."""

from __future__ import annotations

from morgul.core.cache.cache import ContentCache
from morgul.core.cache.storage import FileStorage


class TestContentCache:
    def test_make_key_deterministic(self):
        cache = ContentCache()
        key1 = cache.make_key(b"\x55\x48\x89\xe5")
        key2 = cache.make_key(b"\x55\x48\x89\xe5")
        assert key1 == key2

    def test_make_key_different_bytes(self):
        cache = ContentCache()
        key1 = cache.make_key(b"\x55\x48\x89\xe5")
        key2 = cache.make_key(b"\x90\x90\x90\x90")
        assert key1 != key2

    def test_make_key_with_suffix(self):
        cache = ContentCache()
        key1 = cache.make_key(b"\x55", suffix="decompile")
        key2 = cache.make_key(b"\x55", suffix="analysis")
        assert key1 != key2
        assert key1.endswith("_decompile")

    def test_set_and_get(self, tmp_cache_dir):
        storage = FileStorage(directory=str(tmp_cache_dir))
        cache = ContentCache(storage=storage)
        code = b"\x55\x48\x89\xe5"
        cache.set(code, {"decompiled": "push rbp; mov rbp, rsp"})
        result = cache.get(code)
        assert result["decompiled"] == "push rbp; mov rbp, rsp"

    def test_get_missing(self, tmp_cache_dir):
        storage = FileStorage(directory=str(tmp_cache_dir))
        cache = ContentCache(storage=storage)
        assert cache.get(b"\xcc") is None

    def test_set_and_get_by_key(self, tmp_cache_dir):
        storage = FileStorage(directory=str(tmp_cache_dir))
        cache = ContentCache(storage=storage)
        cache.set_by_key("custom_key", [1, 2, 3])
        assert cache.get_by_key("custom_key") == [1, 2, 3]

    def test_clear(self, tmp_cache_dir):
        storage = FileStorage(directory=str(tmp_cache_dir))
        cache = ContentCache(storage=storage)
        cache.set(b"\x01", "a")
        cache.set(b"\x02", "b")
        cache.clear()
        assert cache.get(b"\x01") is None
        assert cache.get(b"\x02") is None
