from __future__ import annotations

from .client import LLMClient, create_llm_client
from .agentic import AgenticClient, AgenticEvent, AgenticResult, ToolExecutor, create_agentic_client
from .events import InstrumentedLLMClient, LLMEvent, LLMEventCallback
from .types import ChatMessage, LLMResponse, ModelConfig, ToolCall, ToolDefinition, ToolResult, Usage

# Lazy imports for provider clients to avoid requiring all SDKs
def __getattr__(name: str):  # noqa: N807
    if name == "AnthropicClient":
        from .anthropic import AnthropicClient
        return AnthropicClient
    if name == "OpenAIClient":
        from .openai import OpenAIClient
        return OpenAIClient
    if name == "OllamaClient":
        from .ollama import OllamaClient
        return OllamaClient
    if name == "ClaudeAgentClient":
        from .claude_agent import ClaudeAgentClient
        return ClaudeAgentClient
    if name == "CodexClient":
        from .codex_agent import CodexClient
        return CodexClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "LLMClient",
    "AnthropicClient",
    "OpenAIClient",
    "OllamaClient",
    "create_llm_client",
    # Agentic backends
    "AgenticClient",
    "AgenticEvent",
    "AgenticResult",
    "ToolExecutor",
    "create_agentic_client",
    "ClaudeAgentClient",
    "CodexClient",
    # Events / observability
    "InstrumentedLLMClient",
    "LLMEvent",
    "LLMEventCallback",
    # Types
    "ChatMessage",
    "LLMResponse",
    "ModelConfig",
    "ToolCall",
    "ToolDefinition",
    "ToolResult",
    "Usage",
]
