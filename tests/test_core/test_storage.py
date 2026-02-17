"""Tests for FileStorage — file-based key-value cache storage."""

from __future__ import annotations

import json

from morgul.core.cache.storage import FileStorage


class TestFileStorage:
    def test_init_creates_directory(self, tmp_cache_dir):
        sub = tmp_cache_dir / "sub"
        storage = FileStorage(directory=str(sub))
        assert sub.exists()

    def test_set_and_get(self, tmp_cache_dir):
        storage = FileStorage(directory=str(tmp_cache_dir))
        storage.set("key1", {"data": 42})
        assert storage.get("key1") == {"data": 42}

    def test_get_missing_key_returns_none(self, tmp_cache_dir):
        storage = FileStorage(directory=str(tmp_cache_dir))
        assert storage.get("nonexistent") is None

    def test_get_corrupt_json_returns_none(self, tmp_cache_dir):
        storage = FileStorage(directory=str(tmp_cache_dir))
        path = tmp_cache_dir / "bad.json"
        path.write_text("not valid json{{{")
        assert storage.get("bad") is None

    def test_delete_existing_key(self, tmp_cache_dir):
        storage = FileStorage(directory=str(tmp_cache_dir))
        storage.set("key1", "value")
        assert storage.delete("key1") is True
        assert storage.get("key1") is None

    def test_delete_missing_key(self, tmp_cache_dir):
        storage = FileStorage(directory=str(tmp_cache_dir))
        assert storage.delete("nonexistent") is False

    def test_clear(self, tmp_cache_dir):
        storage = FileStorage(directory=str(tmp_cache_dir))
        storage.set("a", 1)
        storage.set("b", 2)
        storage.clear()
        assert storage.keys() == []

    def test_keys(self, tmp_cache_dir):
        storage = FileStorage(directory=str(tmp_cache_dir))
        storage.set("alpha", 1)
        storage.set("beta", 2)
        keys = sorted(storage.keys())
        assert keys == ["alpha", "beta"]

    def test_set_serialises_non_json_types(self, tmp_cache_dir):
        """Non-JSON-serialisable objects should be coerced via default=str."""
        storage = FileStorage(directory=str(tmp_cache_dir))
        from datetime import datetime
        storage.set("dt", {"ts": datetime(2025, 1, 1)})
        result = storage.get("dt")
        assert "2025" in result["ts"]
