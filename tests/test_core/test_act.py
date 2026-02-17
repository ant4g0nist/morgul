"""Tests for ActHandler — NL → Python code execution with self-healing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from morgul.core.primitives.act import ActHandler
from morgul.core.types.actions import Action, ActResult
from morgul.core.types.context import ProcessSnapshot, RegisterInfo
from morgul.core.types.llm import TranslateResponse


@pytest.fixture()
def mock_snapshot():
    return ProcessSnapshot(
        registers=[RegisterInfo(name="rax", value=0, size=8)],
        process_state="stopped",
    )


def _make_handler(mock_llm_client, mock_debugger):
    """Create an ActHandler with mock target and process."""
    mock_target = MagicMock()
    mock_process = MagicMock()
    mock_process.selected_thread = MagicMock()
    mock_process.selected_thread.selected_frame = MagicMock()
    return ActHandler(
        mock_llm_client,
        mock_debugger,
        target=mock_target,
        process=mock_process,
        self_heal=True,
        max_retries=2,
    )


class TestActHandler:
    @pytest.fixture()
    def handler(self, mock_llm_client, mock_debugger):
        return _make_handler(mock_llm_client, mock_debugger)

    async def test_act_success(self, handler, mock_bridge_process):
        with patch.object(handler.context_builder, "build") as mock_build, \
             patch.object(handler.context_builder, "format_for_prompt") as mock_format:
            mock_build.return_value = ProcessSnapshot(
                registers=[], process_state="stopped"
            )
            mock_format.return_value = "context"

            handler.translate_engine.llm.chat_structured.return_value = TranslateResponse(
                code="print('frame #0: main')",
                reasoning="backtrace requested",
            )

            result = await handler.act("show backtrace", mock_bridge_process)
            assert isinstance(result, ActResult)
            assert result.success is True
            assert "main" in result.output

    async def test_act_no_code(self, handler, mock_bridge_process):
        with patch.object(handler.context_builder, "build"), \
             patch.object(handler.context_builder, "format_for_prompt"):
            handler.translate_engine.llm.chat_structured.return_value = TranslateResponse(
                code="", actions=[], reasoning=""
            )
            result = await handler.act("do nothing", mock_bridge_process)
            assert result.success is False
            assert "No code" in result.message

    async def test_act_code_failure(self, handler, mock_bridge_process):
        with patch.object(handler.context_builder, "build") as mock_build, \
             patch.object(handler.context_builder, "format_for_prompt") as mock_format:
            mock_build.return_value = ProcessSnapshot(
                registers=[], process_state="stopped"
            )
            mock_format.return_value = "context"

            handler.translate_engine.llm.chat_structured.return_value = TranslateResponse(
                code="raise ValueError('bad')",
                reasoning="trying",
            )

            # Disable self-heal for this test
            handler.self_heal = False
            result = await handler.act("bad command", mock_bridge_process)
            assert result.success is False
            assert "ValueError" in result.output

    async def test_act_self_heal_success(self, handler, mock_bridge_process):
        with patch.object(handler.context_builder, "build") as mock_build, \
             patch.object(handler.context_builder, "format_for_prompt") as mock_format:
            mock_build.return_value = ProcessSnapshot(
                registers=[], process_state="stopped"
            )
            mock_format.return_value = "context"

            # First translate returns code that fails, then heal succeeds
            handler.translate_engine.llm.chat_structured.side_effect = [
                TranslateResponse(
                    code="raise ValueError('fail')",
                    reasoning="first try",
                ),
                TranslateResponse(
                    code="print('success')",
                    reasoning="healed",
                ),
            ]

            result = await handler.act("do something", mock_bridge_process)
            assert result.success is True
            assert "success" in result.output

    async def test_act_self_heal_exhausted(self, handler, mock_bridge_process):
        with patch.object(handler.context_builder, "build") as mock_build, \
             patch.object(handler.context_builder, "format_for_prompt") as mock_format:
            mock_build.return_value = ProcessSnapshot(
                registers=[], process_state="stopped"
            )
            mock_format.return_value = "context"

            handler.translate_engine.llm.chat_structured.return_value = TranslateResponse(
                code="raise ValueError('always fails')",
                reasoning="trying",
            )

            result = await handler.act("always fails", mock_bridge_process)
            assert result.success is False

    async def test_act_with_actions_code(self, handler, mock_bridge_process):
        """Test that code from Action objects is also executed."""
        with patch.object(handler.context_builder, "build") as mock_build, \
             patch.object(handler.context_builder, "format_for_prompt") as mock_format:
            mock_build.return_value = ProcessSnapshot(
                registers=[], process_state="stopped"
            )
            mock_format.return_value = "context"

            handler.translate_engine.llm.chat_structured.return_value = TranslateResponse(
                actions=[
                    Action(code="bp = target.breakpoint_create_by_name('main')", description="set bp"),
                    Action(code="print('done')", description="confirm"),
                ],
                reasoning="set and confirm",
            )

            result = await handler.act("set breakpoint", mock_bridge_process)
            assert result.success is True

    async def test_act_self_heal_disabled(self, handler, mock_bridge_process):
        handler.self_heal = False
        with patch.object(handler.context_builder, "build") as mock_build, \
             patch.object(handler.context_builder, "format_for_prompt") as mock_format:
            mock_build.return_value = ProcessSnapshot(
                registers=[], process_state="stopped"
            )
            mock_format.return_value = "context"

            handler.translate_engine.llm.chat_structured.return_value = TranslateResponse(
                code="raise RuntimeError('error')",
                reasoning="try",
            )

            result = await handler.act("fail", mock_bridge_process)
            assert result.success is False

    async def test_act_legacy_command_fallback(self, handler, mock_bridge_process):
        """Legacy Action with command but no code wraps in execute_command."""
        with patch.object(handler.context_builder, "build") as mock_build, \
             patch.object(handler.context_builder, "format_for_prompt") as mock_format:
            mock_build.return_value = ProcessSnapshot(
                registers=[], process_state="stopped"
            )
            mock_format.return_value = "context"

            handler.translate_engine.llm.chat_structured.return_value = TranslateResponse(
                actions=[Action(command="bt", description="backtrace")],
                reasoning="legacy",
            )

            result = await handler.act("show backtrace", mock_bridge_process)
            # Should attempt to execute via debugger.execute_command wrapper
            assert isinstance(result, ActResult)
