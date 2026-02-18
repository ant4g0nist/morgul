"""Types for the REPL agent."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class REPLCodeBlock(BaseModel):
    """Telemetry for a single executed code block."""

    code: str
    stdout: str = ""
    stderr: str = ""
    succeeded: bool = True
    duration: float = 0.0
    llm_sub_queries: int = 0


class REPLIteration(BaseModel):
    """Telemetry for one REPL iteration (LLM response + code executions)."""

    step_number: int
    llm_response: str = ""
    code_blocks: List[REPLCodeBlock] = Field(default_factory=list)
    duration: float = 0.0


class REPLResult(BaseModel):
    """Result of an RLM REPL agent run."""

    result: str
    """The DONE() message or final output."""

    steps: int
    """Number of iterations the agent ran."""

    code_blocks_executed: int
    """Total number of Python code blocks executed."""

    variables: Dict[str, str] = Field(default_factory=dict)
    """Key variables from the namespace (stringified)."""

    iterations: List[REPLIteration] = Field(default_factory=list)
    """Per-iteration telemetry."""

    final_var: Optional[Any] = None
    """Structured result from FINAL_VAR(), if used."""

    model_config = {"arbitrary_types_allowed": True}
