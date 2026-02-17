"""Root conftest — shared fixtures for the entire test suite."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from morgul.bridge.types import CommandResult, ProcessState, RegisterValue, StopReason, Variable
from morgul.core.types.actions import Action
from morgul.core.types.context import (
    FrameInfo,
    ModuleDetail,
    ProcessSnapshot,
    RegisterInfo,
    StackTrace,
)
from morgul.core.types.llm import TranslateResponse
from morgul.llm.types import ChatMessage, LLMResponse, ToolCall, Usage


# ---------------------------------------------------------------------------
# Mock LLM client
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_llm_client():
    """AsyncMock implementing the LLMClient protocol."""
    client = AsyncMock()

    # Default: chat() returns a simple LLMResponse
    client.chat.return_value = LLMResponse(
        content="Here is my response",
        tool_calls=None,
        usage=Usage(input_tokens=100, output_tokens=50),
    )

    # Default: chat_structured() returns a TranslateResponse
    client.chat_structured.return_value = TranslateResponse(
        actions=[Action(command="bt", description="backtrace")],
        reasoning="Analysed the context",
    )

    return client


# ---------------------------------------------------------------------------
# Sample process snapshot
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_snapshot():
    """A realistic ProcessSnapshot for use in tests."""
    return ProcessSnapshot(
        registers=[
            RegisterInfo(name="rax", value=0x0000000000000001, size=8),
            RegisterInfo(name="rbx", value=0x00007FF7BFEFF6A0, size=8),
            RegisterInfo(name="rcx", value=0x00007FF7BFEFF798, size=8),
            RegisterInfo(name="rdx", value=0x00007FF7BFEFF7A8, size=8),
            RegisterInfo(name="rsp", value=0x00007FF7BFEFF680, size=8),
            RegisterInfo(name="rbp", value=0x00007FF7BFEFF690, size=8),
            RegisterInfo(name="rip", value=0x0000000100003F00, size=8),
        ],
        stack_trace=StackTrace(
            frames=[
                FrameInfo(index=0, function_name="main", module_name="a.out", pc=0x100003F00),
                FrameInfo(index=1, function_name="_start", module_name="dyld", pc=0x7FF80A1E52A0),
            ],
            thread_id=1,
            thread_name="main",
        ),
        modules=[
            ModuleDetail(name="a.out", path="/tmp/a.out", uuid="ABC-123", base_address=0x100000000),
            ModuleDetail(
                name="libSystem.B.dylib",
                path="/usr/lib/libSystem.B.dylib",
                uuid="DEF-456",
                base_address=0x7FF80A000000,
            ),
        ],
        disassembly=(
            "  0x100003f00: push rbp\n"
            "  0x100003f01: mov rbp, rsp\n"
            "  0x100003f04: sub rsp, 0x20\n"
        ),
        variables=[
            {"name": "argc", "type": "int", "value": "1"},
            {"name": "argv", "type": "char **", "value": "0x7ff7bfeff7a8"},
        ],
        process_state="stopped",
        stop_reason="breakpoint 1.1",
        pc=0x100003F00,
    )


# ---------------------------------------------------------------------------
# Mock bridge objects
# ---------------------------------------------------------------------------

def _make_mock_frame():
    """Create a mock Frame with realistic data."""
    frame = MagicMock()
    frame.pc = 0x100003F00
    frame.sp = 0x7FF7BFEFF680
    frame.fp = 0x7FF7BFEFF690
    frame.index = 0
    frame.function_name = "main"
    frame.module_name = "a.out"
    frame.line_entry = {"file": "/tmp/main.c", "line": 10, "col": 0}
    frame.registers = [
        RegisterValue(name="rax", value=0x1, size=8),
        RegisterValue(name="rip", value=0x100003F00, size=8),
    ]
    frame.variables.return_value = [
        Variable(name="argc", type_name="int", value="1", address=0x7FF7BFEFF6A0, size=4),
    ]
    frame.arguments = [
        Variable(name="argc", type_name="int", value="1", address=0x7FF7BFEFF6A0, size=4),
    ]
    frame.disassemble.return_value = "  0x100003f00: push rbp\n  0x100003f01: mov rbp, rsp"
    frame.evaluate_expression.return_value = "42"
    return frame


def _make_mock_thread(frame=None):
    """Create a mock Thread."""
    thread = MagicMock()
    thread.id = 1
    thread.name = "main"
    thread.stop_reason = StopReason.BREAKPOINT
    thread.num_frames = 2
    thread.selected_frame = frame or _make_mock_frame()
    thread.get_frames.return_value = [thread.selected_frame]
    return thread


@pytest.fixture()
def mock_bridge_process():
    """Mock Process with realistic defaults."""
    frame = _make_mock_frame()
    thread = _make_mock_thread(frame)

    process = MagicMock()
    process.state = ProcessState.STOPPED
    process.pid = 12345
    process.exit_status = 0
    process.exit_description = ""
    process.selected_thread = thread
    process.threads = [thread]
    process.num_threads = 1
    process.read_memory.return_value = b"\xde\xad\xbe\xef" * 16
    process.write_memory.return_value = 4
    process._target = MagicMock()
    process._target.modules = []
    return process


@pytest.fixture()
def mock_bridge_target():
    """Mock Target with realistic defaults."""
    target = MagicMock()
    target.path = "/tmp/a.out"
    target.triple = "arm64-apple-macosx"
    target.byte_order = "little"
    target.modules = []
    target.breakpoints = []

    # breakpoint_create_by_name returns a mock breakpoint
    mock_bp = MagicMock()
    mock_bp.id = 1
    mock_bp.enabled = True
    mock_bp.num_locations = 1
    mock_bp.hit_count = 0
    target.breakpoint_create_by_name.return_value = mock_bp
    target.breakpoint_create_by_address.return_value = mock_bp
    target.breakpoint_create_by_regex.return_value = mock_bp

    target.find_functions.return_value = [
        {"name": "main", "address": 0x100003F00, "module": "a.out"},
    ]
    target.find_symbols.return_value = [
        {"name": "main", "address": 0x100003F00, "module": "a.out"},
    ]
    return target


@pytest.fixture()
def mock_debugger():
    """Mock Debugger with execute_command support."""
    debugger = MagicMock()
    debugger.execute_command.return_value = CommandResult(
        output="frame #0: 0x100003f00 a.out`main",
        error="",
        succeeded=True,
    )
    debugger.create_target.return_value = MagicMock()
    return debugger
