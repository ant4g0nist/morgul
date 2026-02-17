"""Tests for prompt templates."""

from __future__ import annotations

from morgul.core.translate.prompts import (
    ACT_PROMPT,
    AGENT_SYSTEM_PROMPT,
    BRIDGE_API_REFERENCE,
    EXTRACT_PROMPT,
    OBSERVE_PROMPT,
    STRATEGY_DESCRIPTIONS,
)


class TestPromptTemplates:
    def test_act_prompt_has_placeholders(self):
        assert "{context}" in ACT_PROMPT
        assert "{instruction}" in ACT_PROMPT

    def test_act_prompt_formats(self):
        result = ACT_PROMPT.format(context="ctx", instruction="do stuff")
        assert "ctx" in result
        assert "do stuff" in result

    def test_act_prompt_references_bridge_api(self):
        assert "bridge API" in ACT_PROMPT.lower() or "Bridge API" in ACT_PROMPT

    def test_act_prompt_asks_for_python_code(self):
        assert "Python" in ACT_PROMPT
        assert '"code"' in ACT_PROMPT

    def test_extract_prompt_has_placeholders(self):
        assert "{context}" in EXTRACT_PROMPT
        assert "{instruction}" in EXTRACT_PROMPT
        assert "{schema}" in EXTRACT_PROMPT

    def test_observe_prompt_has_placeholders(self):
        assert "{context}" in OBSERVE_PROMPT
        assert "{instruction_section}" in OBSERVE_PROMPT

    def test_observe_prompt_references_bridge_api(self):
        assert "bridge API" in OBSERVE_PROMPT.lower() or "Bridge API" in OBSERVE_PROMPT

    def test_agent_system_prompt_has_placeholders(self):
        assert "{strategy}" in AGENT_SYSTEM_PROMPT
        assert "{strategy_description}" in AGENT_SYSTEM_PROMPT
        assert "{task}" in AGENT_SYSTEM_PROMPT
        assert "{max_steps}" in AGENT_SYSTEM_PROMPT

    def test_agent_system_prompt_formats(self):
        result = AGENT_SYSTEM_PROMPT.format(
            strategy="depth-first",
            strategy_description="Follow leads deeply",
            task="Find a bug",
            max_steps=10,
        )
        assert "depth-first" in result
        assert "Find a bug" in result

    def test_strategy_descriptions_has_all_keys(self):
        assert "depth-first" in STRATEGY_DESCRIPTIONS
        assert "breadth-first" in STRATEGY_DESCRIPTIONS
        assert "hypothesis-driven" in STRATEGY_DESCRIPTIONS

    def test_bridge_api_reference_has_objects(self):
        assert "process" in BRIDGE_API_REFERENCE
        assert "thread" in BRIDGE_API_REFERENCE
        assert "frame" in BRIDGE_API_REFERENCE
        assert "target" in BRIDGE_API_REFERENCE
        assert "debugger" in BRIDGE_API_REFERENCE

    def test_bridge_api_reference_has_memory_utils(self):
        assert "read_string" in BRIDGE_API_REFERENCE
        assert "read_pointer" in BRIDGE_API_REFERENCE
        assert "read_uint64" in BRIDGE_API_REFERENCE
