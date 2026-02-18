"""Integration tests that require a real LLDB installation.

Run with: PYTHONPATH="$(lldb -P)" uv run pytest tests/ -v -m lldb
"""

from __future__ import annotations

import os
import sys

import pytest

# Skip entire module if LLDB is not available
try:
    import lldb  # noqa: F401
    HAS_LLDB = True
except ImportError:
    HAS_LLDB = False

pytestmark = pytest.mark.lldb


@pytest.fixture()
def debugger():
    """Create a real LLDB Debugger for integration tests."""
    if not HAS_LLDB:
        pytest.skip("LLDB not available")
    from morgul.bridge import Debugger
    dbg = Debugger()
    yield dbg
    dbg.destroy()


@pytest.mark.skipif(not HAS_LLDB, reason="LLDB not available")
class TestLLDBIntegration:
    def test_debugger_creates(self, debugger):
        assert debugger is not None
        assert debugger._sb is not None

    def test_create_target_ls(self, debugger):
        """Create a target for /bin/ls (exists on all macOS/Linux)."""
        ls_path = "/bin/ls"
        if not os.path.exists(ls_path):
            pytest.skip(f"{ls_path} not found")
        target = debugger.create_target(ls_path)
        assert target is not None
        assert target.path != ""

    def test_target_triple(self, debugger):
        ls_path = "/bin/ls"
        if not os.path.exists(ls_path):
            pytest.skip(f"{ls_path} not found")
        target = debugger.create_target(ls_path)
        triple = target.triple
        assert triple != ""
        # Should contain architecture info
        assert any(arch in triple for arch in ["x86_64", "arm64", "aarch64"])

    def test_breakpoint_on_main(self, debugger):
        ls_path = "/bin/ls"
        if not os.path.exists(ls_path):
            pytest.skip(f"{ls_path} not found")
        target = debugger.create_target(ls_path)
        bp = target.breakpoint_create_by_name("main")
        assert bp.id > 0
        if bp.num_locations == 0:
            pytest.skip("'main' symbol not resolvable (stripped binary)")

    def test_execute_command(self, debugger):
        result = debugger.execute_command("version")
        assert result.succeeded
        assert "lldb" in result.output.lower() or len(result.output) > 0

    def test_modules_listed(self, debugger):
        ls_path = "/bin/ls"
        if not os.path.exists(ls_path):
            pytest.skip(f"{ls_path} not found")
        target = debugger.create_target(ls_path)
        modules = target.modules
        assert len(modules) >= 1

    def test_find_functions(self, debugger):
        ls_path = "/bin/ls"
        if not os.path.exists(ls_path):
            pytest.skip(f"{ls_path} not found")
        target = debugger.create_target(ls_path)
        funcs = target.find_functions("main")
        if not funcs:
            pytest.skip("'main' symbol not found (stripped binary)")
        assert funcs[0]["name"] == "main"
