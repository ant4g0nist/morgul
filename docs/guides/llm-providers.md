# Guide: LLM Providers

## Overview

Morgul supports three LLM providers. Choose based on your requirements for reasoning quality, cost, speed, and network access.

## Anthropic (Claude)

```toml
[llm]
provider = "anthropic"
model = "claude-sonnet-4-5-20250929"
```

Set the `ANTHROPIC_API_KEY` environment variable or provide `api_key` in the config.

Best for: complex reasoning tasks, detailed analysis, and cases where you need the LLM to maintain long chains of reasoning about binary behavior.

## OpenAI (GPT-4)

```toml
[llm]
provider = "openai"
model = "gpt-4o"
```

Set the `OPENAI_API_KEY` environment variable or provide `api_key` in the config.

Best for: general-purpose debugging tasks.

## Ollama (Local)

```toml
[llm]
provider = "ollama"
model = "llama3"
base_url = "http://localhost:11434"
```

No API key needed. Install Ollama and pull a model first (`ollama pull llama3`).

Best for: air-gapped environments, sensitive targets where data cannot leave the machine, and cost-free experimentation during development.

## Comparison

| Provider  | Setup         | Cost      | Speed  | Air-gapped |
|-----------|---------------|-----------|--------|------------|
| Anthropic | API key       | Per-token | Fast   | No         |
| OpenAI    | API key       | Per-token | Fast   | No         |
| Ollama    | Local install | Free      | Varies | Yes        |

## Programmatic Selection

You can select the provider and model in code instead of using a config file:

```python
from morgul.core import Morgul
from morgul.core.types.config import MorgulConfig, LLMConfig

config = MorgulConfig(llm=LLMConfig(
    provider="ollama",
    model="deepseek-r1",
    base_url="http://localhost:11434",
))
morgul = Morgul(config=config)
```

Note: The `LLMConfig` field for the model name is `model`, not `model_name`. This applies both to the TOML config and the programmatic API.
