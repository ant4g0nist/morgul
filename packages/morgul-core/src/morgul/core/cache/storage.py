"""File-based cache storage."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FileStorage:
    """Simple file-based key-value storage for cache entries."""

    def __init__(self, directory: str = ".morgul/cache"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _key_path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str) -> Any | None:
        """Retrieve a cached value by key."""
        path = self._key_path(key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to read cache entry: %s", key)
            return None

    def set(self, key: str, value: Any) -> None:
        """Store a value in the cache."""
        path = self._key_path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, default=str))
        except OSError:
            logger.warning("Failed to write cache entry: %s", key)

    def delete(self, key: str) -> bool:
        """Delete a cache entry."""
        path = self._key_path(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        for path in self.directory.glob("*.json"):
            path.unlink()

    def keys(self) -> list[str]:
        """List all cache keys."""
        return [p.stem for p in self.directory.glob("*.json")]
