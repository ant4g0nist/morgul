"""Per-iteration telemetry logger for the REPL agent."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

from morgul.core.types.repl import REPLCodeBlock, REPLIteration

logger = logging.getLogger(__name__)


class REPLLogger:
    """Tracks per-iteration and per-code-block telemetry for a REPL session.

    Optionally writes each iteration as a JSONL line to *log_path*.
    """

    def __init__(self, log_path: Optional[Path] = None):
        self._log_path = log_path
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
        self._iterations: list[REPLIteration] = []
        self._current_step: Optional[int] = None
        self._current_llm_response: str = ""
        self._current_code_blocks: list[REPLCodeBlock] = []
        self._iteration_t0: float = 0.0
        self._block_t0: float = 0.0

    @property
    def iterations(self) -> list[REPLIteration]:
        return list(self._iterations)

    def begin_iteration(self, step_number: int, llm_response: str = "") -> None:
        """Start tracking a new iteration."""
        self._current_step = step_number
        self._current_llm_response = llm_response
        self._current_code_blocks = []
        self._iteration_t0 = time.monotonic()

    def begin_code_block(self) -> None:
        """Mark the start of a code block execution."""
        self._block_t0 = time.monotonic()

    def end_code_block(
        self,
        code: str,
        stdout: str = "",
        stderr: str = "",
        succeeded: bool = True,
        llm_sub_queries: int = 0,
    ) -> None:
        """Record a completed code block."""
        duration = time.monotonic() - self._block_t0
        self._current_code_blocks.append(REPLCodeBlock(
            code=code,
            stdout=stdout,
            stderr=stderr,
            succeeded=succeeded,
            duration=duration,
            llm_sub_queries=llm_sub_queries,
        ))

    def end_iteration(self) -> REPLIteration:
        """Finalize the current iteration and return its model."""
        duration = time.monotonic() - self._iteration_t0
        iteration = REPLIteration(
            step_number=self._current_step or 0,
            llm_response=self._current_llm_response,
            code_blocks=list(self._current_code_blocks),
            duration=duration,
        )
        self._iterations.append(iteration)
        self._write_jsonl(iteration)
        return iteration

    def _write_jsonl(self, iteration: REPLIteration) -> None:
        """Append an iteration record to the JSONL log file, if configured."""
        if self._log_path is None:
            return
        try:
            with open(self._log_path, "a") as f:
                f.write(iteration.model_dump_json() + "\n")
        except Exception:
            logger.warning("Failed to write REPL log entry", exc_info=True)
