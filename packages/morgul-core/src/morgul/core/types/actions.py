from __future__ import annotations

from typing import Any, Dict, Generic, List, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Action(BaseModel):
    """A single debugging action to execute."""

    command: str = ""
    """Legacy LLDB CLI command (kept for backward compatibility)."""

    code: str = ""
    """Python code to execute via bridge API."""

    description: str
    """Human-readable description."""

    args: Dict[str, Any] = {}
    """Additional arguments."""


class ActResult(BaseModel):
    """Result of executing one or more actions."""

    success: bool
    message: str
    actions: List[Action]
    """Commands that were executed."""

    output: str = ""
    """Raw LLDB output."""


class ObserveResult(BaseModel):
    """Result of an observe operation."""

    actions: List[Action]
    """Ranked list of suggested actions."""

    description: str
    """Overall description of observed state."""


class ExtractResult(BaseModel, Generic[T]):
    """Result of a structured extraction."""

    data: T
    raw_response: str = ""
