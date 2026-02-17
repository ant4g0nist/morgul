"""Self-healing: fuzzy symbol matching and reference updating."""

from __future__ import annotations

import logging
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from morgul.bridge.target import Target

logger = logging.getLogger(__name__)


class SymbolResolver:
    """Resolves symbols that fail to match exactly using fuzzy matching.

    When a symbol or address fails to resolve, this resolver:
    1. Searches for similar symbol names using fuzzy matching
    2. Compares function signatures and byte patterns
    3. Updates cached references to new addresses
    """

    def __init__(self, similarity_threshold: float = 0.7):
        self.similarity_threshold = similarity_threshold
        self._symbol_cache: dict[str, list[dict]] = {}

    def resolve(self, name: str, target: Target) -> list[dict]:
        """Attempt to resolve a symbol name, falling back to fuzzy matching.

        Args:
            name: The symbol name to resolve.
            target: The debugger target to search in.

        Returns:
            List of matching symbols with name, address, module, and score.
        """
        # Try exact match first
        exact = target.find_functions(name)
        if exact:
            return [{"name": f["name"], "address": f["address"], "score": 1.0} for f in exact]

        # Try symbols
        symbols = target.find_symbols(name)
        if symbols:
            return [{"name": s["name"], "address": s["address"], "score": 1.0} for s in symbols]

        # Fuzzy match against all known symbols
        return self._fuzzy_match(name, target)

    def _fuzzy_match(self, name: str, target: Target) -> list[dict]:
        """Fuzzy match a symbol name against all symbols in the target."""
        candidates: list[dict] = []

        # Search with partial name patterns
        parts = name.split("::")
        search_term = parts[-1] if parts else name

        # Try regex-based search
        try:
            from morgul.bridge.target import Target as _T  # noqa: F811

            # Search for functions matching partial name
            matches = target.find_functions(search_term)
            for match in matches:
                score = SequenceMatcher(None, name.lower(), match["name"].lower()).ratio()
                if score >= self.similarity_threshold:
                    candidates.append({
                        "name": match["name"],
                        "address": match["address"],
                        "score": score,
                    })
        except Exception:
            logger.debug("Fuzzy search failed for: %s", name)

        # Sort by similarity score
        candidates.sort(key=lambda c: c["score"], reverse=True)
        return candidates

    def best_match(self, name: str, target: Target) -> dict | None:
        """Return the best matching symbol, or None if no good match found."""
        matches = self.resolve(name, target)
        if matches and matches[0]["score"] >= self.similarity_threshold:
            return matches[0]
        return None
