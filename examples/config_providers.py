"""Switch between LLM providers: Anthropic, OpenAI, and Ollama.

Morgul supports three providers out of the box.  You can configure the
provider via morgul.toml, environment variables, or programmatically.
This example shows the programmatic approach.
"""

from morgul.core import Morgul
from morgul.core.types.config import LLMConfig, MorgulConfig

# --- Provider 1: Anthropic (cloud) ---
# Requires: ANTHROPIC_API_KEY environment variable or api_key below
anthropic_config = MorgulConfig(
    llm=LLMConfig(
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        # api_key="sk-ant-...",  # or set ANTHROPIC_API_KEY
    ),
)

# --- Provider 2: OpenAI (cloud) ---
# Requires: OPENAI_API_KEY environment variable or api_key below
openai_config = MorgulConfig(
    llm=LLMConfig(
        provider="openai",
        model="gpt-4o",
        # api_key="sk-proj-...",  # or set OPENAI_API_KEY
    ),
)

# --- Provider 3: Ollama (local, air-gapped) ---
# Requires: Ollama running locally (ollama serve)
ollama_config = MorgulConfig(
    llm=LLMConfig(
        provider="ollama",
        model="llama3",
        base_url="http://localhost:11434",
    ),
)

# Pick one and run
config = anthropic_config  # Change this to try different providers

with Morgul(config=config) as morgul:
    morgul.start("/tmp/morgul_test")

    result = morgul.act("set a breakpoint on main and continue")
    print(f"Provider: {config.llm.provider}")
    print(f"Model:    {config.llm.model}")
    print(f"Result:   {result.success} — {result.message}")

    obs = morgul.observe()
    print(f"\nState: {obs.description}")
