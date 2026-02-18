"""Execution event system for observable debugging operations."""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Callable, Dict, Optional


class ExecutionEventType(Enum):
    """Types of execution events emitted during debugging operations."""

    CODE_START = "code_start"
    CODE_END = "code_end"
    HEAL_START = "heal_start"
    HEAL_END = "heal_end"
    REPL_STEP = "repl_step"
    LLM_RESPONSE = "llm_response"
    CACHE_HIT = "cache_hit"
    LLM_SUB_QUERY = "llm_sub_query"


class ExecutionEvent:
    """Lightweight event emitted around code execution and healing operations."""

    __slots__ = (
        "event_type",
        "code",
        "stdout",
        "stderr",
        "succeeded",
        "duration",
        "metadata",
    )

    def __init__(
        self,
        event_type: ExecutionEventType,
        code: str = "",
        stdout: str = "",
        stderr: str = "",
        succeeded: Optional[bool] = None,
        duration: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.event_type = event_type
        self.code = code
        self.stdout = stdout
        self.stderr = stderr
        self.succeeded = succeeded
        self.duration = duration
        self.metadata = metadata or {}


ExecutionEventCallback = Callable[[ExecutionEvent], None]
