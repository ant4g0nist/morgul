"""Tests for PythonExecutor — shared execution engine."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from morgul.core.primitives.executor import REPL_SCAFFOLD_NAMES, RESERVED_NAMES, PythonExecutor


def _mock_process():
    frame = MagicMock()
    frame.pc = 0x100003F00
    frame.function_name = "main"

    thread = MagicMock()
    thread.selected_frame = frame

    process = MagicMock()
    process.selected_thread = thread
    process.pid = 12345
    return process


def _make_executor():
    debugger = MagicMock()
    target = MagicMock()
    process = _mock_process()
    return PythonExecutor(debugger, target, process)


class TestNamespace:
    def test_bridge_objects_present(self):
        executor = _make_executor()
        ns = executor.namespace
        assert "debugger" in ns
        assert "target" in ns
        assert "process" in ns
        assert "thread" in ns
        assert "frame" in ns

    def test_memory_utilities_present(self):
        executor = _make_executor()
        ns = executor.namespace
        assert callable(ns["read_string"])
        assert callable(ns["read_pointer"])
        assert callable(ns["read_uint8"])
        assert callable(ns["read_uint16"])
        assert callable(ns["read_uint32"])
        assert callable(ns["read_uint64"])
        assert callable(ns["search_memory"])

    def test_stdlib_present(self):
        executor = _make_executor()
        ns = executor.namespace
        import struct
        assert ns["struct"] is struct

    def test_no_done_function(self):
        """PythonExecutor does not include DONE() — that's REPL-specific."""
        executor = _make_executor()
        assert "DONE" not in executor.namespace


class TestExecute:
    def test_stdout_capture(self):
        executor = _make_executor()
        stdout, stderr, succeeded = executor.execute("print('hello world')")
        assert "hello world" in stdout
        assert stderr == ""
        assert succeeded is True

    def test_stderr_on_error(self):
        executor = _make_executor()
        stdout, stderr, succeeded = executor.execute("1/0")
        assert "ZeroDivisionError" in stderr
        assert succeeded is False

    def test_variable_persistence(self):
        executor = _make_executor()
        executor.execute("my_var = 42")
        stdout, _, succeeded = executor.execute("print(my_var)")
        assert "42" in stdout
        assert succeeded is True

    def test_success_flag(self):
        executor = _make_executor()
        _, _, succeeded = executor.execute("x = 1")
        assert succeeded is True

        _, _, succeeded = executor.execute("raise ValueError('boom')")
        assert succeeded is False

    def test_thread_frame_refresh(self):
        executor = _make_executor()
        original_frame = executor.namespace["frame"]
        executor.execute("x = 1")
        # Frame should still be present (refreshed from process)
        assert executor.namespace["frame"] is not None

    def test_truncation(self):
        executor = _make_executor()
        stdout, _, _ = executor.execute("print('x' * 30000)")
        assert "truncated" in stdout


class TestRefresh:
    def test_refresh_updates_thread_and_frame(self):
        executor = _make_executor()
        new_frame = MagicMock()
        new_thread = MagicMock()
        new_thread.selected_frame = new_frame
        executor.process.selected_thread = new_thread

        executor.refresh()
        assert executor.namespace["thread"] is new_thread
        assert executor.namespace["frame"] is new_frame

    def test_refresh_handles_none_thread(self):
        executor = _make_executor()
        executor.process.selected_thread = None

        executor.refresh()
        assert executor.namespace["thread"] is None
        assert executor.namespace["frame"] is None


class TestScaffoldProtection:
    def test_overwritten_bridge_object_restored(self):
        executor = _make_executor()
        original_debugger = executor.namespace["debugger"]
        executor.execute("debugger = 'oops'")
        assert executor.namespace["debugger"] is original_debugger

    def test_overwritten_builtin_restored(self):
        executor = _make_executor()
        executor.execute("print = None")
        assert executor.namespace["print"] is print

    def test_user_variables_survive_scaffold_restore(self):
        executor = _make_executor()
        executor.execute("my_var = 42")
        assert executor.namespace["my_var"] == 42

    def test_update_scaffold_registers_new_entry(self):
        executor = _make_executor()
        sentinel = object()
        executor.update_scaffold("MY_SPECIAL", sentinel)
        assert executor.namespace["MY_SPECIAL"] is sentinel
        # Overwrite it via exec, then verify it's restored
        executor.execute("MY_SPECIAL = 'overwritten'")
        assert executor.namespace["MY_SPECIAL"] is sentinel


class TestInjectTools:
    def test_inject_tools_simple_callable(self):
        """Callable tool is available in namespace."""
        executor = _make_executor()
        my_fn = lambda x: x * 2
        descs = executor.inject_tools({"my_helper": my_fn})
        assert executor.namespace["my_helper"] is my_fn
        assert descs == [("my_helper", "callable(my_helper)")]

    def test_inject_tools_data_value(self):
        """Non-callable data value is available in namespace."""
        executor = _make_executor()
        descs = executor.inject_tools({"BLOCK_SIZE": 4096})
        assert executor.namespace["BLOCK_SIZE"] == 4096
        assert descs == [("BLOCK_SIZE", "")]

    def test_inject_tools_rich_format(self):
        """Rich format {'tool': fn, 'description': '...'} is supported."""
        executor = _make_executor()
        my_fn = lambda addr: addr
        descs = executor.inject_tools({
            "decode_header": {
                "tool": my_fn,
                "description": "Parse Mach-O header at addr",
            }
        })
        assert executor.namespace["decode_header"] is my_fn
        assert descs == [("decode_header", "Parse Mach-O header at addr")]

    def test_inject_tools_reserved_name_rejected(self):
        """ValueError raised if tool name conflicts with RESERVED_NAMES."""
        executor = _make_executor()
        with pytest.raises(ValueError, match="conflicts with reserved name"):
            executor.inject_tools({"debugger": lambda: None})

    def test_inject_tools_scaffold_name_rejected(self):
        """ValueError raised if tool name conflicts with REPL_SCAFFOLD_NAMES."""
        executor = _make_executor()
        with pytest.raises(ValueError, match="conflicts with reserved name"):
            executor.inject_tools({"DONE": lambda: None})

    def test_inject_tools_scaffold_protected(self):
        """Injected tools survive overwrite in exec()."""
        executor = _make_executor()
        my_fn = lambda: "original"
        executor.inject_tools({"my_tool": my_fn})
        executor.execute("my_tool = 'overwritten'")
        assert executor.namespace["my_tool"] is my_fn
