"""Tool definitions for agent mode."""

from __future__ import annotations

from morgul.llm.types import ToolDefinition

AGENT_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="act",
        description="Execute a natural language debugging action. Translates the instruction into LLDB commands and runs them.",
        parameters={
            "type": "object",
            "properties": {
                "instruction": {
                    "type": "string",
                    "description": "Natural language instruction describing what to do (e.g., 'set a breakpoint on main')",
                },
            },
            "required": ["instruction"],
        },
    ),
    ToolDefinition(
        name="set_breakpoint",
        description="Set a breakpoint at a function name or memory address.",
        parameters={
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Function name or hex address (e.g., 'main' or '0x100003f00')",
                },
            },
            "required": ["location"],
        },
    ),
    ToolDefinition(
        name="read_memory",
        description="Read memory at a given address.",
        parameters={
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Hex address to read from (e.g., '0x7fff5fbff8c0')",
                },
                "size": {
                    "type": "integer",
                    "description": "Number of bytes to read",
                    "default": 64,
                },
            },
            "required": ["address"],
        },
    ),
    ToolDefinition(
        name="step",
        description="Step execution by one instruction or line.",
        parameters={
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["over", "into", "out", "instruction"],
                    "description": "Step mode: over (step over), into (step into), out (step out), instruction (single instruction)",
                    "default": "over",
                },
            },
        },
    ),
    ToolDefinition(
        name="continue_execution",
        description="Continue process execution until the next breakpoint or stop.",
        parameters={
            "type": "object",
            "properties": {},
        },
    ),
    ToolDefinition(
        name="evaluate",
        description="Evaluate an expression in the current frame context.",
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Expression to evaluate (e.g., '*(int*)0x7fff5fbff8c0' or 'argc')",
                },
            },
            "required": ["expression"],
        },
    ),
    ToolDefinition(
        name="done",
        description="Signal that the task is complete and provide the final result.",
        parameters={
            "type": "object",
            "properties": {
                "result": {
                    "type": "string",
                    "description": "Summary of findings and conclusions",
                },
            },
            "required": ["result"],
        },
    ),
]
