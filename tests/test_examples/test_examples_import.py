"""Tests that example scripts are valid Python (compile without errors)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"


def _example_files():
    """Collect all .py files in the examples directory."""
    if not EXAMPLES_DIR.exists():
        return []
    return sorted(EXAMPLES_DIR.glob("*.py"))


@pytest.mark.parametrize("example_path", _example_files(), ids=lambda p: p.name)
def test_example_compiles(example_path):
    """Each example script should be valid Python that compiles without errors."""
    source = example_path.read_text()
    try:
        compile(source, str(example_path), "exec")
    except SyntaxError as exc:
        pytest.fail(f"Syntax error in {example_path.name}: {exc}")


@pytest.mark.parametrize("example_path", _example_files(), ids=lambda p: p.name)
def test_example_parses_ast(example_path):
    """Each example should produce a valid AST."""
    source = example_path.read_text()
    tree = ast.parse(source)
    assert isinstance(tree, ast.Module)
    assert len(tree.body) > 0, f"{example_path.name} is empty"


def test_examples_directory_exists():
    """The examples directory should exist and contain Python files."""
    assert EXAMPLES_DIR.exists(), f"Examples directory not found: {EXAMPLES_DIR}"
    py_files = list(EXAMPLES_DIR.glob("*.py"))
    assert len(py_files) >= 1, "No example .py files found"


def test_all_examples_have_docstrings():
    """Each example should start with a module docstring."""
    for path in _example_files():
        source = path.read_text()
        tree = ast.parse(source)
        docstring = ast.get_docstring(tree)
        assert docstring is not None, f"{path.name} is missing a module docstring"
