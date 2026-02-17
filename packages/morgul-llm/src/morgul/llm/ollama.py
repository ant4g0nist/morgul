from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel

from .structured import (
    create_extraction_tool,
    parse_structured_response,
    pydantic_to_json_schema,
)
from .types import (
    ChatMessage,
    LLMResponse,
    ModelConfig,
    ToolCall,
    ToolDefinition,
    Usage,
)

T = TypeVar("T", bound=BaseModel)


class OllamaClient:
    """LLM client backed by a local Ollama instance."""

    def __init__(self, config: ModelConfig) -> None:
        try:
            import ollama
        except ImportError as exc:
            raise ImportError(
                "The 'ollama' package is required for OllamaClient. "
                "Install it with: pip install ollama"
            ) from exc

        self._config = config
        kwargs: Dict[str, Any] = {}
        if config.base_url is not None:
            kwargs["host"] = config.base_url
        self._client = ollama.AsyncClient(**kwargs)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
    ) -> LLMResponse:
        """Send *messages* to the Ollama API and return a unified response."""
        api_messages = self._to_ollama_messages(messages)

        kwargs: Dict[str, Any] = {
            "model": self._config.model_name,
            "messages": api_messages,
            "options": {
                "temperature": self._config.temperature,
                "num_predict": self._config.max_tokens,
            },
        }
        if tools:
            kwargs["tools"] = [self._tool_to_ollama(t) for t in tools]

        try:
            response = await self._client.chat(**kwargs)
        except Exception as exc:
            raise RuntimeError(
                f"Ollama API call failed: {exc}"
            ) from exc

        return self._from_ollama_response(response)

    async def chat_structured(
        self,
        messages: List[ChatMessage],
        response_model: Type[T],
        tools: Optional[List[ToolDefinition]] = None,
    ) -> T:
        """Get structured output by requesting JSON format with a schema instruction."""
        schema = pydantic_to_json_schema(response_model)
        schema_instruction = (
            "You MUST respond with valid JSON matching this exact schema:\n"
            f"```json\n{json.dumps(schema, indent=2)}\n```\n"
            "Do NOT include any text outside the JSON object."
        )

        # Prepend schema instruction as a system message
        augmented: List[ChatMessage] = [
            ChatMessage(role="system", content=schema_instruction),
            *messages,
        ]

        api_messages = self._to_ollama_messages(augmented)

        kwargs: Dict[str, Any] = {
            "model": self._config.model_name,
            "messages": api_messages,
            "format": "json",
            "options": {
                "temperature": self._config.temperature,
                "num_predict": self._config.max_tokens,
            },
        }

        try:
            response = await self._client.chat(**kwargs)
        except Exception as exc:
            raise RuntimeError(
                f"Ollama API call failed: {exc}"
            ) from exc

        content = response.get("message", {}).get("content", "")
        if hasattr(response, "message"):
            content = response.message.content or ""

        return parse_structured_response(content, response_model)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_ollama_messages(messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        """Convert ``ChatMessage`` list to Ollama format."""
        api_messages: List[Dict[str, Any]] = []

        for msg in messages:
            entry: Dict[str, Any] = {
                "role": msg.role,
                "content": msg.content,
            }

            if msg.role == "tool" and msg.tool_call_id is not None:
                entry["tool_call_id"] = msg.tool_call_id

            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]

            api_messages.append(entry)

        return api_messages

    @staticmethod
    def _from_ollama_response(response: Any) -> LLMResponse:
        """Convert an Ollama response to a unified ``LLMResponse``."""
        # Ollama responses can be dict-like or object-like depending on version
        if isinstance(response, dict):
            message = response.get("message", {})
            content = message.get("content", "")
            raw_tool_calls = message.get("tool_calls")
            prompt_eval_count = response.get("prompt_eval_count", 0)
            eval_count = response.get("eval_count", 0)
        else:
            message = getattr(response, "message", None)
            content = getattr(message, "content", "") or "" if message else ""
            raw_tool_calls = getattr(message, "tool_calls", None)
            prompt_eval_count = getattr(response, "prompt_eval_count", 0) or 0
            eval_count = getattr(response, "eval_count", 0) or 0

        tool_calls: List[ToolCall] = []
        if raw_tool_calls:
            for tc in raw_tool_calls:
                if isinstance(tc, dict):
                    func = tc.get("function", {})
                    tool_calls.append(
                        ToolCall(
                            id=tc.get("id", str(uuid.uuid4())),
                            name=func.get("name", ""),
                            arguments=func.get("arguments", {}),
                        )
                    )
                else:
                    func = getattr(tc, "function", None)
                    tool_calls.append(
                        ToolCall(
                            id=getattr(tc, "id", str(uuid.uuid4())),
                            name=getattr(func, "name", "") if func else "",
                            arguments=getattr(func, "arguments", {}) if func else {},
                        )
                    )

        usage = Usage(
            input_tokens=prompt_eval_count,
            output_tokens=eval_count,
        )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls or None,
            usage=usage,
            raw=response,
        )

    @staticmethod
    def _tool_to_ollama(tool: ToolDefinition) -> Dict[str, Any]:
        """Convert a ``ToolDefinition`` to Ollama's tool format."""
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }

    @staticmethod
    def _schema_to_tool(model: Type[BaseModel]) -> Dict[str, Any]:
        """Build an Ollama tool dict from a Pydantic model."""
        tool_def = create_extraction_tool(model)
        return {
            "type": "function",
            "function": {
                "name": tool_def.name,
                "description": tool_def.description,
                "parameters": tool_def.parameters,
            },
        }
