"""Tests for Target wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from morgul.bridge.target import Target
from morgul.bridge.types import ModuleInfo


class TestTarget:
    def test_path(self, mock_sb_target):
        target = Target(mock_sb_target)
        assert target.path == "/tmp/a.out"

    def test_path_no_executable(self, mock_sb_target):
        mock_sb_target.GetExecutable.return_value = None
        target = Target(mock_sb_target)
        assert target.path == ""

    def test_triple(self, mock_sb_target):
        target = Target(mock_sb_target)
        assert "arm64" in target.triple

    def test_modules_empty(self, mock_sb_target):
        target = Target(mock_sb_target)
        assert target.modules == []

    def test_modules_with_entries(self, mock_sb_target):
        mod = MagicMock()
        mod.IsValid.return_value = True
        fs = MagicMock()
        fs.IsValid.return_value = True
        fs.GetFilename.return_value = "a.out"
        fs.__str__ = lambda self: "/tmp/a.out"
        mod.GetFileSpec.return_value = fs
        mod.GetUUIDString.return_value = "UUID-123"
        mod.GetNumSections.return_value = 0

        mock_sb_target.GetNumModules.return_value = 1
        mock_sb_target.GetModuleAtIndex.return_value = mod

        target = Target(mock_sb_target)
        modules = target.modules
        assert len(modules) == 1
        assert modules[0].name == "a.out"

    def test_breakpoints_empty(self, mock_sb_target):
        target = Target(mock_sb_target)
        assert target.breakpoints == []

    def test_breakpoint_create_by_name(self, mock_sb_target):
        bp_sb = MagicMock()
        bp_sb.IsValid.return_value = True
        bp_sb.__bool__ = lambda self: True
        mock_sb_target.BreakpointCreateByName.return_value = bp_sb

        target = Target(mock_sb_target)
        bp = target.breakpoint_create_by_name("main")
        assert bp is not None

    def test_breakpoint_create_by_name_failure(self, mock_sb_target):
        mock_sb_target.BreakpointCreateByName.return_value = None
        target = Target(mock_sb_target)
        with pytest.raises(RuntimeError, match="Failed to create breakpoint"):
            target.breakpoint_create_by_name("nonexistent")

    def test_breakpoint_create_by_name_with_module(self, mock_sb_target):
        bp_sb = MagicMock()
        bp_sb.IsValid.return_value = True
        bp_sb.__bool__ = lambda self: True
        mock_sb_target.BreakpointCreateByName.return_value = bp_sb

        target = Target(mock_sb_target)
        bp = target.breakpoint_create_by_name("main", module="a.out")
        mock_sb_target.BreakpointCreateByName.assert_called_with("main", "a.out")

    def test_breakpoint_create_by_address(self, mock_sb_target):
        bp_sb = MagicMock()
        bp_sb.IsValid.return_value = True
        bp_sb.__bool__ = lambda self: True
        mock_sb_target.BreakpointCreateByAddress.return_value = bp_sb

        target = Target(mock_sb_target)
        bp = target.breakpoint_create_by_address(0x100003F00)
        assert bp is not None

    def test_breakpoint_create_by_address_failure(self, mock_sb_target):
        mock_sb_target.BreakpointCreateByAddress.return_value = None
        target = Target(mock_sb_target)
        with pytest.raises(RuntimeError, match="Failed to create breakpoint"):
            target.breakpoint_create_by_address(0xDEAD)

    def test_breakpoint_create_by_regex(self, mock_sb_target):
        bp_sb = MagicMock()
        bp_sb.IsValid.return_value = True
        bp_sb.__bool__ = lambda self: True
        mock_sb_target.BreakpointCreateByRegex.return_value = bp_sb

        target = Target(mock_sb_target)
        bp = target.breakpoint_create_by_regex("main.*")
        assert bp is not None

    def test_find_functions_empty(self, mock_sb_target):
        target = Target(mock_sb_target)
        with patch("morgul.bridge.target.lldb") as mock_lldb:
            mock_lldb.eFunctionNameTypeAuto = 0
            results = target.find_functions("main")
        assert results == []

    def test_find_symbols_empty(self, mock_sb_target):
        target = Target(mock_sb_target)
        results = target.find_symbols("main")
        assert results == []

    def test_read_memory(self, mock_sb_target):
        sb_process = MagicMock()
        sb_process.IsValid.return_value = True
        sb_process.__bool__ = lambda self: True
        error = MagicMock()
        error.Fail.return_value = False
        sb_process.ReadMemory.return_value = b"\xDE\xAD"
        mock_sb_target.GetProcess.return_value = sb_process

        target = Target(mock_sb_target)
        with patch("morgul.bridge.target.lldb") as mock_lldb:
            mock_lldb.SBError.return_value = error
            data = target.read_memory(0x1000, 2)
        assert data == b"\xDE\xAD"

    def test_read_memory_no_process(self, mock_sb_target):
        mock_sb_target.GetProcess.return_value = None
        target = Target(mock_sb_target)
        with pytest.raises(RuntimeError, match="No process"):
            target.read_memory(0x1000, 2)

    def test_resolve_address(self, mock_sb_target):
        sb_addr = MagicMock()
        sb_addr.IsValid.return_value = False
        mock_sb_target.ResolveLoadAddress.return_value = sb_addr

        target = Target(mock_sb_target)
        result = target.resolve_address(0x100003F00)
        assert result["address"] == 0x100003F00

    def test_launch(self, mock_sb_target):
        error = MagicMock()
        error.Fail.return_value = False
        sb_process = MagicMock()
        mock_sb_target.Launch.return_value = sb_process

        target = Target(mock_sb_target)
        with patch("morgul.bridge.target.lldb") as mock_lldb:
            mock_lldb.SBError.return_value = error
            mock_lldb.SBListener.return_value = MagicMock()
            process = target.launch(args=["-la"])
        assert process is not None
        mock_sb_target.Launch.assert_called_once()

    def test_launch_failure(self, mock_sb_target):
        error = MagicMock()
        error.Fail.return_value = True
        error.__str__ = lambda self: "launch failed"
        mock_sb_target.Launch.return_value = MagicMock()

        target = Target(mock_sb_target)
        with patch("morgul.bridge.target.lldb") as mock_lldb:
            mock_lldb.SBError.return_value = error
            mock_lldb.SBListener.return_value = MagicMock()
            with pytest.raises(RuntimeError, match="Failed to launch target"):
                target.launch()
