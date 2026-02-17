"""Tests for ExtractHandler — structured data extraction."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from morgul.core.primitives.extract import ExtractHandler
from morgul.core.types.context import ProcessSnapshot, RegisterInfo


class FunctionInfo(BaseModel):
    name: str
    address: int
    num_args: int


class TestExtractHandler:
    @pytest.fixture()
    def handler(self, mock_llm_client):
        return ExtractHandler(mock_llm_client)

    async def test_extract_success(self, handler, mock_bridge_process):
        expected = FunctionInfo(name="main", address=0x1000, num_args=2)

        with patch.object(handler.context_builder, "build") as mock_build, \
             patch.object(handler.context_builder, "format_for_prompt") as mock_format:
            mock_build.return_value = ProcessSnapshot(
                registers=[], process_state="stopped"
            )
            mock_format.return_value = "context"
            handler.translate_engine.llm.chat_structured.return_value = expected

            result = await handler.extract(
                "extract function info", mock_bridge_process, FunctionInfo
            )
            assert isinstance(result, FunctionInfo)
            assert result.name == "main"
            assert result.address == 0x1000

    async def test_extract_calls_translate_extract(self, handler, mock_bridge_process):
        expected = FunctionInfo(name="foo", address=0x2000, num_args=1)

        with patch.object(handler.translate_engine, "translate_extract", new_callable=AsyncMock) as mock_te:
            with patch.object(handler.context_builder, "build"), \
                 patch.object(handler.context_builder, "format_for_prompt", return_value="ctx"):
                mock_te.return_value = expected
                result = await handler.extract("extract", mock_bridge_process, FunctionInfo)

            mock_te.assert_called_once()
            assert result.name == "foo"

    async def test_extract_passes_response_model(self, handler, mock_bridge_process):
        with patch.object(handler.translate_engine, "translate_extract", new_callable=AsyncMock) as mock_te:
            with patch.object(handler.context_builder, "build"), \
                 patch.object(handler.context_builder, "format_for_prompt", return_value="ctx"):
                mock_te.return_value = FunctionInfo(name="x", address=0, num_args=0)
                await handler.extract("extract", mock_bridge_process, FunctionInfo)

            call_kwargs = mock_te.call_args
            assert call_kwargs.kwargs.get("response_model") == FunctionInfo or \
                   FunctionInfo in call_kwargs.args
