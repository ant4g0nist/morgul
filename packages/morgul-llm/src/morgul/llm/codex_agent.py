"""Codex CLI backend — subprocess-based agentic client for OpenAI Codex."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from typing import Any, AsyncIterator, Dict, List, Optional

from .agentic import AgenticClient, AgenticEvent, AgenticResult, ToolExecutor
from .types import ToolDefinition

logger = logging.getLogger(__name__)

# System context prepended to the task prompt for Codex.
_LLDB_SYSTEM_CONTEXT = (
    "You are an autonomous LLDB debugger agent. You have access to tools that "
    "execute LLDB debugging commands against a live process. Use these tools to "
    "investigate, debug, and analyze the target process. When you are done, call "
    "the 'done' tool with your findings."
)


class CodexClient:
    """Agentic backend that spawns the ``codex`` CLI as a subprocess.

    Communication happens via JSONL over stdin/stdout.
    Tool calls from Codex are routed through the ``tool_executor`` callback.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        cli_path: Optional[str] = None,
    ):
        self.model = model
        self.cli_path = cli_path or shutil.which("codex") or "codex"

    def _build_prompt(self, task: str, tools: List[ToolDefinition]) -> str:
        """Build the full prompt including tool descriptions."""
        tool_descriptions = []
        for tool in tools:
            params = tool.parameters.get("properties", {})
            param_desc = ", ".join(
                f"{k}: {v.get('description', v.get('type', 'any'))}"
                for k, v in params.items()
            )
            tool_descriptions.append(f"- {tool.name}({param_desc}): {tool.description}")

        tools_text = "\n".join(tool_descriptions)
        return (
            f"{_LLDB_SYSTEM_CONTEXT}\n\n"
            f"Available debugging tools:\n{tools_text}\n\n"
            f"Task: {task}"
        )

    def _build_command(self, prompt: str, max_iterations: int) -> List[str]:
        """Build the codex CLI command."""
        cmd = [self.cli_path, "--json"]
        if self.model:
            cmd.extend(["--model", self.model])
        cmd.extend(["--max-turns", str(max_iterations)])
        cmd.append(prompt)
        return cmd

    async def run_agent(
        self,
        task: str,
        tools: List[ToolDefinition],
        tool_executor: ToolExecutor,
        max_iterations: int = 50,
    ) -> AgenticResult:
        """Run Codex CLI agent, routing tool calls through tool_executor."""
        prompt = self._build_prompt(task, tools)
        cmd = self._build_command(prompt, max_iterations)

        tool_calls_log: List[Dict[str, Any]] = []
        result_text = ""
        steps = 0

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"Codex CLI not found at '{self.cli_path}'. "
                "Install it with: npm install -g @openai/codex"
            )

        try:
            result_text, tool_calls_log, steps = await self._process_events(
                proc, tool_executor
            )
        finally:
            if proc.returncode is None:
                proc.terminate()
                await proc.wait()

        return AgenticResult(
            result=result_text or "Agent completed without explicit result.",
            steps=steps,
            tool_calls=tool_calls_log,
        )

    async def run_agent_stream(
        self,
        task: str,
        tools: List[ToolDefinition],
        tool_executor: ToolExecutor,
        max_iterations: int = 50,
    ) -> AsyncIterator[AgenticEvent]:
        """Stream events from Codex CLI agent."""
        prompt = self._build_prompt(task, tools)
        cmd = self._build_command(prompt, max_iterations)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"Codex CLI not found at '{self.cli_path}'. "
                "Install it with: npm install -g @openai/codex"
            )

        try:
            async for event in self._stream_events(proc, tool_executor):
                yield event
        finally:
            if proc.returncode is None:
                proc.terminate()
                await proc.wait()

    async def _process_events(
        self,
        proc: asyncio.subprocess.Process,
        tool_executor: ToolExecutor,
    ) -> tuple[str, List[Dict[str, Any]], int]:
        """Read JSONL events from Codex, handle tool calls, return final state."""
        tool_calls_log: List[Dict[str, Any]] = []
        result_text = ""
        steps = 0

        assert proc.stdout is not None
        assert proc.stdin is not None

        while True:
            line = await proc.stdout.readline()
            if not line:
                break

            line_str = line.decode("utf-8").strip()
            if not line_str:
                continue

            try:
                event = json.loads(line_str)
            except json.JSONDecodeError:
                logger.warning("Non-JSON line from codex: %s", line_str)
                continue

            event_type = event.get("type", "")

            if event_type == "tool_call":
                tool_name = event.get("name", "")
                tool_args = event.get("arguments", {})

                logger.debug("Codex tool call: %s(%s)", tool_name, tool_args)

                tool_result = await tool_executor(tool_name, tool_args)

                tool_calls_log.append(
                    {"name": tool_name, "arguments": tool_args, "result": tool_result}
                )

                # Send tool result back to Codex
                response = json.dumps(
                    {"type": "tool_result", "name": tool_name, "result": tool_result}
                )
                proc.stdin.write(response.encode("utf-8") + b"\n")
                await proc.stdin.drain()

                steps += 1

            elif event_type in ("text", "message"):
                text = event.get("text", event.get("content", ""))
                result_text = text  # Keep updating with latest text
                steps += 1

            elif event_type == "done":
                result_text = event.get("result", event.get("text", result_text))
                break

        return result_text, tool_calls_log, steps

    async def _stream_events(
        self,
        proc: asyncio.subprocess.Process,
        tool_executor: ToolExecutor,
    ) -> AsyncIterator[AgenticEvent]:
        """Stream JSONL events from Codex, handling tool calls inline."""
        assert proc.stdout is not None
        assert proc.stdin is not None

        while True:
            line = await proc.stdout.readline()
            if not line:
                break

            line_str = line.decode("utf-8").strip()
            if not line_str:
                continue

            try:
                event = json.loads(line_str)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type", "")

            if event_type == "tool_call":
                tool_name = event.get("name", "")
                tool_args = event.get("arguments", {})

                yield AgenticEvent(
                    type="tool_call",
                    data={"name": tool_name, "arguments": tool_args},
                )

                tool_result = await tool_executor(tool_name, tool_args)

                yield AgenticEvent(
                    type="tool_result",
                    data={"name": tool_name, "result": tool_result},
                )

                response = json.dumps(
                    {"type": "tool_result", "name": tool_name, "result": tool_result}
                )
                proc.stdin.write(response.encode("utf-8") + b"\n")
                await proc.stdin.drain()

            elif event_type in ("text", "message"):
                text = event.get("text", event.get("content", ""))
                yield AgenticEvent(type="text", data=text)

            elif event_type == "done":
                result_text = event.get("result", event.get("text", ""))
                yield AgenticEvent(type="done", data=result_text)
                break
