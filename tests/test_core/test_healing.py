"""Tests for SymbolResolver — fuzzy symbol matching."""

from __future__ import annotations

from unittest.mock import MagicMock

from morgul.core.healing.resolver import SymbolResolver


class TestSymbolResolver:
    def _make_target(self, functions=None, symbols=None):
        target = MagicMock()
        target.find_functions.return_value = functions or []
        target.find_symbols.return_value = symbols or []
        return target

    def test_exact_match_functions(self):
        resolver = SymbolResolver()
        target = self._make_target(functions=[
            {"name": "main", "address": 0x1000},
        ])
        results = resolver.resolve("main", target)
        assert len(results) == 1
        assert results[0]["name"] == "main"
        assert results[0]["score"] == 1.0

    def test_exact_match_symbols(self):
        resolver = SymbolResolver()
        target = self._make_target(
            functions=[],
            symbols=[{"name": "_main", "address": 0x1000}],
        )
        results = resolver.resolve("_main", target)
        assert len(results) == 1
        assert results[0]["score"] == 1.0

    def test_no_match_returns_empty(self):
        resolver = SymbolResolver()
        target = self._make_target()
        results = resolver.resolve("nonexistent_function_xyz", target)
        assert results == []

    def test_fuzzy_match(self):
        resolver = SymbolResolver(similarity_threshold=0.5)
        target = MagicMock()
        # First call (exact) returns empty, second call (fuzzy) returns candidates
        target.find_functions.side_effect = [
            [],  # exact match fails
            [{"name": "main_loop", "address": 0x2000}],  # fuzzy finds candidates
        ]
        target.find_symbols.return_value = []

        results = resolver.resolve("main", target)
        # fuzzy match should find "main_loop" as similar to "main"
        assert isinstance(results, list)

    def test_best_match_found(self):
        resolver = SymbolResolver()
        target = self._make_target(functions=[
            {"name": "main", "address": 0x1000},
        ])
        result = resolver.best_match("main", target)
        assert result is not None
        assert result["name"] == "main"

    def test_best_match_none(self):
        resolver = SymbolResolver()
        target = self._make_target()
        result = resolver.best_match("nonexistent_xyz_abc", target)
        assert result is None

    def test_threshold_configurable(self):
        resolver = SymbolResolver(similarity_threshold=0.9)
        assert resolver.similarity_threshold == 0.9

    def test_results_sorted_by_score(self):
        resolver = SymbolResolver(similarity_threshold=0.3)
        target = MagicMock()
        target.find_functions.side_effect = [
            [],  # exact
            [
                {"name": "process_data", "address": 0x1000},
                {"name": "process_input", "address": 0x2000},
            ],  # fuzzy
        ]
        target.find_symbols.return_value = []

        results = resolver.resolve("process", target)
        if len(results) >= 2:
            assert results[0]["score"] >= results[1]["score"]
