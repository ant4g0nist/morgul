# Configuration Reference

Morgul is configured through a `morgul.toml` file or by passing a `MorgulConfig` object directly to the constructor. This page documents every available configuration key.

---

## Config Loading Precedence

Configuration is resolved in the following order (highest priority first):

1. **Explicit `MorgulConfig` object** passed to the `Morgul()` constructor.
2. **`config_path` parameter** pointing to a specific TOML file.
3. **`morgul.toml`** in the current working directory.
4. **Default values** as documented below.

---

## Top-Level Keys

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `verbose` | bool | `false` | Enable verbose debug logging. When enabled, Morgul logs detailed information about LLM requests, command translation, and execution. |
| `self_heal` | bool | `true` | Enable self-healing on command failures. When a translated LLDB command fails, Morgul sends the error back to the LLM to generate a corrected command. |
| `visible` | bool | `false` | **Deprecated.** Alias for `dashboard_port = 8546`. Kept for backward compatibility. |
| `dashboard_port` | int | `null` | When set, starts a web dashboard on the given port. Opens a browser to `http://127.0.0.1:<port>` showing a split-pane view with LLDB execution on the left and AI reasoning on the right. Events are streamed via SSE. If `visible = true` and `dashboard_port` is not set, defaults to `8546`. |

---

## `[llm]` Section

Controls which LLM provider and model Morgul uses for natural-language understanding and command translation.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `provider` | string | `"anthropic"` | LLM provider. Supported values: `"anthropic"`, `"openai"`, `"ollama"`. |
| `model` | string | `"claude-sonnet-4-20250514"` | Model name or identifier to use. Must be a valid model for the chosen provider. |
| `api_key` | string | `null` | API key for authentication. If not set, Morgul reads from the `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` environment variable depending on the provider. |
| `base_url` | string | `null` | Custom API endpoint URL. Required for Ollama (typically `http://localhost:11434`). Optional for other providers. |
| `temperature` | float | `0.7` | Sampling temperature for LLM responses. Lower values produce more deterministic output; higher values increase creativity. |
| `max_tokens` | int | `4096` | Maximum number of tokens the LLM may generate in a single response. |

**Example:**

```toml
[llm]
provider = "anthropic"
model = "claude-sonnet-4-20250514"
temperature = 0.5
max_tokens = 4096
```

---

## `[cache]` Section

Controls the content-addressed cache that stores LLM responses to avoid redundant API calls.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Enable or disable caching. When enabled, identical queries return cached results without making an LLM call. |
| `directory` | string | `".morgul/cache"` | Path to the directory where cache files are stored. Relative paths are resolved from the current working directory. |

**Example:**

```toml
[cache]
enabled = true
directory = ".morgul/cache"
```

---

## `[healing]` Section

Controls the self-healing system that automatically retries failed commands with LLM-corrected alternatives.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Enable the self-healing subsystem. Must be `true` along with the top-level `self_heal` key for healing to function. |
| `max_retries` | int | `3` | Maximum number of times the LLM is asked to correct a failed command before giving up. |

**Example:**

```toml
[healing]
enabled = true
max_retries = 3
```

---

## `[agent]` Section

Controls the autonomous agent loop used by `Morgul.agent()`.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `max_steps` | int | `50` | Maximum number of iterations the agent will perform before stopping. Each step consists of an action and an observation. |
| `timeout` | float | `300.0` | Maximum total runtime for the agent in seconds. The agent stops if this limit is reached, regardless of progress. |
| `strategy` | string | `"depth-first"` | Default agent strategy. Supported values: `"depth-first"` (follows one line of investigation), `"breadth-first"` (explores multiple avenues), `"hypothesis-driven"` (forms and tests hypotheses). |

**Example:**

```toml
[agent]
max_steps = 30
timeout = 120.0
strategy = "hypothesis-driven"
```

---

## Full Example

A complete `morgul.toml` with all sections:

```toml
verbose = false
self_heal = true
dashboard_port = 8546  # open web dashboard on port 8546

[llm]
provider = "anthropic"
model = "claude-sonnet-4-20250514"
temperature = 0.5
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
strategy = "depth-first"
```
