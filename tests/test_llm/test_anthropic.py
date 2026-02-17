"""Tests for AnthropicClient with mocked SDK."""

from __future__ import annotations

import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from morgul.llm.types import ChatMessage, LLMResponse, ToolCall, ToolDefinition


class SimpleOutput(BaseModel):
    answer: str
    confidence: float


class TestAnthropicClient:
    @pytest.fixture()
    def client(self, anthropic_config):
        mock_sdk = MagicMock()
        mock_sdk.AsyncAnthropic.return_value = AsyncMock()
        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            from morgul.llm.anthropic import AnthropicClient
            c = AnthropicClient(anthropic_config)
        return c

    async def test_chat_basic(self, client, mock_anthropic_response):
        client._client.messages.create = AsyncMock(return_value=mock_anthropic_response)

        messages = [ChatMessage(role="user", content="Hello")]
        result = await client.chat(messages)

        assert isinstance(result, LLMResponse)
        assert result.content == "Here is my response"
        assert result.usage is not None
        assert result.usage.input_tokens == 100

    async def test_chat_with_system_message(self, client, mock_anthropic_response):
        client._client.messages.create = AsyncMock(return_value=mock_anthropic_response)

        messages = [
            ChatMessage(role="system", content="You are helpful"),
            ChatMessage(role="user", content="Hello"),
        ]
        result = await client.chat(messages)
        assert result.content == "Here is my response"

    async def test_chat_with_tools(self, client, mock_anthropic_tool_response, sample_tools):
        client._client.messages.create = AsyncMock(return_value=mock_anthropic_tool_response)

        messages = [ChatMessage(role="user", content="Use a tool")]
        result = await client.chat(messages, tools=sample_tools)

        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "act"

    async def test_chat_api_error(self, client):
        client._client.messages.create = AsyncMock(side_effect=Exception("API error"))

        messages = [ChatMessage(role="user", content="Hello")]
        with pytest.raises(RuntimeError, match="Anthropic API call failed"):
            await client.chat(messages)

    async def test_chat_structured(self, client):
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "tool_1"
        tool_block.name = "extract_simpleoutput"
        tool_block.input = {"answer": "42", "confidence": 0.95}

        response = MagicMock()
        response.content = [tool_block]
        response.usage = MagicMock(input_tokens=100, output_tokens=50)

        client._client.messages.create = AsyncMock(return_value=response)

        messages = [ChatMessage(role="user", content="Extract data")]
        result = await client.chat_structured(messages, response_model=SimpleOutput)
        assert isinstance(result, SimpleOutput)
        assert result.answer == "42"
        assert result.confidence == 0.95

    async def test_chat_structured_fallback_to_content(self, client, mock_anthropic_response):
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = '{"answer": "hello", "confidence": 0.5}'
        mock_anthropic_response.content = [text_block]
        client._client.messages.create = AsyncMock(return_value=mock_anthropic_response)

        messages = [ChatMessage(role="user", content="Extract")]
        result = await client.chat_structured(messages, response_model=SimpleOutput)
        assert result.answer == "hello"

    def test_to_anthropic_messages_system(self):
        from morgul.llm.anthropic import AnthropicClient
        messages = [
            ChatMessage(role="system", content="Be helpful"),
            ChatMessage(role="user", content="Hi"),
        ]
        system, api = AnthropicClient._to_anthropic_messages(messages)
        assert system == "Be helpful"
        assert len(api) == 1
        assert api[0]["role"] == "user"

    def test_to_anthropic_messages_tool_result(self):
        from morgul.llm.anthropic import AnthropicClient
        messages = [
            ChatMessage(role="tool", content="result", tool_call_id="tc_1"),
        ]
        system, api = AnthropicClient._to_anthropic_messages(messages)
        assert system is None
        assert len(api) == 1
        assert api[0]["content"][0]["type"] == "tool_result"

    def test_to_anthropic_messages_assistant_with_tool_calls(self):
        from morgul.llm.anthropic import AnthropicClient
        messages = [
            ChatMessage(
                role="assistant",
                content="Let me help",
                tool_calls=[ToolCall(id="tc_1", name="act", arguments={"x": 1})],
            ),
        ]
        system, api = AnthropicClient._to_anthropic_messages(messages)
        assert len(api) == 1
        content = api[0]["content"]
        assert any(b["type"] == "tool_use" for b in content)

    def test_tool_to_anthropic(self):
        from morgul.llm.anthropic import AnthropicClient
        tool = ToolDefinition(name="test", description="A test tool", parameters={"type": "object"})
        result = AnthropicClient._tool_to_anthropic(tool)
        assert result["name"] == "test"
        assert "input_schema" in result

    def test_from_anthropic_response_no_usage(self):
        from morgul.llm.anthropic import AnthropicClient
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "hello"

        response = MagicMock()
        response.content = [text_block]
        response.usage = None

        result = AnthropicClient._from_anthropic_response(response)
        assert result.content == "hello"
        assert result.usage is None
