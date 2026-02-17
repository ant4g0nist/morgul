"""Tests for morgul-bridge types."""

from __future__ import annotations

from morgul.bridge.types import (
    CommandResult,
    MemoryRegion,
    ModuleInfo,
    ProcessState,
    RegisterValue,
    StopReason,
    Variable,
)


def test_process_state_enum():
    assert ProcessState.STOPPED.value is not None
    assert ProcessState.RUNNING.value is not None
    assert ProcessState.EXITED.value is not None


def test_stop_reason_enum():
    assert StopReason.BREAKPOINT.value is not None
    assert StopReason.TRACE.value is not None
    assert StopReason.NONE.value is not None


def test_register_value():
    reg = RegisterValue(name="rax", value=0xDEADBEEF, size=8)
    assert reg.name == "rax"
    assert reg.value == 0xDEADBEEF
    assert reg.size == 8


def test_variable():
    var = Variable(name="argc", type_name="int", value="1", address=0x7FFF0000, size=4)
    assert var.name == "argc"
    assert var.address == 0x7FFF0000


def test_memory_region():
    region = MemoryRegion(
        start=0x100000000,
        end=0x100001000,
        readable=True,
        writable=False,
        executable=True,
        name="__TEXT",
    )
    assert region.executable
    assert not region.writable


def test_module_info():
    mod = ModuleInfo(name="a.out", path="/tmp/a.out", uuid="ABC-123", base_address=0x100000000)
    assert mod.name == "a.out"


def test_command_result():
    result = CommandResult(output="frame #0: main", error="", succeeded=True)
    assert result.succeeded
    assert "main" in result.output
