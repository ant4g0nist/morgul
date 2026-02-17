"""NL → Python code / LLDB command translation engine."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import TYPE_CHECKING

from morgul.core.translate.prompts import ACT_PROMPT, EXTRACT_PROMPT, OBSERVE_PROMPT
from morgul.core.types.actions import Action, ObserveResult
from morgul.core.types.context import ProcessSnapshot
from morgul.core.types.llm import TranslateResponse

if TYPE_CHECKING:
    from pydantic import BaseModel

    from morgul.core.cache import ContentCache
    from morgul.llm import LLMClient
    from morgul.llm.types import ChatMessage

logger = logging.getLogger(__name__)


class TranslateEngine:
    """Translates natural language instructions into Python code or LLDB commands."""

    def __init__(self, llm_client: LLMClient, cache: ContentCache | None = None):
        self.llm = llm_client
        self._cache = cache

    def _cache_key(self, *parts: str) -> str:
        """Build a deterministic cache key from string parts."""
        blob = "\n".join(parts).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    async def translate(
        self,
        instruction: str,
        context: ProcessSnapshot,
        context_text: str,
    ) -> TranslateResponse:
        """Translate a natural language instruction into Python code.

        Note: caching for act() is handled at the ActHandler level
        (after execution succeeds) rather than here, because the LLM
        may produce code that fails and requires self-healing.
        """
        from morgul.llm.types import ChatMessage

        prompt = ACT_PROMPT.format(
            context=context_text,
            instruction=instruction,
        )

        messages = [ChatMessage(role="user", content=prompt)]

        try:
            response = await self.llm.chat_structured(
                messages=messages,
                response_model=TranslateResponse,
            )
        except Exception:
            logger.exception("Translation failed, attempting raw chat")
            raw_response = await self.llm.chat(messages=messages)
            response = self._parse_raw_response(raw_response.content)

        return response

    async def translate_extract(
        self,
        instruction: str,
        context_text: str,
        response_model: type[BaseModel],
    ):
        """Translate an extraction instruction and return structured data."""
        from morgul.llm.structured import pydantic_to_json_schema
        from morgul.llm.types import ChatMessage

        if self._cache is not None:
            key = self._cache_key(instruction, context_text, response_model.__name__, "extract")
            cached = self._cache.get_by_key(key)
            if cached is not None:
                logger.info("Cache hit: %s", key)
                return response_model.model_validate(cached)

        schema = pydantic_to_json_schema(response_model)
        prompt = EXTRACT_PROMPT.format(
            context=context_text,
            instruction=instruction,
            schema=json.dumps(schema, indent=2),
        )

        messages = [ChatMessage(role="user", content=prompt)]
        result = await self.llm.chat_structured(
            messages=messages,
            response_model=response_model,
        )

        if self._cache is not None:
            self._cache.set_by_key(key, result.model_dump())

        return result

    async def translate_observe(
        self,
        context_text: str,
        instruction: str | None = None,
    ) -> ObserveResult:
        """Generate observation-based action suggestions."""
        from morgul.llm.types import ChatMessage

        if self._cache is not None:
            key = self._cache_key(context_text, instruction or "", "observe")
            cached = self._cache.get_by_key(key)
            if cached is not None:
                logger.info("Cache hit: %s", key)
                return ObserveResult.model_validate(cached)

        instruction_section = ""
        if instruction:
            instruction_section = f"## User Focus\n{instruction}"

        prompt = OBSERVE_PROMPT.format(
            context=context_text,
            instruction_section=instruction_section,
        )

        messages = [ChatMessage(role="user", content=prompt)]

        try:
            result = await self.llm.chat_structured(
                messages=messages,
                response_model=ObserveResult,
            )
        except Exception:
            logger.exception("Observe translation failed, attempting raw chat")
            raw_response = await self.llm.chat(messages=messages)
            result = self._parse_observe_response(raw_response.content)

        if self._cache is not None:
            self._cache.set_by_key(key, result.model_dump())

        return result

    def _parse_raw_response(self, content: str) -> TranslateResponse:
        """Parse a raw LLM response into a TranslateResponse."""
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(content[start:end])

                # New format: single "code" field
                if "code" in data and isinstance(data["code"], str):
                    return TranslateResponse(
                        code=data["code"],
                        reasoning=data.get("reasoning", ""),
                    )

                # Legacy format: "actions" list with "command" keys
                actions = [
                    Action(
                        command=a.get("command", ""),
                        code=a.get("code", ""),
                        description=a.get("description", ""),
                    )
                    for a in data.get("actions", [])
                ]
                return TranslateResponse(
                    actions=actions,
                    reasoning=data.get("reasoning", ""),
                )
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

        # Last resort: treat entire content as a single code block
        return TranslateResponse(
            code=content.strip(),
            reasoning="Failed to parse structured response",
        )

    def _parse_observe_response(self, content: str) -> ObserveResult:
        """Parse a raw LLM response into an ObserveResult."""
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(content[start:end])
                actions = [
                    Action(
                        command=a.get("command", ""),
                        code=a.get("code", ""),
                        description=a.get("description", ""),
                    )
                    for a in data.get("actions", [])
                ]
                return ObserveResult(
                    actions=actions,
                    description=data.get("description", ""),
                )
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

        return ObserveResult(actions=[], description="Failed to parse observation")
