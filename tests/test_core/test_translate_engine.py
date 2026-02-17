"""Tests for TranslateEngine — NL → Python code / LLDB command translation."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from morgul.core.translate.engine import TranslateEngine
from morgul.core.types.actions import Action, ObserveResult
from morgul.core.types.context import ProcessSnapshot, RegisterInfo
from morgul.core.types.llm import TranslateResponse
from morgul.llm.types import LLMResponse, ToolCall, Usage


class SampleExtract(BaseModel):
    function_name: str
    address: int


class TestTranslateEngine:
    @pytest.fixture()
    def engine(self, mock_llm_client):
        return TranslateEngine(mock_llm_client)

    @pytest.fixture()
    def snapshot(self):
        return ProcessSnapshot(
            registers=[RegisterInfo(name="rax", value=0x42, size=8)],
            process_state="stopped",
        )

    async def test_translate_structured(self, engine, snapshot):
        expected = TranslateResponse(
            code="print(thread.get_frames())",
            reasoning="User wants backtrace",
        )
        engine.llm.chat_structured.return_value = expected

        result = await engine.translate("show backtrace", snapshot, "context text")
        assert isinstance(result, TranslateResponse)
        assert result.code == "print(thread.get_frames())"

    async def test_translate_with_actions(self, engine, snapshot):
        expected = TranslateResponse(
            actions=[Action(code="print('hello')", description="greet")],
            reasoning="test",
        )
        engine.llm.chat_structured.return_value = expected

        result = await engine.translate("greet", snapshot, "context text")
        assert len(result.actions) == 1
        assert result.actions[0].code == "print('hello')"

    async def test_translate_fallback_to_raw_code(self, engine, snapshot):
        """When chat_structured fails, falls back to raw chat + parsing (code format)."""
        engine.llm.chat_structured.side_effect = Exception("structured failed")
        engine.llm.chat.return_value = LLMResponse(
            content='{"code": "print(frame.pc)", "reasoning": "ok"}',
        )

        result = await engine.translate("show pc", snapshot, "context text")
        assert isinstance(result, TranslateResponse)
        assert result.code == "print(frame.pc)"

    async def test_translate_fallback_to_raw_actions(self, engine, snapshot):
        """Fallback parsing still handles legacy action format."""
        engine.llm.chat_structured.side_effect = Exception("structured failed")
        engine.llm.chat.return_value = LLMResponse(
            content='{"actions": [{"code": "print(1)", "description": "test"}], "reasoning": "ok"}',
        )

        result = await engine.translate("test", snapshot, "context text")
        assert isinstance(result, TranslateResponse)
        assert result.actions[0].code == "print(1)"

    async def test_translate_fallback_raw_unparseable(self, engine, snapshot):
        """When both structured and raw parsing fail, treats content as raw code."""
        engine.llm.chat_structured.side_effect = Exception("structured failed")
        engine.llm.chat.return_value = LLMResponse(content="print(frame.registers)")

        result = await engine.translate("show registers", snapshot, "context text")
        assert result.code == "print(frame.registers)"

    async def test_translate_extract(self, engine):
        expected = SampleExtract(function_name="main", address=0x1000)
        engine.llm.chat_structured.return_value = expected

        result = await engine.translate_extract(
            instruction="extract function info",
            context_text="context",
            response_model=SampleExtract,
        )
        assert isinstance(result, SampleExtract)
        assert result.function_name == "main"

    async def test_translate_observe(self, engine):
        expected = ObserveResult(
            actions=[Action(code="print(thread.get_frames())", description="backtrace")],
            description="Process is stopped",
        )
        engine.llm.chat_structured.return_value = expected

        result = await engine.translate_observe(context_text="context")
        assert isinstance(result, ObserveResult)
        assert len(result.actions) == 1

    async def test_translate_observe_with_instruction(self, engine):
        expected = ObserveResult(actions=[], description="Focused observation")
        engine.llm.chat_structured.return_value = expected

        result = await engine.translate_observe(
            context_text="context", instruction="focus on memory"
        )
        assert result.description == "Focused observation"

    async def test_translate_observe_fallback(self, engine):
        """When structured observe fails, falls back to raw parsing."""
        engine.llm.chat_structured.side_effect = Exception("fail")
        engine.llm.chat.return_value = LLMResponse(
            content='{"actions": [{"code": "print(1)", "description": "test"}], "description": "ok"}',
        )

        result = await engine.translate_observe(context_text="context")
        assert isinstance(result, ObserveResult)

    def test_parse_raw_response_code_format(self):
        engine = TranslateEngine(MagicMock())
        result = engine._parse_raw_response(
            '{"code": "print(frame.pc)", "reasoning": "test"}'
        )
        assert result.code == "print(frame.pc)"

    def test_parse_raw_response_actions_format(self):
        engine = TranslateEngine(MagicMock())
        result = engine._parse_raw_response(
            '{"actions": [{"code": "print(1)", "description": "test"}], "reasoning": "ok"}'
        )
        assert result.actions[0].code == "print(1)"

    def test_parse_raw_response_invalid_json(self):
        engine = TranslateEngine(MagicMock())
        result = engine._parse_raw_response("print(frame.registers)")
        assert result.code == "print(frame.registers)"

    def test_parse_observe_response_valid(self):
        engine = TranslateEngine(MagicMock())
        result = engine._parse_observe_response(
            '{"actions": [{"code": "print(1)", "description": "test"}], "description": "ok"}'
        )
        assert result.actions[0].code == "print(1)"

    def test_parse_observe_response_invalid(self):
        engine = TranslateEngine(MagicMock())
        result = engine._parse_observe_response("unparseable")
        assert result.actions == []
        assert "Failed" in result.description
