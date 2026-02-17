"""Tests for command execution helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from morgul.bridge.commands import format_disassembly, run_command, run_commands
from morgul.bridge.types import CommandResult


class TestRunCommand:
    def test_run_command(self, mock_debugger):
        result = run_command(mock_debugger, "bt")
        assert isinstance(result, CommandResult)
        mock_debugger.execute_command.assert_called_once_with("bt")

    def test_run_commands(self, mock_debugger):
        results = run_commands(mock_debugger, ["bt", "register read"])
        assert len(results) == 2
        assert mock_debugger.execute_command.call_count == 2


class TestFormatDisassembly:
    def test_with_function_name(self):
        frame = MagicMock()
        frame.function_name = "main"
        frame.pc = 0x100003F00
        frame.disassemble.return_value = "  0x100003f00: push rbp"

        result = format_disassembly(frame, count=10)
        assert "main" in result
        assert "0x100003f00" in result
        assert "push rbp" in result

    def test_without_function_name(self):
        frame = MagicMock()
        frame.function_name = None
        frame.pc = 0x100003F00
        frame.disassemble.return_value = "  0x100003f00: nop"

        result = format_disassembly(frame, count=5)
        assert "0x100003f00" in result
        assert "nop" in result
