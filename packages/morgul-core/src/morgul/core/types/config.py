from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, model_validator


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096


class CacheConfig(BaseModel):
    """Cache configuration."""

    enabled: bool = True
    directory: str = ".morgul/cache"


class HealingConfig(BaseModel):
    """Self-healing configuration."""

    enabled: bool = True
    max_retries: int = 3


class AgentConfig(BaseModel):
    """Agent loop configuration."""

    max_steps: int = 50
    timeout: float = 300.0
    strategy: str = "repl"

    # Optional agentic backend (SDK-managed tool loop).
    # Set to "claude-code" or "codex" to use an agentic backend for agent().
    agentic_provider: Optional[str] = None
    agentic_model: Optional[str] = None
    agentic_api_key: Optional[str] = None
    agentic_cli_path: Optional[str] = None  # path to codex binary


class MorgulConfig(BaseModel):
    """Top-level Morgul configuration."""

    llm: LLMConfig = LLMConfig()
    cache: CacheConfig = CacheConfig()
    healing: HealingConfig = HealingConfig()
    agent: AgentConfig = AgentConfig()
    verbose: bool = False
    visible: bool = False
    self_heal: bool = True
    dashboard_port: Optional[int] = None

    @model_validator(mode="after")
    def _visible_implies_dashboard(self) -> "MorgulConfig":
        """Backward compat: visible=True sets dashboard_port=8546 if not set."""
        if self.visible and self.dashboard_port is None:
            self.dashboard_port = 8546
        return self


def load_config(path: Optional[str] = None) -> MorgulConfig:
    """Load configuration from a morgul.toml file, falling back to defaults.

    Uses ``tomllib`` on Python 3.11+ and ``tomli`` on older versions.
    """

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            # If tomli is not installed and we are on an older Python, just
            # return defaults when no explicit path is given.
            if path is None:
                return MorgulConfig()
            raise

    config_path = Path(path) if path else Path("morgul.toml")

    if not config_path.exists():
        return MorgulConfig()

    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    return MorgulConfig(**raw)
