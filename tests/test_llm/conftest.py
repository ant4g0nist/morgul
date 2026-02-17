"""LLM test fixtures — mock SDK responses for each provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from morgul.llm.types import ChatMessage, ModelConfig, ToolDefinition


# ---------------------------------------------------------------------------
# Model configs for each provider
# ---------------------------------------------------------------------------

@pytest.fixture()
def anthropic_config():
    return ModelConfig(
        provider="anthropic",
        model_name="claude-sonnet-4-20250514",
        api_key="test-key-anthropic",
        temperature=0.5,
        max_tokens=1024,
    )


@pytest.fixture()
def openai_config():
    return ModelConfig(
        provider="openai",
        model_name="gpt-4",
        api_key="test-key-openai",
        temperature=0.5,
        max_tokens=1024,
    )


@pytest.fixture()
def ollama_config():
    return ModelConfig(
        provider="ollama",
        model_name="llama3",
        base_url="http://localhost:11434",
        temperature=0.5,
        max_tokens=1024,
    )


# ---------------------------------------------------------------------------
# Common test data
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_messages():
    return [
        ChatMessage(role="system", content="You are a helpful assistant."),
        ChatMessage(role="user", content="Hello, world!"),
    ]


@pytest.fixture()
def sample_tools():
    return [
        ToolDefinition(
            name="act",
            description="Execute an action",
            parameters={
                "type": "object",
                "properties": {"instruction": {"type": "string"}},
                "required": ["instruction"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Mock Anthropic SDK response
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_anthropic_response():
    """Simulates an anthropic.types.Message object."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Here is my response"

    response = MagicMock()
    response.content = [text_block]

    usage = MagicMock()
    usage.input_tokens = 100
    usage.output_tokens = 50
    response.usage = usage

    return response


@pytest.fixture()
def mock_anthropic_tool_response():
    """Anthropic response with tool_use block."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Let me use a tool"

    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "tool_call_1"
    tool_block.name = "act"
    tool_block.input = {"instruction": "set breakpoint"}

    response = MagicMock()
    response.content = [text_block, tool_block]

    usage = MagicMock()
    usage.input_tokens = 150
    usage.output_tokens = 75
    response.usage = usage

    return response


# ---------------------------------------------------------------------------
# Mock OpenAI SDK response
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_openai_response():
    """Simulates an openai ChatCompletion object."""
    message = MagicMock()
    message.content = "Here is my response"
    message.tool_calls = None

    choice = MagicMock()
    choice.message = message

    usage = MagicMock()
    usage.prompt_tokens = 100
    usage.completion_tokens = 50

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage

    return response


@pytest.fixture()
def mock_openai_tool_response():
    """OpenAI response with function call."""
    func = MagicMock()
    func.name = "act"
    func.arguments = '{"instruction": "set breakpoint"}'

    tc = MagicMock()
    tc.id = "call_1"
    tc.function = func

    message = MagicMock()
    message.content = ""
    message.tool_calls = [tc]

    choice = MagicMock()
    choice.message = message

    usage = MagicMock()
    usage.prompt_tokens = 150
    usage.completion_tokens = 75

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage

    return response


# ---------------------------------------------------------------------------
# Mock Ollama SDK response
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_ollama_response():
    """Simulates an Ollama chat response (dict-like)."""
    return {
        "message": {"role": "assistant", "content": "Here is my response"},
        "prompt_eval_count": 100,
        "eval_count": 50,
    }


@pytest.fixture()
def mock_ollama_tool_response():
    """Ollama response with tool calls."""
    return {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "act",
                        "arguments": {"instruction": "set breakpoint"},
                    },
                }
            ],
        },
        "prompt_eval_count": 150,
        "eval_count": 75,
    }
