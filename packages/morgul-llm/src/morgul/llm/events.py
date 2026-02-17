"""LLM call observability — lightweight event hooks for request/response tracking."""

from __future__ import annotations

import time
from typing import Any, Callable, List, Optional, Protocol, Type, TypeVar

from pydantic import BaseModel

from .types import ChatMessage, LLMResponse, ToolDefinition, Usage

T = TypeVar("T", bound=BaseModel)


class LLMEvent:
    """Lightweight event emitted around LLM calls."""

    __slots__ = ("method", "duration", "usage", "model_type", "error")

    def __init__(
        self,
        method: str,
        duration: float = 0.0,
        usage: Optional[Usage] = None,
        model_type: Optional[str] = None,
        error: Optional[str] = None,
    ):
        self.method = method          # "chat" or "chat_structured"
        self.duration = duration      # seconds
        self.usage = usage            # token counts
        self.model_type = model_type  # response_model class name (structured only)
        self.error = error            # error message if failed


# Callback type: called with (event, is_start)
# is_start=True → request about to be sent
# is_start=False → response received (event has duration/usage)
LLMEventCallback = Callable[[LLMEvent, bool], None]


class InstrumentedLLMClient:
    """Wraps any LLMClient and fires callbacks on each call."""

    def __init__(self, client: Any, callback: LLMEventCallback):
        self._client = client
        self._callback = callback

    async def chat(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
    ) -> LLMResponse:
        event = LLMEvent(method="chat")
        self._callback(event, True)
        start = time.monotonic()

        try:
            response = await self._client.chat(messages, tools)
        except Exception as exc:
            event.duration = time.monotonic() - start
            event.error = str(exc)
            self._callback(event, False)
            raise

        event.duration = time.monotonic() - start
        event.usage = response.usage
        self._callback(event, False)
        return response

    async def chat_structured(
        self,
        messages: List[ChatMessage],
        response_model: Type[T],
        tools: Optional[List[ToolDefinition]] = None,
    ) -> T:
        event = LLMEvent(method="chat_structured", model_type=response_model.__name__)
        self._callback(event, True)
        start = time.monotonic()

        try:
            response = await self._client.chat_structured(messages, response_model, tools)
        except Exception as exc:
            event.duration = time.monotonic() - start
            event.error = str(exc)
            self._callback(event, False)
            raise

        event.duration = time.monotonic() - start
        self._callback(event, False)
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)
