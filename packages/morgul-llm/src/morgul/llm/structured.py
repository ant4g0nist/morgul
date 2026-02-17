from __future__ import annotations

import json
from typing import Any, Dict, Type, TypeVar

from pydantic import BaseModel, ValidationError

from .types import ToolDefinition

T = TypeVar("T", bound=BaseModel)


def pydantic_to_json_schema(model: Type[BaseModel]) -> Dict[str, Any]:
    """Convert a Pydantic model class to a JSON Schema dict.

    Strips internal Pydantic keys (``$defs``, ``title``) so the schema is
    suitable for use in tool / function definitions sent to LLM providers.
    """
    schema = model.model_json_schema()
    # Remove top-level keys that providers don't need
    schema.pop("title", None)
    # Inline any $defs references for maximum compatibility
    defs = schema.pop("$defs", None)
    if defs is not None:
        schema = _inline_refs(schema, defs)
    return schema


def _inline_refs(node: Any, defs: Dict[str, Any]) -> Any:
    """Recursively replace ``$ref`` pointers with their definitions."""
    if isinstance(node, dict):
        if "$ref" in node:
            ref_path = node["$ref"]  # e.g. "#/$defs/Foo"
            ref_name = ref_path.rsplit("/", 1)[-1]
            resolved = defs.get(ref_name, node)
            resolved = dict(resolved)  # shallow copy
            resolved.pop("title", None)
            return _inline_refs(resolved, defs)
        return {k: _inline_refs(v, defs) for k, v in node.items()}
    if isinstance(node, list):
        return [_inline_refs(item, defs) for item in node]
    return node


def parse_structured_response(content: str, model: Type[T]) -> T:
    """Parse a JSON string into a Pydantic model instance.

    Raises ``ValueError`` with a helpful message on failure.
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM response is not valid JSON: {exc}"
        ) from exc

    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ValueError(
            f"LLM response does not match schema for {model.__name__}: {exc}"
        ) from exc


def create_extraction_tool(model: Type[BaseModel]) -> ToolDefinition:
    """Create a ``ToolDefinition`` that forces the LLM to output data matching *model*.

    The tool is named ``extract_{model_name}`` and its parameters are the
    JSON schema derived from the Pydantic model.
    """
    schema = pydantic_to_json_schema(model)
    name = f"extract_{model.__name__.lower()}"
    return ToolDefinition(
        name=name,
        description=(
            f"Extract structured data matching the {model.__name__} schema. "
            "You MUST call this tool with the extracted information."
        ),
        parameters=schema,
    )
