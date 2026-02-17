"""Tests for context builder."""

from __future__ import annotations

from morgul.core.context.builder import ContextBuilder
from morgul.core.types.context import (
    FrameInfo,
    ProcessSnapshot,
    RegisterInfo,
    StackTrace,
)


def test_context_builder_format():
    builder = ContextBuilder()
    snapshot = ProcessSnapshot(
        registers=[
            RegisterInfo(name="rax", value=0x42, size=8),
            RegisterInfo(name="rip", value=0x100000F00, size=8),
        ],
        stack_trace=StackTrace(
            frames=[
                FrameInfo(index=0, function_name="main", pc=0x100000F00),
                FrameInfo(index=1, function_name="_start", pc=0x100000E00),
            ],
            thread_id=1,
            thread_name="main",
        ),
        disassembly="0x100000f00: push rbp\n0x100000f01: mov rbp, rsp",
        process_state="stopped",
        stop_reason="breakpoint",
        pc=0x100000F00,
    )

    text = builder.format_for_prompt(snapshot)
    assert "stopped" in text
    assert "breakpoint" in text
    assert "rax" in text
    assert "main" in text
    assert "push rbp" in text


def test_context_builder_prune_noop():
    """Small snapshots should not be pruned."""
    builder = ContextBuilder(max_tokens=10000)
    snapshot = ProcessSnapshot(
        registers=[RegisterInfo(name="rax", value=0, size=8)],
        process_state="stopped",
    )
    pruned = builder._prune(snapshot)
    assert len(pruned.registers) == 1


def test_context_builder_prune_large():
    """Large snapshots should be pruned to fit within budget."""
    builder = ContextBuilder(max_tokens=100)
    snapshot = ProcessSnapshot(
        registers=[RegisterInfo(name=f"r{i}", value=i, size=8) for i in range(100)],
        memory_regions=[],
        modules=[],
        disassembly="x" * 2000,
        process_state="stopped",
    )
    pruned = builder._prune(snapshot)
    assert len(pruned.disassembly) < 2000
