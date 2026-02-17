from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from morgul.core.types.actions import Action
from morgul.core.types.context import ProcessSnapshot


class TranslateRequest(BaseModel):
    """Request to translate a natural-language instruction into LLDB actions."""

    instruction: str
    context: ProcessSnapshot
    history: List[Dict[str, str]] = []


class TranslateResponse(BaseModel):
    """Response containing translated debugging actions."""

    actions: List[Action] = []
    """List of individual actions (for multi-step responses)."""

    code: str = ""
    """Single code block (alternative to actions list)."""

    reasoning: str = ""


class ExtractRequest(BaseModel):
    """Request to extract structured data from process state."""

    instruction: str
    context: ProcessSnapshot
    output_schema: Dict[str, Any]


class ObserveRequest(BaseModel):
    """Request to observe and analyse process state."""

    instruction: Optional[str] = None
    context: ProcessSnapshot


class AgentStep(BaseModel):
    """A single step in an agent reasoning loop."""

    step_number: int
    action: str
    observation: str
    reasoning: str = ""
