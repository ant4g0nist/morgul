"""Tests for Process wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from morgul.bridge.process import Process
from morgul.bridge.types import ProcessState


class TestProcess:
    def _make_process(self, mock_sb_process):
        target = MagicMock()
        # Avoid triggering _build_state_map which needs real lldb
        with patch("morgul.bridge.process._build_state_map"):
            return Process(mock_sb_process, target)

    def test_pid(self, mock_sb_process):
        proc = self._make_process(mock_sb_process)
        assert proc.pid == 12345

    def test_exit_status(self, mock_sb_process):
        proc = self._make_process(mock_sb_process)
        assert proc.exit_status == 0

    def test_exit_description(self, mock_sb_process):
        proc = self._make_process(mock_sb_process)
        assert proc.exit_description == ""

    def test_num_threads(self, mock_sb_process):
        proc = self._make_process(mock_sb_process)
        assert proc.num_threads == 1

    def test_threads(self, mock_sb_process):
        mock_thread = MagicMock()
        mock_sb_process.GetThreadAtIndex.return_value = mock_thread
        proc = self._make_process(mock_sb_process)
        threads = proc.threads
        assert len(threads) == 1

    def test_selected_thread(self, mock_sb_process):
        mock_thread = MagicMock()
        mock_sb_process.GetSelectedThread.return_value = mock_thread
        proc = self._make_process(mock_sb_process)
        assert proc.selected_thread is not None

    def test_continue(self, mock_sb_process, mock_sb_error_success):
        mock_sb_process.Continue.return_value = mock_sb_error_success
        proc = self._make_process(mock_sb_process)
        proc.continue_()
        mock_sb_process.Continue.assert_called_once()

    def test_continue_failure(self, mock_sb_process):
        err = MagicMock()
        err.Success.return_value = False
        err.__bool__ = lambda self: True
        mock_sb_process.Continue.return_value = err
        proc = self._make_process(mock_sb_process)
        with pytest.raises(RuntimeError, match="Failed to continue"):
            proc.continue_()

    def test_stop(self, mock_sb_process, mock_sb_error_success):
        mock_sb_process.Stop.return_value = mock_sb_error_success
        proc = self._make_process(mock_sb_process)
        proc.stop()
        mock_sb_process.Stop.assert_called_once()

    def test_kill(self, mock_sb_process, mock_sb_error_success):
        mock_sb_process.Kill.return_value = mock_sb_error_success
        proc = self._make_process(mock_sb_process)
        proc.kill()
        mock_sb_process.Kill.assert_called_once()

    def test_detach(self, mock_sb_process, mock_sb_error_success):
        mock_sb_process.Detach.return_value = mock_sb_error_success
        proc = self._make_process(mock_sb_process)
        proc.detach()
        mock_sb_process.Detach.assert_called_once()

    def test_read_memory(self, mock_sb_process):
        error = MagicMock()
        error.Fail.return_value = False
        mock_sb_process.ReadMemory.return_value = b"\xAB\xCD"

        proc = self._make_process(mock_sb_process)
        with patch("morgul.bridge.process.lldb") as mock_lldb:
            mock_lldb.SBError.return_value = error
            data = proc.read_memory(0x1000, 2)
        assert data == b"\xAB\xCD"

    def test_read_memory_failure(self, mock_sb_process):
        error = MagicMock()
        error.Fail.return_value = True
        error.__str__ = lambda self: "read failed"
        mock_sb_process.ReadMemory.return_value = None

        proc = self._make_process(mock_sb_process)
        with patch("morgul.bridge.process.lldb") as mock_lldb:
            mock_lldb.SBError.return_value = error
            with pytest.raises(RuntimeError, match="Failed to read"):
                proc.read_memory(0x1000, 2)

    def test_write_memory(self, mock_sb_process):
        error = MagicMock()
        error.Fail.return_value = False
        mock_sb_process.WriteMemory.return_value = 4

        proc = self._make_process(mock_sb_process)
        with patch("morgul.bridge.process.lldb") as mock_lldb:
            mock_lldb.SBError.return_value = error
            written = proc.write_memory(0x1000, b"\x01\x02\x03\x04")
        assert written == 4

    def test_write_memory_failure(self, mock_sb_process):
        error = MagicMock()
        error.Fail.return_value = True
        error.__str__ = lambda self: "write failed"

        proc = self._make_process(mock_sb_process)
        with patch("morgul.bridge.process.lldb") as mock_lldb:
            mock_lldb.SBError.return_value = error
            with pytest.raises(RuntimeError, match="Failed to write"):
                proc.write_memory(0x1000, b"\x01\x02")
