from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    """Configuration for an LLM provider and model."""

    provider: Literal["anthropic", "openai", "ollama"]
    model_name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096


class ToolCall(BaseModel):
    """Represents a tool/function call requested by the model."""

    id: str
    name: str
    arguments: Dict[str, Any]


class ToolResult(BaseModel):
    """Result of executing a tool call."""

    tool_call_id: str
    content: str
    is_error: bool = False


class ChatMessage(BaseModel):
    """A single message in a chat conversation."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


class ToolDefinition(BaseModel):
    """Definition of a tool that can be called by the model."""

    name: str
    description: str
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema dict describing the tool parameters",
    )


class Usage(BaseModel):
    """Token usage information from an LLM response."""

    input_tokens: int
    output_tokens: int


class LLMResponse(BaseModel):
    """Unified response from any LLM provider."""

    content: str
    tool_calls: Optional[List[ToolCall]] = None
    usage: Optional[Usage] = None
    raw: Any = None

    model_config = {"arbitrary_types_allowed": True}
