"""ObserveHandler — survey state, suggest actions."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from morgul.core.context.builder import ContextBuilder
from morgul.core.translate.engine import TranslateEngine
from morgul.core.types.actions import ObserveResult

if TYPE_CHECKING:
    from morgul.bridge.process import Process
    from morgul.llm import LLMClient

logger = logging.getLogger(__name__)


class ObserveHandler:
    """Surveys the current process state and suggests debugging actions.

    Unlike act(), observe() does not execute any commands. It analyzes
    the state and returns a ranked list of suggested actions.
    """

    def __init__(self, llm_client: LLMClient, cache=None):
        self.translate_engine = TranslateEngine(llm_client, cache=cache)
        self.context_builder = ContextBuilder()

    async def observe(
        self,
        process: Process,
        instruction: str | None = None,
    ) -> ObserveResult:
        """Observe the current process state and suggest actions.

        Args:
            process: The debugger process to observe.
            instruction: Optional focus area for the observation.

        Returns:
            ObserveResult with ranked list of suggested actions.
        """
        snapshot = self.context_builder.build(process)
        context_text = self.context_builder.format_for_prompt(snapshot)

        result = await self.translate_engine.translate_observe(
            context_text=context_text,
            instruction=instruction,
        )

        return result
