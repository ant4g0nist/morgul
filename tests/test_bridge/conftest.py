"""Bridge test fixtures — mock SB objects for each LLDB class."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pytest

from morgul.bridge.types import ProcessState, StopReason


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sb_error(success: bool = True) -> MagicMock:
    err = MagicMock()
    err.Success.return_value = success
    err.Fail.return_value = not success
    err.__str__ = lambda self: "" if success else "mock error"
    err.__bool__ = lambda self: True  # SBError is truthy
    return err


# ---------------------------------------------------------------------------
# SBDebugger
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_sb_debugger():
    sb = MagicMock(name="SBDebugger")
    sb.GetAsync.return_value = False
    sb.GetCommandInterpreter.return_value = MagicMock()

    ret_obj = MagicMock()
    ret_obj.GetOutput.return_value = "ok"
    ret_obj.GetError.return_value = ""
    ret_obj.Succeeded.return_value = True
    sb.GetCommandInterpreter().HandleCommand.return_value = None
    # We'll have to patch SBCommandReturnObject separately in tests

    return sb


# ---------------------------------------------------------------------------
# SBTarget
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_sb_target():
    sb = MagicMock(name="SBTarget")

    # Executable
    exe = MagicMock()
    exe.IsValid.return_value = True
    exe.__str__ = lambda self: "/tmp/a.out"
    sb.GetExecutable.return_value = exe

    sb.GetTriple.return_value = "arm64-apple-macosx15.0.0"
    sb.GetByteOrder.return_value = 1  # little endian
    sb.GetAddressByteSize.return_value = 8
    sb.GetNumModules.return_value = 0
    sb.GetNumBreakpoints.return_value = 0

    # FindFunctions returns an empty list by default
    sc_list = MagicMock()
    sc_list.GetSize.return_value = 0
    sb.FindFunctions.return_value = sc_list
    sb.FindSymbols.return_value = sc_list

    return sb


# ---------------------------------------------------------------------------
# SBProcess
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_sb_process(mock_sb_target):
    sb = MagicMock(name="SBProcess")
    sb.GetState.return_value = 5  # eStateStopped
    sb.GetProcessID.return_value = 12345
    sb.GetExitStatus.return_value = 0
    sb.GetExitDescription.return_value = ""
    sb.GetNumThreads.return_value = 1
    sb.GetTarget.return_value = mock_sb_target

    sb.Continue.return_value = _sb_error(True)
    sb.Stop.return_value = _sb_error(True)
    sb.Kill.return_value = _sb_error(True)
    sb.Detach.return_value = _sb_error(True)

    # Memory ops
    sb.ReadMemory.return_value = b"\x41\x42\x43\x44"
    sb.WriteMemory.return_value = 4

    # Memory regions
    region_list = MagicMock()
    region_list.GetSize.return_value = 0
    sb.GetMemoryRegions.return_value = region_list

    return sb


# ---------------------------------------------------------------------------
# SBThread
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_sb_thread():
    sb = MagicMock(name="SBThread")
    sb.GetThreadID.return_value = 1
    sb.GetName.return_value = "main"
    sb.GetStopReason.return_value = 3  # eStopReasonBreakpoint
    sb.GetNumFrames.return_value = 2
    return sb


# ---------------------------------------------------------------------------
# SBFrame
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_sb_frame():
    sb = MagicMock(name="SBFrame")
    sb.GetPC.return_value = 0x100003F00
    sb.GetSP.return_value = 0x7FF7BFEFF680
    sb.GetFP.return_value = 0x7FF7BFEFF690
    sb.GetFrameID.return_value = 0
    sb.GetFunctionName.return_value = "main"

    # Module
    mod = MagicMock()
    mod.IsValid.return_value = True
    fs = MagicMock()
    fs.IsValid.return_value = True
    fs.GetFilename.return_value = "a.out"
    mod.GetFileSpec.return_value = fs
    sb.GetModule.return_value = mod

    # Line entry
    le = MagicMock()
    le.IsValid.return_value = True
    le.GetLine.return_value = 10
    le.GetColumn.return_value = 0
    le_fs = MagicMock()
    le_fs.IsValid.return_value = True
    le_fs.__str__ = lambda self: "/tmp/main.c"
    le.GetFileSpec.return_value = le_fs
    sb.GetLineEntry.return_value = le

    # Registers — one set with one register
    reg = MagicMock()
    reg.GetName.return_value = "rax"
    reg.GetValueAsUnsigned.return_value = 0x42
    reg.GetByteSize.return_value = 8

    reg_set = MagicMock()
    reg_set.GetNumChildren.return_value = 1
    reg_set.GetChildAtIndex.return_value = reg

    reg_sets = MagicMock()
    reg_sets.GetSize.return_value = 1
    reg_sets.GetValueAtIndex.return_value = reg_set
    sb.GetRegisters.return_value = reg_sets

    # Variables
    var = MagicMock()
    var.GetName.return_value = "argc"
    var.GetTypeName.return_value = "int"
    var.GetValue.return_value = "1"
    var.GetSummary.return_value = None
    var.GetLoadAddress.return_value = 0x7FF7BFEFF6A0
    var.GetByteSize.return_value = 4
    # Type info for _to_variable() recursive expansion
    var_type = MagicMock()
    var_type.GetTypeClass.return_value = 1  # eTypeClassBuiltin (not a pointer)
    var.GetType.return_value = var_type
    var.GetNumChildren.return_value = 0
    var.IsValid.return_value = True

    vars_list = MagicMock()
    vars_list.GetSize.return_value = 1
    vars_list.GetValueAtIndex.return_value = var
    sb.GetVariables.return_value = vars_list

    # Expression evaluation
    expr_val = MagicMock()
    expr_error = MagicMock()
    expr_error.Fail.return_value = False
    expr_val.GetError.return_value = expr_error
    expr_val.GetValue.return_value = "42"
    expr_val.GetSummary.return_value = None
    sb.EvaluateExpression.return_value = expr_val

    return sb


# ---------------------------------------------------------------------------
# SBBreakpoint
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_sb_breakpoint():
    sb = MagicMock(name="SBBreakpoint")
    sb.GetID.return_value = 1
    sb.IsEnabled.return_value = True
    sb.IsValid.return_value = True
    sb.GetHitCount.return_value = 0
    sb.GetNumLocations.return_value = 1
    sb.GetCondition.return_value = None

    target = MagicMock()
    target.IsValid.return_value = True
    sb.GetTarget.return_value = target

    return sb


# ---------------------------------------------------------------------------
# Convenience: error fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_sb_error_success():
    return _sb_error(True)


@pytest.fixture()
def mock_sb_error_fail():
    return _sb_error(False)
