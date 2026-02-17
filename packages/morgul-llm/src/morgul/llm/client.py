from __future__ import annotations

from typing import List, Optional, Protocol, Type, TypeVar, runtime_checkable

from pydantic import BaseModel

from .types import ChatMessage, LLMResponse, ModelConfig, ToolDefinition

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class LLMClient(Protocol):
    """Protocol that every LLM provider client must satisfy."""

    async def chat(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
    ) -> LLMResponse:
        """Send a list of messages and (optionally) tool definitions, return a response."""
        ...

    async def chat_structured(
        self,
        messages: List[ChatMessage],
        response_model: Type[T],
        tools: Optional[List[ToolDefinition]] = None,
    ) -> T:
        """Like ``chat`` but parse the response into a Pydantic model *response_model*."""
        ...


def create_llm_client(config: ModelConfig) -> LLMClient:
    """Factory that returns the appropriate client for *config.provider*.

    Provider SDKs are imported lazily so users only need the SDK they use.
    """
    if config.provider == "anthropic":
        from .anthropic import AnthropicClient

        return AnthropicClient(config)

    if config.provider == "openai":
        from .openai import OpenAIClient

        return OpenAIClient(config)

    if config.provider == "ollama":
        from .ollama import OllamaClient

        return OllamaClient(config)

    raise ValueError(f"Unsupported LLM provider: {config.provider!r}")
