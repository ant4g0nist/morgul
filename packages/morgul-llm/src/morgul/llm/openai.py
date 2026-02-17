from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel

from .structured import create_extraction_tool, parse_structured_response, pydantic_to_json_schema
from .types import (
    ChatMessage,
    LLMResponse,
    ModelConfig,
    ToolCall,
    ToolDefinition,
    Usage,
)

T = TypeVar("T", bound=BaseModel)


class OpenAIClient:
    """LLM client backed by the OpenAI Chat Completions API."""

    def __init__(self, config: ModelConfig) -> None:
        try:
            import openai
        except ImportError as exc:
            raise ImportError(
                "The 'openai' package is required for OpenAIClient. "
                "Install it with: pip install openai"
            ) from exc

        self._config = config
        kwargs: Dict[str, Any] = {}
        if config.api_key is not None:
            kwargs["api_key"] = config.api_key
        if config.base_url is not None:
            kwargs["base_url"] = config.base_url
        self._client = openai.AsyncOpenAI(**kwargs)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
    ) -> LLMResponse:
        """Send *messages* to the OpenAI API and return a unified response."""
        api_messages = self._to_openai_messages(messages)

        kwargs: Dict[str, Any] = {
            "model": self._config.model_name,
            "messages": api_messages,
            "temperature": self._config.temperature,
            "max_completion_tokens": self._config.max_tokens,
        }
        if tools:
            kwargs["tools"] = [self._tool_to_function(t) for t in tools]

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise RuntimeError(
                f"OpenAI API call failed: {exc}"
            ) from exc

        return self._from_openai_response(response)

    async def chat_structured(
        self,
        messages: List[ChatMessage],
        response_model: Type[T],
        tools: Optional[List[ToolDefinition]] = None,
    ) -> T:
        """Force structured output via function calling, then parse the result."""
        extraction_tool = create_extraction_tool(response_model)
        all_tools = list(tools or []) + [extraction_tool]

        response = await self.chat(messages, tools=all_tools)

        # If the model called the extraction function, use its arguments
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
    def _to_openai_messages(messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        """Convert ``ChatMessage`` list to OpenAI Chat Completions format."""
        api_messages: List[Dict[str, Any]] = []

        for msg in messages:
            if msg.role == "tool":
                api_messages.append(
                    {
                        "role": "tool",
                        "content": msg.content,
                        "tool_call_id": msg.tool_call_id or "",
                    }
                )
                continue

            entry: Dict[str, Any] = {
                "role": msg.role,
                "content": msg.content,
            }

            if msg.name is not None:
                entry["name"] = msg.name

            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]

            api_messages.append(entry)

        return api_messages

    @staticmethod
    def _from_openai_response(response: Any) -> LLMResponse:
        """Convert an OpenAI ``ChatCompletion`` object to a unified ``LLMResponse``."""
        choice = response.choices[0]
        message = choice.message

        content = message.content or ""
        tool_calls: List[ToolCall] = []

        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    arguments = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    arguments = {"raw": tc.function.arguments}

                tool_calls.append(
                    ToolCall(
                        id=tc.id or str(uuid.uuid4()),
                        name=tc.function.name,
                        arguments=arguments,
                    )
                )

        usage = None
        if response.usage is not None:
            usage = Usage(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
            )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls or None,
            usage=usage,
            raw=response,
        )

    @staticmethod
    def _tool_to_function(tool: ToolDefinition) -> Dict[str, Any]:
        """Convert a ``ToolDefinition`` to the OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }

    @staticmethod
    def _schema_to_function(model: Type[BaseModel]) -> Dict[str, Any]:
        """Build an OpenAI function dict from a Pydantic model."""
        schema = pydantic_to_json_schema(model)
        return {
            "type": "function",
            "function": {
                "name": f"extract_{model.__name__.lower()}",
                "description": f"Extract structured data matching the {model.__name__} schema.",
                "parameters": schema,
            },
        }
