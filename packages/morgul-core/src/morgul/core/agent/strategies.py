"""Agent strategies for autonomous debugging."""

from __future__ import annotations

from enum import Enum

from morgul.core.translate.prompts import STRATEGY_DESCRIPTIONS


class AgentStrategy(str, Enum):
    DEPTH_FIRST = "depth-first"
    BREADTH_FIRST = "breadth-first"
    HYPOTHESIS_DRIVEN = "hypothesis-driven"


def get_strategy_description(strategy: AgentStrategy) -> str:
    """Get the description for a given strategy."""
    return STRATEGY_DESCRIPTIONS.get(strategy.value, STRATEGY_DESCRIPTIONS["depth-first"])
