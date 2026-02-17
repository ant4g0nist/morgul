"""Tests for capture_snapshot()."""

from __future__ import annotations

from unittest.mock import MagicMock

from morgul.bridge.types import RegisterValue, Variable
from morgul.core.context.snapshot import capture_snapshot
from morgul.core.types.context import ProcessSnapshot


class TestCaptureSnapshot:
    def _make_frame(self):
        frame = MagicMock()
        frame.pc = 0x100003F00
        frame.registers = [RegisterValue(name="rax", value=0x42, size=8)]
        frame.variables.return_value = [
            Variable(name="argc", type_name="int", value="1", address=0x1000, size=4),
        ]
        frame.disassemble.return_value = "  0x100003f00: push rbp"
        frame.index = 0
        frame.function_name = "main"
        frame.module_name = "a.out"
        frame.line_entry = {"file": "/tmp/main.c", "line": 10}
        return frame

    def _make_thread(self, frame):
        thread = MagicMock()
        thread.id = 1
        thread.name = "main"
        thread.stop_reason = "breakpoint"
        thread.selected_frame = frame
        thread.get_frames.return_value = [frame]
        return thread

    def _make_process(self, thread):
        process = MagicMock()
        process.state = "stopped"
        process.selected_thread = thread
        process._target = None
        return process

    def test_basic_snapshot(self):
        frame = self._make_frame()
        thread = self._make_thread(frame)
        process = self._make_process(thread)
        snap = capture_snapshot(process)
        assert isinstance(snap, ProcessSnapshot)
        assert snap.process_state == "stopped"
        assert snap.pc == 0x100003F00

    def test_registers_captured(self):
        frame = self._make_frame()
        thread = self._make_thread(frame)
        process = self._make_process(thread)
        snap = capture_snapshot(process)
        assert len(snap.registers) == 1
        assert snap.registers[0].name == "rax"

    def test_stack_trace_captured(self):
        frame = self._make_frame()
        thread = self._make_thread(frame)
        process = self._make_process(thread)
        snap = capture_snapshot(process)
        assert snap.stack_trace is not None
        assert snap.stack_trace.thread_id == 1
        assert len(snap.stack_trace.frames) == 1

    def test_disassembly_captured(self):
        frame = self._make_frame()
        thread = self._make_thread(frame)
        process = self._make_process(thread)
        snap = capture_snapshot(process)
        assert "push rbp" in snap.disassembly

    def test_variables_captured(self):
        frame = self._make_frame()
        thread = self._make_thread(frame)
        process = self._make_process(thread)
        snap = capture_snapshot(process)
        assert len(snap.variables) == 1
        assert snap.variables[0]["name"] == "argc"

    def test_no_thread(self):
        process = MagicMock()
        process.state = "exited"
        process.selected_thread = None
        process._target = None
        snap = capture_snapshot(process)
        assert snap.stack_trace is None
        assert snap.registers == []

    def test_explicit_frame(self):
        frame = self._make_frame()
        thread = self._make_thread(frame)
        process = self._make_process(thread)
        snap = capture_snapshot(process, frame=frame)
        assert snap.pc == 0x100003F00

    def test_modules_captured(self):
        frame = self._make_frame()
        thread = self._make_thread(frame)
        process = self._make_process(thread)

        mod = MagicMock()
        mod.name = "a.out"
        mod.path = "/tmp/a.out"
        mod.uuid = "UUID-1"
        mod.base_address = 0x100000000

        target = MagicMock()
        target.modules = [mod]
        target.triple = "arm64-apple-macosx15.4.0"
        process._target = target

        snap = capture_snapshot(process)
        assert len(snap.modules) == 1
        assert snap.modules[0].name == "a.out"
