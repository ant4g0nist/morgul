"""Tests for morgul-llm types and utilities."""

from __future__ import annotations

from pydantic import BaseModel

from morgul.llm.types import ChatMessage, ModelConfig, ToolCall, ToolDefinition, ToolResult, Usage
from morgul.llm.structured import create_extraction_tool, parse_structured_response, pydantic_to_json_schema


def test_model_config_defaults():
    config = ModelConfig(provider="anthropic", model_name="claude-sonnet-4-20250514")
    assert config.temperature == 0.7
    assert config.max_tokens == 4096
    assert config.api_key is None


def test_chat_message():
    msg = ChatMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.tool_calls is None


def test_tool_call():
    tc = ToolCall(id="tc_1", name="act", arguments={"instruction": "set breakpoint"})
    assert tc.name == "act"
    assert tc.arguments["instruction"] == "set breakpoint"


def test_tool_result():
    tr = ToolResult(tool_call_id="tc_1", content="Breakpoint set")
    assert not tr.is_error


def test_tool_definition():
    td = ToolDefinition(
        name="act",
        description="Execute action",
        parameters={"type": "object", "properties": {"instruction": {"type": "string"}}},
    )
    assert td.name == "act"


def test_usage():
    usage = Usage(input_tokens=100, output_tokens=50)
    assert usage.input_tokens == 100


class SampleModel(BaseModel):
    name: str
    value: int


def test_pydantic_to_json_schema():
    schema = pydantic_to_json_schema(SampleModel)
    assert schema["type"] == "object"
    assert "name" in schema["properties"]
    assert "value" in schema["properties"]


def test_parse_structured_response():
    result = parse_structured_response('{"name": "test", "value": 42}', SampleModel)
    assert result.name == "test"
    assert result.value == 42


def test_create_extraction_tool():
    tool = create_extraction_tool(SampleModel)
    assert tool.name == "extract_samplemodel"
    assert "SampleModel" in tool.description
