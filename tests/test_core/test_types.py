"""Tests for morgul-core type models."""

from __future__ import annotations

from morgul.core.types.actions import Action, ActResult, ExtractResult, ObserveResult
from morgul.core.types.config import MorgulConfig, load_config
from morgul.core.types.context import (
    FrameInfo,
    MemoryRegionInfo,
    ModuleDetail,
    ProcessSnapshot,
    RegisterInfo,
    StackTrace,
)
from morgul.core.types.llm import (
    AgentStep,
    ExtractRequest,
    ObserveRequest,
    TranslateRequest,
    TranslateResponse,
)


def test_action_creation():
    action = Action(command="breakpoint set -n main", description="Set breakpoint on main")
    assert action.command == "breakpoint set -n main"
    assert action.args == {}


def test_act_result():
    action = Action(command="bt", description="backtrace")
    result = ActResult(success=True, message="OK", actions=[action], output="frame #0")
    assert result.success
    assert len(result.actions) == 1


def test_observe_result():
    actions = [
        Action(command="bt", description="Show backtrace"),
        Action(command="register read", description="Show registers"),
    ]
    result = ObserveResult(actions=actions, description="Process stopped at breakpoint")
    assert len(result.actions) == 2
    assert result.description == "Process stopped at breakpoint"


def test_extract_result():
    result = ExtractResult[dict](data={"key": "value"}, raw_response='{"key": "value"}')
    assert result.data["key"] == "value"


def test_process_snapshot():
    snapshot = ProcessSnapshot(
        registers=[RegisterInfo(name="rax", value=0x1234, size=8)],
        stack_trace=StackTrace(
            frames=[FrameInfo(index=0, function_name="main", pc=0x100000F00)],
            thread_id=1,
        ),
        modules=[ModuleDetail(name="a.out", path="/tmp/a.out", base_address=0x100000000)],
        disassembly="0x100000f00: push rbp",
        process_state="stopped",
        stop_reason="breakpoint",
        pc=0x100000F00,
    )
    assert snapshot.registers[0].name == "rax"
    assert snapshot.stack_trace.frames[0].function_name == "main"
    assert snapshot.pc == 0x100000F00


def test_config_defaults():
    config = MorgulConfig()
    assert config.llm.provider == "anthropic"
    assert config.cache.enabled is True
    assert config.healing.max_retries == 3
    assert config.agent.max_steps == 50
    assert config.self_heal is True


def test_load_config_no_file():
    config = load_config("/nonexistent/morgul.toml")
    assert config.llm.provider == "anthropic"


def test_translate_response():
    resp = TranslateResponse(
        actions=[Action(command="bt", description="backtrace")],
        reasoning="User asked for backtrace",
    )
    assert len(resp.actions) == 1
    assert resp.reasoning == "User asked for backtrace"


def test_agent_step():
    step = AgentStep(
        step_number=1,
        action="set_breakpoint(main)",
        observation="Breakpoint 1 set at main",
        reasoning="Need to stop at entry point",
    )
    assert step.step_number == 1


def test_translate_request():
    snapshot = ProcessSnapshot(
        registers=[RegisterInfo(name="rax", value=0, size=8)],
        process_state="stopped",
    )
    req = TranslateRequest(instruction="set breakpoint on main", context=snapshot)
    assert req.instruction == "set breakpoint on main"
    assert req.history == []


def test_extract_request():
    snapshot = ProcessSnapshot(
        registers=[],
        process_state="stopped",
    )
    req = ExtractRequest(
        instruction="get vtable",
        context=snapshot,
        output_schema={"type": "object", "properties": {"name": {"type": "string"}}},
    )
    assert req.instruction == "get vtable"
    assert "properties" in req.output_schema


def test_observe_request():
    snapshot = ProcessSnapshot(registers=[], process_state="stopped")
    req = ObserveRequest(context=snapshot)
    assert req.instruction is None

    req2 = ObserveRequest(instruction="check heap", context=snapshot)
    assert req2.instruction == "check heap"
