"""Content-addressed cache keyed on function bytes hash (ASLR-resistant)."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from morgul.core.cache.storage import FileStorage

logger = logging.getLogger(__name__)


class ContentCache:
    """Content-addressed cache that keys on function bytes, making it ASLR-resistant.

    Instead of caching by address (which changes with ASLR), we hash the actual
    code bytes at the function's location. This means cache entries survive
    process restarts and ASLR re-randomization.
    """

    def __init__(self, storage: FileStorage | None = None):
        self.storage = storage or FileStorage()

    def make_key(self, code_bytes: bytes, suffix: str = "") -> str:
        """Create a content-addressed cache key from function bytes.

        Args:
            code_bytes: The raw bytes of the function/code region.
            suffix: Optional suffix to differentiate cache types (e.g., "decompile", "analysis").
        """
        h = hashlib.sha256(code_bytes).hexdigest()[:16]
        return f"{h}_{suffix}" if suffix else h

    def get(self, code_bytes: bytes, suffix: str = "") -> Any | None:
        """Look up a cached value by code content."""
        key = self.make_key(code_bytes, suffix)
        return self.storage.get(key)

    def set(self, code_bytes: bytes, value: Any, suffix: str = "") -> None:
        """Store a value keyed by code content."""
        key = self.make_key(code_bytes, suffix)
        self.storage.set(key, value)

    def get_by_key(self, key: str) -> Any | None:
        """Direct key lookup."""
        return self.storage.get(key)

    def set_by_key(self, key: str, value: Any) -> None:
        """Direct key storage."""
        self.storage.set(key, value)

    def clear(self) -> None:
        """Clear the entire cache."""
        self.storage.clear()
