from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar

from pydantic import BaseModel

from .structured import create_extraction_tool, parse_structured_response
from .types import (
    ChatMessage,
    LLMResponse,
    ModelConfig,
    ToolCall,
    ToolDefinition,
    Usage,
)

T = TypeVar("T", bound=BaseModel)


class AnthropicClient:
    """LLM client backed by the Anthropic Messages API."""

    def __init__(self, config: ModelConfig) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError(
                "The 'anthropic' package is required for AnthropicClient. "
                "Install it with: pip install anthropic"
            ) from exc

        self._config = config
        kwargs: Dict[str, Any] = {}
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        if config.base_url is not None:
            kwargs["base_url"] = config.base_url
        self._client = anthropic.AsyncAnthropic(**kwargs)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
    ) -> LLMResponse:
        """Send *messages* to the Anthropic API and return a unified response."""
        system_prompt, api_messages = self._to_anthropic_messages(messages)

        kwargs: Dict[str, Any] = {
            "model": self._config.model_name,
            "max_tokens": self._config.max_tokens,
            "temperature": self._config.temperature,
            "messages": api_messages,
        }
        if system_prompt is not None:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = [self._tool_to_anthropic(t) for t in tools]

        try:
            response = await self._client.messages.create(**kwargs)
        except Exception as exc:
            raise RuntimeError(
                f"Anthropic API call failed: {exc}"
            ) from exc

        return self._from_anthropic_response(response)

    async def chat_structured(
        self,
        messages: List[ChatMessage],
        response_model: Type[T],
        tools: Optional[List[ToolDefinition]] = None,
    ) -> T:
        """Force structured output by injecting a schema tool, then parse the result."""
        extraction_tool = create_extraction_tool(response_model)
        all_tools = list(tools or []) + [extraction_tool]

        response = await self.chat(messages, tools=all_tools)

        # If the model called the extraction tool, use its arguments directly
        if response.tool_calls:
            for tc in response.tool_calls:
                if tc.name == extraction_tool.name:
                    return parse_structured_response(
                        json.dumps(tc.arguments), response_model
                    )

        # Fallback: try to parse content directly
        return parse_structured_response(response.content, response_model)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_anthropic_messages(
        messages: List[ChatMessage],
    ) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """Convert ``ChatMessage`` list to Anthropic format.

        Returns ``(system_prompt, api_messages)``.  Anthropic expects
        the system prompt as a separate parameter rather than as a message.
        """
        system_prompt: Optional[str] = None
        api_messages: List[Dict[str, Any]] = []

        for msg in messages:
            if msg.role == "system":
                # Anthropic only supports a single system prompt; concatenate
                if system_prompt is None:
                    system_prompt = msg.content
                else:
                    system_prompt += "\n\n" + msg.content
                continue

            if msg.role == "tool":
                api_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id,
                                "content": msg.content,
                            }
                        ],
                    }
                )
                continue

            content: Any
            if msg.tool_calls:
                # Assistant message with tool_use blocks
                blocks: List[Dict[str, Any]] = []
                if msg.content:
                    blocks.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        }
                    )
                content = blocks
            else:
                content = msg.content

            api_messages.append({"role": msg.role, "content": content})

        return system_prompt, api_messages

    @staticmethod
    def _from_anthropic_response(response: Any) -> LLMResponse:
        """Convert an Anthropic ``Message`` object to a unified ``LLMResponse``."""
        text_parts: List[str] = []
        tool_calls: List[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input,
                    )
                )

        usage = None
        if hasattr(response, "usage") and response.usage is not None:
            usage = Usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

        return LLMResponse(
            content="\n".join(text_parts),
            tool_calls=tool_calls or None,
            usage=usage,
            raw=response,
        )

    @staticmethod
    def _tool_to_anthropic(tool: ToolDefinition) -> Dict[str, Any]:
        """Convert a ``ToolDefinition`` to the Anthropic tool format."""
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters,
        }

    @staticmethod
    def _schema_to_tool(model: Type[BaseModel]) -> Dict[str, Any]:
        """Build an Anthropic tool dict from a Pydantic model."""
        tool_def = create_extraction_tool(model)
        return {
            "name": tool_def.name,
            "description": tool_def.description,
            "input_schema": tool_def.parameters,
        }
