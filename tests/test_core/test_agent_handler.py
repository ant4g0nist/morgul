"""Tests for AgentHandler — autonomous debugging loop."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from morgul.bridge.types import CommandResult
from morgul.core.agent.handler import AgentHandler
from morgul.core.agent.strategies import AgentStrategy
from morgul.core.types.context import ProcessSnapshot, RegisterInfo
from morgul.core.types.llm import AgentStep
from morgul.llm.types import LLMResponse, ToolCall, Usage


class TestAgentHandler:
    @pytest.fixture()
    def handler(self, mock_llm_client, mock_debugger, mock_bridge_process):
        return AgentHandler(
            llm_client=mock_llm_client,
            debugger=mock_debugger,
            process=mock_bridge_process,
            strategy=AgentStrategy.DEPTH_FIRST,
            max_steps=5,
            timeout=10.0,
        )

    def _patch_context(self, handler):
        return patch.object(
            handler.context_builder, "build",
            return_value=ProcessSnapshot(registers=[], process_state="stopped"),
        ), patch.object(
            handler.context_builder, "format_for_prompt",
            return_value="context",
        )

    async def test_run_with_done_tool(self, handler):
        """Agent calls 'done' tool to complete."""
        p1, p2 = self._patch_context(handler)
        with p1, p2:
            handler.llm.chat.return_value = LLMResponse(
                content="I'm done",
                tool_calls=[ToolCall(id="tc_1", name="done", arguments={"result": "Found bug"})],
                usage=Usage(input_tokens=100, output_tokens=50),
            )
            steps = await handler.run("find a bug")

        assert len(steps) == 1
        assert "done" in steps[0].action

    async def test_run_text_only_response(self, handler):
        """Agent responds with text (no tools) then done."""
        p1, p2 = self._patch_context(handler)
        with p1, p2:
            handler.llm.chat.side_effect = [
                LLMResponse(content="Let me think...", tool_calls=None),
                LLMResponse(
                    content="Done",
                    tool_calls=[ToolCall(id="tc_1", name="done", arguments={"result": "ok"})],
                ),
            ]
            steps = await handler.run("analyse")

        assert len(steps) == 2
        assert steps[0].action == "think"

    async def test_run_max_steps(self, handler):
        """Agent stops at max_steps."""
        p1, p2 = self._patch_context(handler)
        with p1, p2:
            handler.llm.chat.return_value = LLMResponse(
                content="thinking...", tool_calls=None
            )
            steps = await handler.run("loop forever")

        assert len(steps) == handler.max_steps

    async def test_run_timeout(self, handler):
        """Agent stops on timeout."""
        handler.timeout = 0.01  # Very short timeout

        p1, p2 = self._patch_context(handler)
        with p1, p2:
            async def slow_chat(*args, **kwargs):
                import asyncio
                await asyncio.sleep(0.1)
                return LLMResponse(content="slow", tool_calls=None)

            handler.llm.chat = slow_chat
            steps = await handler.run("slow task")

        # Should stop due to timeout
        assert len(steps) <= handler.max_steps

    async def test_execute_tool_act(self, handler):
        handler.debugger.execute_command.return_value = CommandResult(
            output="frame #0: main", error="", succeeded=True
        )
        result = await handler._execute_tool("act", {"instruction": "bt"})
        assert "main" in result

    async def test_execute_tool_act_failure(self, handler):
        handler.debugger.execute_command.return_value = CommandResult(
            output="", error="bad command", succeeded=False
        )
        result = await handler._execute_tool("act", {"instruction": "bad"})
        assert "Error" in result

    async def test_execute_tool_set_breakpoint_by_name(self, handler):
        mock_bp = MagicMock()
        mock_bp.id = 1
        handler.process._target.breakpoint_create_by_name.return_value = mock_bp

        result = await handler._execute_tool("set_breakpoint", {"location": "main"})
        assert "Breakpoint 1" in result

    async def test_execute_tool_set_breakpoint_by_address(self, handler):
        mock_bp = MagicMock()
        mock_bp.id = 2
        handler.process._target.breakpoint_create_by_address.return_value = mock_bp

        result = await handler._execute_tool("set_breakpoint", {"location": "0x100003f00"})
        assert "Breakpoint 2" in result

    async def test_execute_tool_read_memory(self, handler):
        handler.process.read_memory.return_value = b"\xDE\xAD\xBE\xEF"
        result = await handler._execute_tool("read_memory", {"address": "0x1000", "size": 4})
        assert "de ad be ef" in result

    async def test_execute_tool_step_over(self, handler):
        result = await handler._execute_tool("step", {"mode": "over"})
        assert "over" in result
        handler.process.selected_thread.step_over.assert_called_once()

    async def test_execute_tool_step_into(self, handler):
        result = await handler._execute_tool("step", {"mode": "into"})
        assert "into" in result

    async def test_execute_tool_continue(self, handler):
        result = await handler._execute_tool("continue_execution", {})
        assert "continued" in result.lower() or "Process" in result

    async def test_execute_tool_evaluate(self, handler):
        handler.process.selected_thread.selected_frame.evaluate_expression.return_value = "42"
        result = await handler._execute_tool("evaluate", {"expression": "argc"})
        assert "42" in result

    async def test_execute_tool_done(self, handler):
        result = await handler._execute_tool("done", {"result": "found the bug"})
        assert "found the bug" in result

    async def test_execute_tool_unknown(self, handler):
        result = await handler._execute_tool("nonexistent", {})
        assert "Unknown tool" in result

    async def test_execute_tool_exception(self, handler):
        handler.debugger.execute_command.side_effect = Exception("boom")
        result = await handler._execute_tool("act", {"instruction": "crash"})
        assert "Error" in result

    async def test_run_stream(self, handler):
        """Test streaming steps."""
        p1, p2 = self._patch_context(handler)
        with p1, p2:
            handler.llm.chat.return_value = LLMResponse(
                content="done",
                tool_calls=[ToolCall(id="tc_1", name="done", arguments={"result": "ok"})],
            )
            steps = []
            async for step in handler.run_stream("task"):
                steps.append(step)

        assert len(steps) == 1
        assert isinstance(steps[0], AgentStep)

    async def test_run_multiple_tool_calls(self, handler):
        """When LLM returns multiple tool_calls, all must be executed and
        the message history must have one assistant msg + one tool msg per call."""
        handler.debugger.execute_command.return_value = CommandResult(
            output="ok", error="", succeeded=True
        )
        handler.process.selected_thread.step_over.return_value = None

        p1, p2 = self._patch_context(handler)
        with p1, p2:
            handler.llm.chat.side_effect = [
                # First response: LLM requests 3 tools at once
                LLMResponse(
                    content="I'll run multiple commands",
                    tool_calls=[
                        ToolCall(id="tc_a", name="act", arguments={"instruction": "bt"}),
                        ToolCall(id="tc_b", name="step", arguments={"mode": "over"}),
                        ToolCall(id="tc_c", name="act", arguments={"instruction": "register read"}),
                    ],
                ),
                # Second response: done
                LLMResponse(
                    content="All done",
                    tool_calls=[ToolCall(id="tc_d", name="done", arguments={"result": "finished"})],
                ),
            ]
            steps = await handler.run("multi tool task")

        # 3 tool steps from first response + 1 done step
        assert len(steps) == 4
        assert steps[0].action.startswith("act(")
        assert steps[1].action.startswith("step(")
        assert steps[2].action.startswith("act(")
        assert steps[3].action.startswith("done(")

        # Verify message history: the second chat call should have received
        # proper tool result messages for all 3 tool_call_ids
        second_call_messages = handler.llm.chat.call_args_list[1][1]["messages"]
        tool_msgs = [m for m in second_call_messages if m.role == "tool"]
        assert len(tool_msgs) == 3
        tool_ids = {m.tool_call_id for m in tool_msgs}
        assert tool_ids == {"tc_a", "tc_b", "tc_c"}
