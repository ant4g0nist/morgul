"""Claude Agent SDK backend — delegates the full tool loop to claude-agent-sdk.

Uses in-process SDK MCP tools so LLDB commands route through Morgul's bridge
without subprocess overhead.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from .agentic import AgenticClient, AgenticEvent, AgenticResult, ToolExecutor
from .types import ToolDefinition

logger = logging.getLogger(__name__)

# System prompt context injected into Claude Agent sessions.
_LLDB_SYSTEM_CONTEXT = (
    "You are an autonomous LLDB debugger agent. You have access to tools that "
    "execute LLDB debugging commands against a live process. Use these tools to "
    "investigate, debug, and analyze the target process. When you are done, call "
    "the 'done' tool with your findings."
)

_MCP_SERVER_NAME = "morgul-lldb"


def _build_mcp_tools(
    tools: List[ToolDefinition],
    tool_executor: ToolExecutor,
    results_log: List[Dict[str, Any]],
) -> list:
    """Convert Morgul ToolDefinitions into @tool-decorated functions for the SDK MCP server.

    *results_log* is a shared list that each handler appends to so callers can
    capture tool results even when the SDK doesn't surface ToolResultBlocks.
    """
    try:
        from claude_agent_sdk import tool as sdk_tool
    except ImportError:
        raise ImportError(
            "claude-agent-sdk is required for the 'claude-code' agentic provider. "
            "Install it with: pip install claude-agent-sdk"
        )

    mcp_tools = []
    for tdef in tools:
        # Build the parameter type hints dict from JSON Schema properties.
        props = tdef.parameters.get("properties", {})
        param_types: Dict[str, type] = {}
        for pname, pschema in props.items():
            json_type = pschema.get("type", "string")
            param_types[pname] = {
                "string": str,
                "integer": int,
                "number": float,
                "boolean": bool,
            }.get(json_type, str)

        # Capture tdef.name in closure.
        _tool_name = tdef.name

        @sdk_tool(_tool_name, tdef.description, param_types)
        async def _handler(args: dict, __name=_tool_name) -> dict:
            result = await tool_executor(__name, args)
            results_log.append({"name": __name, "arguments": dict(args), "result": result})
            return {"content": [{"type": "text", "text": result}]}

        mcp_tools.append(_handler)

    return mcp_tools


class ClaudeAgentClient:
    """Agentic backend powered by the ``claude-agent-sdk`` Python package.

    The SDK manages the full reasoning + tool-call loop internally.
    LLDB tools are registered as in-process MCP tools so tool calls route
    directly through Morgul's bridge without subprocess overhead.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.model = model
        self.api_key = api_key

    async def run_agent(
        self,
        task: str,
        tools: List[ToolDefinition],
        tool_executor: ToolExecutor,
        max_iterations: int = 50,
    ) -> AgenticResult:
        """Run Claude Agent SDK, routing tool calls through tool_executor."""
        try:
            from claude_agent_sdk import (
                AssistantMessage,
                ClaudeAgentOptions,
                ClaudeSDKClient,
                TextBlock,
                ToolResultBlock,
                ToolUseBlock,
                create_sdk_mcp_server,
            )
        except ImportError:
            raise ImportError(
                "claude-agent-sdk is required for the 'claude-code' agentic provider. "
                "Install it with: pip install claude-agent-sdk"
            )

        # Shared log populated by MCP tool handlers so we always have results.
        tool_calls_log: List[Dict[str, Any]] = []

        mcp_tools = _build_mcp_tools(tools, tool_executor, tool_calls_log)
        server = create_sdk_mcp_server(
            name=_MCP_SERVER_NAME,
            version="1.0.0",
            tools=mcp_tools,
        )

        # Build allowed_tools list: mcp__<server>__<tool_name>
        allowed_tools = [f"mcp__{_MCP_SERVER_NAME}__{t.name}" for t in tools]

        options = ClaudeAgentOptions(
            system_prompt=_LLDB_SYSTEM_CONTEXT,
            max_turns=max_iterations,
            mcp_servers={_MCP_SERVER_NAME: server},
            allowed_tools=allowed_tools,
        )
        if self.model:
            options.model = self.model

        result_text = ""

        async with ClaudeSDKClient(options=options) as client:
            await client.query(task)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            result_text = block.text

        return AgenticResult(
            result=result_text or "Agent completed without explicit result.",
            steps=len(tool_calls_log),
            tool_calls=tool_calls_log,
        )

    async def run_agent_stream(
        self,
        task: str,
        tools: List[ToolDefinition],
        tool_executor: ToolExecutor,
        max_iterations: int = 50,
    ) -> AsyncIterator[AgenticEvent]:
        """Stream events from Claude Agent SDK."""
        try:
            from claude_agent_sdk import (
                AssistantMessage,
                ClaudeAgentOptions,
                ClaudeSDKClient,
                TextBlock,
                ToolResultBlock,
                ToolUseBlock,
                create_sdk_mcp_server,
            )
        except ImportError:
            raise ImportError(
                "claude-agent-sdk is required for the 'claude-code' agentic provider. "
                "Install it with: pip install claude-agent-sdk"
            )

        tool_calls_log: List[Dict[str, Any]] = []

        mcp_tools = _build_mcp_tools(tools, tool_executor, tool_calls_log)
        server = create_sdk_mcp_server(
            name=_MCP_SERVER_NAME,
            version="1.0.0",
            tools=mcp_tools,
        )

        allowed_tools = [f"mcp__{_MCP_SERVER_NAME}__{t.name}" for t in tools]

        options = ClaudeAgentOptions(
            system_prompt=_LLDB_SYSTEM_CONTEXT,
            max_turns=max_iterations,
            mcp_servers={_MCP_SERVER_NAME: server},
            allowed_tools=allowed_tools,
        )
        if self.model:
            options.model = self.model

        result_text = ""
        last_log_idx = 0

        async with ClaudeSDKClient(options=options) as client:
            await client.query(task)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            result_text = block.text
                            yield AgenticEvent(type="text", data=block.text)
                        elif isinstance(block, ToolUseBlock):
                            yield AgenticEvent(
                                type="tool_call",
                                data={"name": block.name, "arguments": block.input},
                            )

                    # Yield any new tool results captured by handlers since last check.
                    while last_log_idx < len(tool_calls_log):
                        entry = tool_calls_log[last_log_idx]
                        yield AgenticEvent(
                            type="tool_result",
                            data={"name": entry["name"], "result": entry["result"]},
                        )
                        last_log_idx += 1

        yield AgenticEvent(type="done", data=result_text)


def _extract_block_text(block: Any) -> str:
    """Extract text from a ToolResultBlock or similar."""
    if hasattr(block, "content"):
        content = block.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
    return str(block)
