"""Tests for ObserveHandler — survey state and suggest actions."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from morgul.core.primitives.observe import ObserveHandler
from morgul.core.types.actions import Action, ObserveResult
from morgul.core.types.context import ProcessSnapshot, RegisterInfo


class TestObserveHandler:
    @pytest.fixture()
    def handler(self, mock_llm_client):
        return ObserveHandler(mock_llm_client)

    async def test_observe_basic(self, handler, mock_bridge_process):
        expected = ObserveResult(
            actions=[
                Action(code="print(thread.get_frames())", description="Show backtrace"),
                Action(code="print(frame.registers)", description="Show registers"),
            ],
            description="Process is stopped at breakpoint",
        )

        with patch.object(handler.context_builder, "build") as mock_build, \
             patch.object(handler.context_builder, "format_for_prompt") as mock_format:
            mock_build.return_value = ProcessSnapshot(
                registers=[], process_state="stopped"
            )
            mock_format.return_value = "context"
            handler.translate_engine.llm.chat_structured.return_value = expected

            result = await handler.observe(mock_bridge_process)
            assert isinstance(result, ObserveResult)
            assert len(result.actions) == 2

    async def test_observe_with_instruction(self, handler, mock_bridge_process):
        expected = ObserveResult(
            actions=[Action(code="print(process.read_memory(frame.sp, 64))", description="Read stack")],
            description="Focused on memory",
        )

        with patch.object(handler.context_builder, "build") as mock_build, \
             patch.object(handler.context_builder, "format_for_prompt") as mock_format:
            mock_build.return_value = ProcessSnapshot(
                registers=[], process_state="stopped"
            )
            mock_format.return_value = "context"
            handler.translate_engine.llm.chat_structured.return_value = expected

            result = await handler.observe(
                mock_bridge_process, instruction="focus on memory layout"
            )
            assert "memory" in result.description.lower()

    async def test_observe_calls_translate_observe(self, handler, mock_bridge_process):
        with patch.object(handler.translate_engine, "translate_observe", new_callable=AsyncMock) as mock_to:
            with patch.object(handler.context_builder, "build"), \
                 patch.object(handler.context_builder, "format_for_prompt", return_value="ctx"):
                mock_to.return_value = ObserveResult(actions=[], description="ok")
                await handler.observe(mock_bridge_process)
            mock_to.assert_called_once()

    async def test_observe_without_instruction(self, handler, mock_bridge_process):
        with patch.object(handler.translate_engine, "translate_observe", new_callable=AsyncMock) as mock_to:
            with patch.object(handler.context_builder, "build"), \
                 patch.object(handler.context_builder, "format_for_prompt", return_value="ctx"):
                mock_to.return_value = ObserveResult(actions=[], description="ok")
                await handler.observe(mock_bridge_process, instruction=None)
            assert mock_to.call_args.kwargs.get("instruction") is None
