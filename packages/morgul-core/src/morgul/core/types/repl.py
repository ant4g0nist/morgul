"""Types for the REPL agent."""

from __future__ import annotations

from typing import Dict

from pydantic import BaseModel


class REPLResult(BaseModel):
    """Result of an RLM-style REPL agent run."""

    result: str
    """The DONE() message or final output."""

    steps: int
    """Number of iterations the agent ran."""

    code_blocks_executed: int
    """Total number of Python code blocks executed."""

    variables: Dict[str, str] = {}
    """Key variables from the namespace (stringified)."""
