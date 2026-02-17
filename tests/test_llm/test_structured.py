"""Tests for structured output helpers."""

from __future__ import annotations

from typing import List, Optional

import pytest
from pydantic import BaseModel

from morgul.llm.structured import (
    create_extraction_tool,
    parse_structured_response,
    pydantic_to_json_schema,
)


# ---------------------------------------------------------------------------
# Test models
# ---------------------------------------------------------------------------

class SimpleModel(BaseModel):
    name: str
    value: int


class NestedModel(BaseModel):
    items: List[SimpleModel]
    total: int


class OptionalFieldModel(BaseModel):
    required_field: str
    optional_field: Optional[str] = None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPydanticToJsonSchema:
    def test_basic_schema(self):
        schema = pydantic_to_json_schema(SimpleModel)
        assert schema["type"] == "object"
        assert "name" in schema["properties"]
        assert "value" in schema["properties"]

    def test_strips_title(self):
        schema = pydantic_to_json_schema(SimpleModel)
        assert "title" not in schema

    def test_inlines_refs(self):
        schema = pydantic_to_json_schema(NestedModel)
        assert "$defs" not in schema
        # The items property should have inline schema, not $ref
        items_prop = schema["properties"]["items"]
        assert "items" in items_prop  # array items schema
        assert "$ref" not in str(items_prop)

    def test_optional_field(self):
        schema = pydantic_to_json_schema(OptionalFieldModel)
        assert "required_field" in schema["properties"]
        assert "optional_field" in schema["properties"]


class TestParseStructuredResponse:
    def test_valid_json(self):
        result = parse_structured_response('{"name": "test", "value": 42}', SimpleModel)
        assert result.name == "test"
        assert result.value == 42

    def test_invalid_json(self):
        with pytest.raises(ValueError, match="not valid JSON"):
            parse_structured_response("not json{{{", SimpleModel)

    def test_schema_mismatch(self):
        with pytest.raises(ValueError, match="does not match schema"):
            parse_structured_response('{"wrong_field": "test"}', SimpleModel)

    def test_nested_model(self):
        data = '{"items": [{"name": "a", "value": 1}], "total": 1}'
        result = parse_structured_response(data, NestedModel)
        assert len(result.items) == 1
        assert result.items[0].name == "a"


class TestCreateExtractionTool:
    def test_creates_tool(self):
        tool = create_extraction_tool(SimpleModel)
        assert tool.name == "extract_simplemodel"
        assert "SimpleModel" in tool.description
        assert "type" in tool.parameters

    def test_tool_parameters_match_schema(self):
        tool = create_extraction_tool(SimpleModel)
        assert "properties" in tool.parameters
        assert "name" in tool.parameters["properties"]
