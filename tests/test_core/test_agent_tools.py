"""Tests for AGENT_TOOLS definitions."""

from __future__ import annotations

from morgul.core.agent.tools import AGENT_TOOLS
from morgul.llm.types import ToolDefinition


class TestAgentTools:
    def test_tools_is_list(self):
        assert isinstance(AGENT_TOOLS, list)

    def test_all_are_tool_definitions(self):
        for tool in AGENT_TOOLS:
            assert isinstance(tool, ToolDefinition)

    def test_expected_tool_names(self):
        names = {t.name for t in AGENT_TOOLS}
        expected = {"act", "set_breakpoint", "read_memory", "step", "continue_execution", "evaluate", "done"}
        assert names == expected

    def test_all_have_descriptions(self):
        for tool in AGENT_TOOLS:
            assert tool.description
            assert len(tool.description) > 5

    def test_all_have_parameters(self):
        for tool in AGENT_TOOLS:
            assert isinstance(tool.parameters, dict)
            assert tool.parameters.get("type") == "object"

    def test_required_params(self):
        """Tools with required params should list them."""
        act_tool = next(t for t in AGENT_TOOLS if t.name == "act")
        assert "required" in act_tool.parameters
        assert "instruction" in act_tool.parameters["required"]

        done_tool = next(t for t in AGENT_TOOLS if t.name == "done")
        assert "required" in done_tool.parameters
        assert "result" in done_tool.parameters["required"]
