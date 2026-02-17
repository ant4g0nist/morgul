"""Tests for OllamaClient with mocked SDK."""

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


class TestOllamaClient:
    @pytest.fixture()
    def client(self, ollama_config):
        mock_sdk = MagicMock()
        mock_sdk.AsyncClient.return_value = AsyncMock()
        with patch.dict(sys.modules, {"ollama": mock_sdk}):
            from morgul.llm.ollama import OllamaClient
            c = OllamaClient(ollama_config)
        return c

    async def test_chat_basic(self, client, mock_ollama_response):
        client._client.chat = AsyncMock(return_value=mock_ollama_response)

        messages = [ChatMessage(role="user", content="Hello")]
        result = await client.chat(messages)

        assert isinstance(result, LLMResponse)
        assert result.content == "Here is my response"
        assert result.usage is not None
        assert result.usage.input_tokens == 100

    async def test_chat_with_tools(self, client, mock_ollama_tool_response, sample_tools):
        client._client.chat = AsyncMock(return_value=mock_ollama_tool_response)

        messages = [ChatMessage(role="user", content="Use a tool")]
        result = await client.chat(messages, tools=sample_tools)

        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "act"

    async def test_chat_api_error(self, client):
        client._client.chat = AsyncMock(side_effect=Exception("API error"))

        messages = [ChatMessage(role="user", content="Hello")]
        with pytest.raises(RuntimeError, match="Ollama API call failed"):
            await client.chat(messages)

    async def test_chat_structured(self, client):
        response = {
            "message": {"content": '{"answer": "42", "confidence": 0.95}'},
            "prompt_eval_count": 100,
            "eval_count": 50,
        }
        client._client.chat = AsyncMock(return_value=response)

        messages = [ChatMessage(role="user", content="Extract")]
        result = await client.chat_structured(messages, response_model=SimpleOutput)
        assert isinstance(result, SimpleOutput)
        assert result.answer == "42"

    async def test_chat_structured_object_response(self, client):
        """Test when Ollama returns an object-like response instead of dict."""
        msg = MagicMock()
        msg.content = '{"answer": "hello", "confidence": 0.8}'
        response = MagicMock()
        response.message = msg
        response.get = MagicMock(return_value={})
        client._client.chat = AsyncMock(return_value=response)

        messages = [ChatMessage(role="user", content="Extract")]
        result = await client.chat_structured(messages, response_model=SimpleOutput)
        assert result.answer == "hello"

    def test_to_ollama_messages(self):
        from morgul.llm.ollama import OllamaClient
        messages = [
            ChatMessage(role="system", content="Be helpful"),
            ChatMessage(role="user", content="Hi"),
        ]
        api = OllamaClient._to_ollama_messages(messages)
        assert len(api) == 2
        assert api[0]["role"] == "system"

    def test_to_ollama_messages_tool_result(self):
        from morgul.llm.ollama import OllamaClient
        messages = [
            ChatMessage(role="tool", content="result", tool_call_id="tc_1"),
        ]
        api = OllamaClient._to_ollama_messages(messages)
        assert api[0]["role"] == "tool"
        assert api[0]["tool_call_id"] == "tc_1"

    def test_from_ollama_response_dict(self, mock_ollama_response):
        from morgul.llm.ollama import OllamaClient
        result = OllamaClient._from_ollama_response(mock_ollama_response)
        assert result.content == "Here is my response"
        assert result.tool_calls is None

    def test_from_ollama_response_dict_with_tools(self, mock_ollama_tool_response):
        from morgul.llm.ollama import OllamaClient
        result = OllamaClient._from_ollama_response(mock_ollama_tool_response)
        assert result.tool_calls is not None
        assert result.tool_calls[0].name == "act"

    def test_from_ollama_response_object(self):
        from morgul.llm.ollama import OllamaClient
        msg = MagicMock()
        msg.content = "hello"
        msg.tool_calls = None

        response = MagicMock(spec=[])
        response.message = msg
        response.prompt_eval_count = 10
        response.eval_count = 5

        result = OllamaClient._from_ollama_response(response)
        assert result.content == "hello"

    def test_tool_to_ollama(self):
        from morgul.llm.ollama import OllamaClient
        tool = ToolDefinition(name="test", description="A test tool", parameters={"type": "object"})
        result = OllamaClient._tool_to_ollama(tool)
        assert result["type"] == "function"
        assert result["function"]["name"] == "test"
