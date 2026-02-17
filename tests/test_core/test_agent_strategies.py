"""Tests for AgentStrategy enum and helpers."""

from __future__ import annotations

from morgul.core.agent.strategies import AgentStrategy, get_strategy_description


class TestAgentStrategy:
    def test_enum_values(self):
        assert AgentStrategy.DEPTH_FIRST.value == "depth-first"
        assert AgentStrategy.BREADTH_FIRST.value == "breadth-first"
        assert AgentStrategy.HYPOTHESIS_DRIVEN.value == "hypothesis-driven"

    def test_enum_from_string(self):
        assert AgentStrategy("depth-first") == AgentStrategy.DEPTH_FIRST

    def test_get_strategy_description(self):
        desc = get_strategy_description(AgentStrategy.DEPTH_FIRST)
        assert "deeply" in desc.lower() or "deep" in desc.lower()

    def test_get_strategy_description_all(self):
        for strategy in AgentStrategy:
            desc = get_strategy_description(strategy)
            assert isinstance(desc, str)
            assert len(desc) > 10
