"""Tests for Debugger wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from morgul.bridge.types import CommandResult


class TestDebugger:
    """Test the Debugger class with a mocked lldb module."""

    def _make_debugger(self, mock_sb_debugger):
        """Create a Debugger with a pre-built mock SBDebugger."""
        with patch("morgul.bridge.debugger.lldb") as mock_lldb:
            mock_lldb.SBDebugger.Initialize.return_value = None
            mock_lldb.SBDebugger.Create.return_value = mock_sb_debugger
            mock_lldb.SBDebugger.Destroy.return_value = None
            mock_lldb.__bool__ = lambda self: True
            # Make lldb truthy so _require_lldb passes
            from morgul.bridge.debugger import Debugger
            dbg = Debugger()
        return dbg

    def test_create_target(self, mock_sb_debugger):
        sb_target = MagicMock()
        sb_target.IsValid.return_value = True
        sb_target.__bool__ = lambda self: True
        mock_sb_debugger.CreateTarget.return_value = sb_target

        dbg = self._make_debugger(mock_sb_debugger)
        target = dbg.create_target("/tmp/a.out")
        assert target is not None

    def test_create_target_failure(self, mock_sb_debugger):
        mock_sb_debugger.CreateTarget.return_value = None
        dbg = self._make_debugger(mock_sb_debugger)
        with pytest.raises(RuntimeError, match="Failed to create target"):
            dbg.create_target("/nonexistent")

    def test_execute_command(self, mock_sb_debugger):
        ret_obj = MagicMock()
        ret_obj.GetOutput.return_value = "frame #0: main"
        ret_obj.GetError.return_value = ""
        ret_obj.Succeeded.return_value = True

        interpreter = MagicMock()
        mock_sb_debugger.GetCommandInterpreter.return_value = interpreter

        dbg = self._make_debugger(mock_sb_debugger)
        with patch("morgul.bridge.debugger.lldb") as mock_lldb:
            mock_lldb.SBCommandReturnObject.return_value = ret_obj
            result = dbg.execute_command("bt")

        assert isinstance(result, CommandResult)
        assert result.succeeded
        assert "main" in result.output

    def test_async_mode(self, mock_sb_debugger):
        dbg = self._make_debugger(mock_sb_debugger)
        assert dbg.async_mode is False

    def test_set_async_mode(self, mock_sb_debugger):
        dbg = self._make_debugger(mock_sb_debugger)
        dbg.async_mode = True
        mock_sb_debugger.SetAsync.assert_called_with(True)

    def test_destroy(self, mock_sb_debugger):
        dbg = self._make_debugger(mock_sb_debugger)
        with patch("morgul.bridge.debugger.lldb") as mock_lldb:
            dbg.destroy()
        assert dbg._sb is None

    def test_context_manager(self, mock_sb_debugger):
        dbg = self._make_debugger(mock_sb_debugger)
        with patch("morgul.bridge.debugger.lldb"):
            with dbg:
                pass
        assert dbg._sb is None

    def test_attach(self, mock_sb_debugger):
        sb_target = MagicMock()
        sb_target.IsValid.return_value = True
        sb_target.__bool__ = lambda self: True

        sb_process = MagicMock()
        error = MagicMock()
        error.Fail.return_value = False
        sb_target.AttachToProcessWithID.return_value = sb_process

        mock_sb_debugger.CreateTarget.return_value = sb_target
        mock_sb_debugger.GetListener.return_value = MagicMock()

        dbg = self._make_debugger(mock_sb_debugger)
        with patch("morgul.bridge.debugger.lldb") as mock_lldb:
            mock_lldb.SBError.return_value = error
            target, process = dbg.attach(12345)
        assert target is not None
        assert process is not None

    def test_attach_by_name(self, mock_sb_debugger):
        sb_target = MagicMock()
        sb_target.IsValid.return_value = True
        sb_target.__bool__ = lambda self: True

        sb_process = MagicMock()
        error = MagicMock()
        error.Fail.return_value = False
        sb_target.AttachToProcessWithName.return_value = sb_process

        mock_sb_debugger.CreateTarget.return_value = sb_target
        mock_sb_debugger.GetListener.return_value = MagicMock()

        dbg = self._make_debugger(mock_sb_debugger)
        with patch("morgul.bridge.debugger.lldb") as mock_lldb:
            mock_lldb.SBError.return_value = error
            target, process = dbg.attach_by_name("Safari")
        assert target is not None
        assert process is not None

    def test_attach_failure(self, mock_sb_debugger):
        sb_target = MagicMock()
        sb_target.IsValid.return_value = True
        sb_target.__bool__ = lambda self: True

        error = MagicMock()
        error.Fail.return_value = True
        error.__str__ = lambda self: "No such process"

        mock_sb_debugger.CreateTarget.return_value = sb_target
        mock_sb_debugger.GetListener.return_value = MagicMock()

        dbg = self._make_debugger(mock_sb_debugger)
        with patch("morgul.bridge.debugger.lldb") as mock_lldb:
            mock_lldb.SBError.return_value = error
            with pytest.raises(RuntimeError, match="Failed to attach to PID"):
                dbg.attach(99999)

    def test_attach_by_name_failure(self, mock_sb_debugger):
        sb_target = MagicMock()
        sb_target.IsValid.return_value = True
        sb_target.__bool__ = lambda self: True

        error = MagicMock()
        error.Fail.return_value = True
        error.__str__ = lambda self: "process not found"

        mock_sb_debugger.CreateTarget.return_value = sb_target
        mock_sb_debugger.GetListener.return_value = MagicMock()

        dbg = self._make_debugger(mock_sb_debugger)
        with patch("morgul.bridge.debugger.lldb") as mock_lldb:
            mock_lldb.SBError.return_value = error
            with pytest.raises(RuntimeError, match="Failed to attach to process"):
                dbg.attach_by_name("NonExistent")

    def test_attach_empty_target_failure(self, mock_sb_debugger):
        mock_sb_debugger.CreateTarget.return_value = None

        dbg = self._make_debugger(mock_sb_debugger)
        with patch("morgul.bridge.debugger.lldb") as mock_lldb:
            with pytest.raises(RuntimeError, match="Failed to create empty target"):
                dbg.attach(123)
