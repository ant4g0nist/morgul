# Configuration

Morgul can be configured through a TOML file, environment variables, or programmatically in Python.

## How Morgul loads config

By default, Morgul reads `morgul.toml` from the current working directory. You can override this in two ways:

- Pass a path directly: `Morgul(config_path="path/to/morgul.toml")`
- Pass a config object: `Morgul(config=my_config)`

## Full annotated morgul.toml

```toml
[llm]
provider = "anthropic"           # "anthropic", "openai", or "ollama"
model = "claude-sonnet-4-5-20250929"
api_key = ""                     # Or set ANTHROPIC_API_KEY / OPENAI_API_KEY env var
base_url = ""                    # Custom endpoint (for Ollama: "http://localhost:11434")
temperature = 0.7
max_tokens = 4096

[cache]
enabled = true
directory = ".morgul/cache"

[healing]
enabled = true
max_retries = 3

[agent]
max_steps = 50
timeout = 300.0
strategy = "depth-first"         # "depth-first", "breadth-first", "hypothesis-driven"
```

## Environment variables

Morgul auto-detects the following environment variables:

| Variable           | Description                        |
| ------------------ | ---------------------------------- |
| `ANTHROPIC_API_KEY`| API key for Anthropic (Claude)     |
| `OPENAI_API_KEY`   | API key for OpenAI (GPT models)    |

When an environment variable is set, you do not need to specify `api_key` in the TOML file. If both are present, the TOML value takes precedence.

## Programmatic config

You can build the configuration entirely in Python:

```python
from morgul.core import Morgul
from morgul.core.types.config import MorgulConfig, LLMConfig

config = MorgulConfig(
    llm=LLMConfig(provider="openai", model="gpt-4o"),
    verbose=True,
)
morgul = Morgul(config=config)
```

## Top-level options

These options can be set at the root level of `MorgulConfig` or directly in `morgul.toml`:

| Option      | Type   | Default | Description                                      |
| ----------- | ------ | ------- | ------------------------------------------------ |
| `verbose`   | `bool` | `False` | Enable verbose logging output                    |
| `self_heal` | `bool` | `True`  | Automatically retry and repair failed operations |

## Further reading

See the [Configuration Reference](../reference/config.md) for a complete list of every option and its behavior.
