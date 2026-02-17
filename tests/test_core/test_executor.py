"""Tests for PythonExecutor — shared execution engine."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from morgul.core.primitives.executor import PythonExecutor


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
