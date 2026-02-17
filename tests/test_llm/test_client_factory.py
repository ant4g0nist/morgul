"""Tests for create_llm_client factory."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from morgul.llm.client import create_llm_client
from morgul.llm.types import ModelConfig


def _mock_sdk(name):
    """Insert a mock SDK into sys.modules so import <name> succeeds."""
    mock = MagicMock()
    return mock


class TestCreateLLMClient:
    def test_anthropic_provider(self, anthropic_config):
        mock_sdk = MagicMock()
        with patch.dict(sys.modules, {"anthropic": mock_sdk}):
            client = create_llm_client(anthropic_config)
        assert client.__class__.__name__ == "AnthropicClient"

    def test_openai_provider(self, openai_config):
        mock_sdk = MagicMock()
        with patch.dict(sys.modules, {"openai": mock_sdk}):
            client = create_llm_client(openai_config)
        assert client.__class__.__name__ == "OpenAIClient"

    def test_ollama_provider(self, ollama_config):
        mock_sdk = MagicMock()
        with patch.dict(sys.modules, {"ollama": mock_sdk}):
            client = create_llm_client(ollama_config)
        assert client.__class__.__name__ == "OllamaClient"

    def test_unsupported_provider(self):
        config = ModelConfig(provider="anthropic", model_name="test")
        # Monkey-patch to test the ValueError path
        object.__setattr__(config, "provider", "unsupported")
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            create_llm_client(config)

    def test_anthropic_import_error(self, anthropic_config):
        with patch.dict(sys.modules, {"anthropic": None}):
            with pytest.raises((ImportError, ModuleNotFoundError)):
                create_llm_client(anthropic_config)
