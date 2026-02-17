"""Core test fixtures — re-exports root fixtures with core-specific defaults."""

from __future__ import annotations

import pytest


@pytest.fixture()
def tmp_cache_dir(tmp_path):
    """Provide a temporary directory for cache/storage tests."""
    cache_dir = tmp_path / "morgul_cache"
    cache_dir.mkdir()
    return cache_dir
