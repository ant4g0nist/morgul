"""ExtractHandler — structured data extraction from process state."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel

from morgul.core.context.builder import ContextBuilder
from morgul.core.translate.engine import TranslateEngine

if TYPE_CHECKING:
    from morgul.bridge.process import Process
    from morgul.llm import LLMClient

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ExtractHandler:
    """Extracts structured data from process state using an LLM.

    Pipeline:
    1. Build process context
    2. Send context + instruction + Pydantic schema to LLM
    3. LLM returns structured data matching schema
    4. Validate with Pydantic, return typed result
    """

    def __init__(self, llm_client: LLMClient, cache=None):
        self.translate_engine = TranslateEngine(llm_client, cache=cache)
        self.context_builder = ContextBuilder()

    async def extract(
        self,
        instruction: str,
        process: Process,
        response_model: type[T],
    ) -> T:
        """Extract structured data from the current process state.

        Args:
            instruction: Natural language description of what to extract.
            process: The debugger process to extract from.
            response_model: Pydantic model class defining the output schema.

        Returns:
            An instance of response_model populated with extracted data.
        """
        snapshot = self.context_builder.build(process)
        context_text = self.context_builder.format_for_prompt(snapshot)

        result = await self.translate_engine.translate_extract(
            instruction=instruction,
            context_text=context_text,
            response_model=response_model,
        )

        return result
