"""Agentic client protocol — SDK-managed tool loops for agent() primitive."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional, Protocol, runtime_checkable

from .types import ToolDefinition

# Callback type: given (tool_name, arguments) returns the string result.
ToolExecutor = Callable[[str, Dict[str, Any]], Awaitable[str]]


@dataclass
class AgenticResult:
    """Final result from an agentic run."""

    result: str
    steps: int = 0
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    raw_output: Any = None


@dataclass
class AgenticEvent:
    """Streaming event from an agentic run."""

    type: str  # "text", "tool_call", "tool_result", "done"
    data: Any = None


@runtime_checkable
class AgenticClient(Protocol):
    """Protocol for SDK-managed agentic backends (Claude Code, Codex, etc.)."""

    async def run_agent(
        self,
        task: str,
        tools: List[ToolDefinition],
        tool_executor: ToolExecutor,
        max_iterations: int = 50,
    ) -> AgenticResult:
        """Run an autonomous agent loop, returning the final result."""
        ...

    async def run_agent_stream(
        self,
        task: str,
        tools: List[ToolDefinition],
        tool_executor: ToolExecutor,
        max_iterations: int = 50,
    ) -> AsyncIterator[AgenticEvent]:
        """Run an autonomous agent loop, yielding events as they occur."""
        ...


def create_agentic_client(
    provider: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    cli_path: Optional[str] = None,
) -> AgenticClient:
    """Factory that returns the appropriate agentic client for *provider*.

    Returns None-safe — callers should check ``agentic_provider`` before calling.
    Provider SDKs are imported lazily so users only need the SDK they use.
    """
    if provider == "claude-code":
        from .claude_agent import ClaudeAgentClient

        return ClaudeAgentClient(model=model, api_key=api_key)

    if provider == "codex":
        from .codex_agent import CodexClient

        return CodexClient(model=model, cli_path=cli_path)

    raise ValueError(f"Unsupported agentic provider: {provider!r}")
