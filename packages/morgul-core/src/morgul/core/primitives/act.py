"""ActHandler — NL → Python code execution via bridge API."""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING, Optional

from morgul.core.context.builder import ContextBuilder
from morgul.core.events import (
    ExecutionEvent,
    ExecutionEventCallback,
    ExecutionEventType,
)
from morgul.core.primitives.executor import PythonExecutor
from morgul.core.translate.engine import TranslateEngine
from morgul.core.types.actions import ActResult

if TYPE_CHECKING:
    from morgul.bridge import Debugger
    from morgul.bridge.process import Process
    from morgul.bridge.target import Target
    from morgul.core.cache import ContentCache
    from morgul.llm import LLMClient

logger = logging.getLogger(__name__)


class ActHandler:
    """Translates natural language instructions into Python code and executes them.

    Pipeline:
    1. Build process context via context builder
    2. Translate instruction → Python code via translate engine
    3. Execute code via PythonExecutor (persistent namespace with bridge objects)
    4. Return ActResult with success/failure + output
    5. On failure + self_heal enabled: feed traceback to LLM, retry
    """

    def __init__(
        self,
        llm_client: LLMClient,
        debugger: Debugger,
        target: Target,
        process: Process,
        self_heal: bool = True,
        max_retries: int = 3,
        execution_callback: Optional[ExecutionEventCallback] = None,
        cache: ContentCache | None = None,
    ):
        self.translate_engine = TranslateEngine(llm_client)
        self.context_builder = ContextBuilder()
        self.executor = PythonExecutor(
            debugger, target, process,
            execution_callback=execution_callback,
        )
        self._execution_callback = execution_callback
        self._cache = cache
        self.self_heal = self_heal
        self.max_retries = max_retries

    def _get_code(self, response) -> str:
        """Extract executable code from a TranslateResponse.

        Prefers the top-level ``code`` field; falls back to joining
        ``code`` (or ``command``) from individual actions.
        """
        if response.code:
            return response.code
        parts = []
        for action in response.actions:
            if action.code:
                parts.append(action.code)
            elif action.command:
                # Legacy fallback — wrap CLI command in execute_command
                parts.append(
                    f"print(debugger.execute_command({action.command!r}).output)"
                )
        return "\n".join(parts)

    def _cache_key(self, instruction: str, context_text: str) -> str:
        """Build a deterministic cache key for an act() call."""
        blob = f"{instruction}\n{context_text}\nact".encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    async def act(self, instruction: str, process: Process) -> ActResult:
        """Execute a natural language debugging instruction."""
        snapshot = self.context_builder.build(process)
        context_text = self.context_builder.format_for_prompt(snapshot)

        # Check cache for a previously successful result
        if self._cache is not None:
            key = self._cache_key(instruction, context_text)
            cached = self._cache.get_by_key(key)
            if cached is not None:
                logger.info("Cache hit: %s", key)
                return ActResult.model_validate(cached)

        response = await self.translate_engine.translate(
            instruction=instruction,
            context=snapshot,
            context_text=context_text,
        )

        if self._execution_callback is not None and response.reasoning:
            self._execution_callback(ExecutionEvent(
                event_type=ExecutionEventType.LLM_RESPONSE,
                metadata={"content": response.reasoning},
            ))

        code = self._get_code(response)
        if not code:
            return ActResult(
                success=False,
                message="No code generated from instruction",
                actions=response.actions,
                output="",
            )

        # Execute the code
        stdout, stderr, succeeded = self.executor.execute(code)
        output = stdout
        if stderr:
            output = f"{stdout}\n{stderr}".strip() if stdout else stderr

        if not succeeded and self.self_heal:
            healed = await self._try_heal(
                instruction, process, code, stderr
            )
            if healed is not None:
                # Cache the healed result so next time we skip the whole cycle
                if self._cache is not None:
                    self._cache.set_by_key(key, healed.model_dump())
                return healed

        result = ActResult(
            success=succeeded,
            message=response.reasoning,
            actions=response.actions,
            output=output,
        )

        # Only cache successful results
        if succeeded and self._cache is not None:
            self._cache.set_by_key(key, result.model_dump())

        return result

    async def _try_heal(
        self,
        original_instruction: str,
        process: Process,
        failed_code: str,
        error: str,
    ) -> ActResult | None:
        """Attempt self-healing after a code execution failure."""
        for attempt in range(self.max_retries):
            logger.info("Self-heal attempt %d/%d", attempt + 1, self.max_retries)

            if self._execution_callback is not None:
                self._execution_callback(ExecutionEvent(
                    event_type=ExecutionEventType.HEAL_START,
                    code=failed_code,
                    stderr=error,
                    metadata={
                        "attempt": attempt + 1,
                        "max_retries": self.max_retries,
                    },
                ))

            # Re-snapshot with current state
            snapshot = self.context_builder.build(process)
            context_text = self.context_builder.format_for_prompt(snapshot)

            # Add error context to instruction
            heal_instruction = (
                f"{original_instruction}\n\n"
                f"Previous attempt failed:\n"
                f"  Code:\n{failed_code}\n"
                f"  Error:\n{error}\n"
                f"Please try an alternative approach."
            )

            response = await self.translate_engine.translate(
                instruction=heal_instruction,
                context=snapshot,
                context_text=context_text,
            )

            code = self._get_code(response)
            if not code:
                continue

            stdout, stderr, succeeded = self.executor.execute(code)

            if self._execution_callback is not None:
                self._execution_callback(ExecutionEvent(
                    event_type=ExecutionEventType.HEAL_END,
                    code=code,
                    stdout=stdout,
                    stderr=stderr,
                    succeeded=succeeded,
                    metadata={"attempt": attempt + 1},
                ))

            if succeeded:
                output = stdout
                if stderr:
                    output = f"{stdout}\n{stderr}".strip() if stdout else stderr
                return ActResult(
                    success=True,
                    message=f"Healed on attempt {attempt + 1}: {response.reasoning}",
                    actions=response.actions,
                    output=output,
                )
            error = stderr
            failed_code = code

        return None
