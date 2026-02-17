"""Tests for TOML config file loading and MorgulConfig construction."""

from __future__ import annotations

import pytest

from morgul.core.types.config import (
    AgentConfig,
    CacheConfig,
    HealingConfig,
    LLMConfig,
    MorgulConfig,
    load_config,
)


class TestLoadConfig:
    def test_nonexistent_file_returns_defaults(self):
        config = load_config("/nonexistent/path/morgul.toml")
        assert config.llm.provider == "anthropic"
        assert config.llm.model == "claude-sonnet-4-20250514"

    def test_none_path_returns_defaults(self):
        config = load_config(None)
        assert isinstance(config, MorgulConfig)

    def test_load_full_toml(self, tmp_path):
        toml_file = tmp_path / "morgul.toml"
        # Note: verbose/self_heal must NOT appear under [agent] — they are
        # top-level keys in MorgulConfig.  Place them before the first section
        # or after the last section but with no table header.
        toml_file.write_text(
            'verbose = true\n'
            'self_heal = false\n'
            '\n'
            '[llm]\n'
            'provider = "openai"\n'
            'model = "gpt-4o"\n'
            'temperature = 0.5\n'
            'max_tokens = 2048\n'
            '\n'
            '[cache]\n'
            'enabled = false\n'
            'directory = "/tmp/cache"\n'
            '\n'
            '[healing]\n'
            'enabled = false\n'
            'max_retries = 5\n'
            '\n'
            '[agent]\n'
            'max_steps = 100\n'
            'timeout = 600.0\n'
            'strategy = "breadth-first"\n'
        )
        config = load_config(str(toml_file))
        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4o"
        assert config.llm.temperature == 0.5
        assert config.llm.max_tokens == 2048
        assert config.cache.enabled is False
        assert config.cache.directory == "/tmp/cache"
        assert config.healing.enabled is False
        assert config.healing.max_retries == 5
        assert config.agent.max_steps == 100
        assert config.agent.timeout == 600.0
        assert config.agent.strategy == "breadth-first"
        assert config.verbose is True
        assert config.self_heal is False

    def test_load_partial_toml(self, tmp_path):
        """Only [llm] section — other sections should use defaults."""
        toml_file = tmp_path / "morgul.toml"
        toml_file.write_text('[llm]\nprovider = "ollama"\nmodel = "llama3"\n')
        config = load_config(str(toml_file))
        assert config.llm.provider == "ollama"
        assert config.llm.model == "llama3"
        # defaults preserved
        assert config.cache.enabled is True
        assert config.healing.max_retries == 3
        assert config.agent.max_steps == 50

    def test_load_empty_toml(self, tmp_path):
        """Empty file should produce defaults."""
        toml_file = tmp_path / "morgul.toml"
        toml_file.write_text("")
        config = load_config(str(toml_file))
        assert config.llm.provider == "anthropic"

    def test_load_with_base_url(self, tmp_path):
        toml_file = tmp_path / "morgul.toml"
        toml_file.write_text(
            '[llm]\n'
            'provider = "ollama"\n'
            'model = "deepseek-r1"\n'
            'base_url = "http://localhost:11434"\n'
        )
        config = load_config(str(toml_file))
        assert config.llm.base_url == "http://localhost:11434"


class TestMorgulConfigConstruction:
    def test_defaults(self):
        config = MorgulConfig()
        assert config.llm.provider == "anthropic"
        assert config.llm.api_key is None
        assert config.llm.base_url is None
        assert config.cache.enabled is True
        assert config.healing.enabled is True
        assert config.agent.strategy == "depth-first"
        assert config.verbose is False
        assert config.self_heal is True

    def test_custom_llm(self):
        config = MorgulConfig(llm=LLMConfig(provider="openai", model="gpt-4o"))
        assert config.llm.provider == "openai"

    def test_strategy_field_name(self):
        """Verify the field is 'strategy', not 'default_strategy'."""
        config = AgentConfig(strategy="hypothesis-driven")
        assert config.strategy == "hypothesis-driven"

    def test_extra_fields_are_ignored(self):
        """Pydantic by default ignores extra fields — 'default_strategy' won't error
        but also won't set 'strategy'."""
        config = AgentConfig(default_strategy="hypothesis-driven")  # type: ignore[call-arg]
        # The actual 'strategy' field retains its default
        assert config.strategy == "depth-first"
