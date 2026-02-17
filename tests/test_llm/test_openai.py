"""Tests for OpenAIClient with mocked SDK."""

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


class TestOpenAIClient:
    @pytest.fixture()
    def client(self, openai_config):
        mock_sdk = MagicMock()
        mock_sdk.AsyncOpenAI.return_value = AsyncMock()
        with patch.dict(sys.modules, {"openai": mock_sdk}):
            from morgul.llm.openai import OpenAIClient
            c = OpenAIClient(openai_config)
        return c

    async def test_chat_basic(self, client, mock_openai_response):
        client._client.chat.completions.create = AsyncMock(return_value=mock_openai_response)

        messages = [ChatMessage(role="user", content="Hello")]
        result = await client.chat(messages)

        assert isinstance(result, LLMResponse)
        assert result.content == "Here is my response"
        assert result.usage.input_tokens == 100

    async def test_chat_with_tools(self, client, mock_openai_tool_response, sample_tools):
        client._client.chat.completions.create = AsyncMock(return_value=mock_openai_tool_response)

        messages = [ChatMessage(role="user", content="Use a tool")]
        result = await client.chat(messages, tools=sample_tools)

        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "act"

    async def test_chat_api_error(self, client):
        client._client.chat.completions.create = AsyncMock(side_effect=Exception("API error"))

        messages = [ChatMessage(role="user", content="Hello")]
        with pytest.raises(RuntimeError, match="OpenAI API call failed"):
            await client.chat(messages)

    async def test_chat_structured(self, client):
        func = MagicMock()
        func.name = "extract_simpleoutput"
        func.arguments = json.dumps({"answer": "42", "confidence": 0.95})

        tc = MagicMock()
        tc.id = "call_1"
        tc.function = func

        message = MagicMock()
        message.content = ""
        message.tool_calls = [tc]

        choice = MagicMock()
        choice.message = message

        response = MagicMock()
        response.choices = [choice]
        response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

        client._client.chat.completions.create = AsyncMock(return_value=response)

        messages = [ChatMessage(role="user", content="Extract")]
        result = await client.chat_structured(messages, response_model=SimpleOutput)
        assert isinstance(result, SimpleOutput)
        assert result.answer == "42"

    def test_to_openai_messages(self):
        from morgul.llm.openai import OpenAIClient
        messages = [
            ChatMessage(role="system", content="Be helpful"),
            ChatMessage(role="user", content="Hi"),
        ]
        api = OpenAIClient._to_openai_messages(messages)
        assert len(api) == 2
        assert api[0]["role"] == "system"

    def test_to_openai_messages_tool_result(self):
        from morgul.llm.openai import OpenAIClient
        messages = [
            ChatMessage(role="tool", content="result", tool_call_id="tc_1"),
        ]
        api = OpenAIClient._to_openai_messages(messages)
        assert api[0]["role"] == "tool"
        assert api[0]["tool_call_id"] == "tc_1"

    def test_to_openai_messages_with_tool_calls(self):
        from morgul.llm.openai import OpenAIClient
        messages = [
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="tc_1", name="act", arguments={"x": 1})],
            ),
        ]
        api = OpenAIClient._to_openai_messages(messages)
        assert "tool_calls" in api[0]
        assert api[0]["tool_calls"][0]["function"]["name"] == "act"

    def test_tool_to_function(self):
        from morgul.llm.openai import OpenAIClient
        tool = ToolDefinition(name="test", description="A test tool", parameters={"type": "object"})
        result = OpenAIClient._tool_to_function(tool)
        assert result["type"] == "function"
        assert result["function"]["name"] == "test"

    def test_from_openai_response_no_tool_calls(self, mock_openai_response):
        from morgul.llm.openai import OpenAIClient
        result = OpenAIClient._from_openai_response(mock_openai_response)
        assert result.content == "Here is my response"
        assert result.tool_calls is None

    def test_from_openai_response_with_tool_calls(self, mock_openai_tool_response):
        from morgul.llm.openai import OpenAIClient
        result = OpenAIClient._from_openai_response(mock_openai_tool_response)
        assert result.tool_calls is not None
        assert result.tool_calls[0].name == "act"
