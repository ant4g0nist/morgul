# Types Reference

This page documents all public Pydantic models and enums used across Morgul.

---

## Action Types

```python
from morgul.core.types.actions import Action, ActResult, ObserveResult, ExtractResult
```

### `Action`

Represents a single debugging action to be executed.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `code` | `str` | `""` | Python code to execute via the bridge API. |
| `command` | `str` | `""` | Legacy LLDB CLI command (kept for backward compatibility). |
| `description` | `str` | *(required)* | Human-readable description of what the action does. |
| `args` | `Dict[str, Any]` | `{}` | Additional arguments or metadata. |

### `ActResult`

Returned by `Morgul.act()`. Contains the outcome of executing a natural-language instruction.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `success` | `bool` | *(required)* | Whether the code executed successfully. |
| `message` | `str` | *(required)* | Summary message describing the outcome. |
| `actions` | `List[Action]` | *(required)* | The list of actions that were generated. |
| `output` | `str` | `""` | Captured stdout/stderr from code execution. |

### `ObserveResult`

Returned by `Morgul.observe()`. Contains a snapshot of the current debugger state.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `actions` | `List[Action]` | *(required)* | Ranked list of suggested next debugging actions. |
| `description` | `str` | *(required)* | Natural-language summary of the observed debugger state. |

### `ExtractResult[T]`

Returned internally by the extraction pipeline. Wraps structured data extracted from debugger state.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `data` | `T` | *(required)* | The extracted data, conforming to the provided response model. |
| `raw_response` | `str` | `""` | The raw LLM response before parsing. |

---

## Context Types

```python
from morgul.core.types.context import (
    RegisterInfo, FrameInfo, StackTrace,
    MemoryRegionInfo, ModuleDetail, ProcessSnapshot
)
```

### `RegisterInfo`

Represents a single CPU register and its current value.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | *(required)* | Register name (e.g., `"rax"`, `"x0"`). |
| `value` | `int` | *(required)* | Current register value as an integer. |
| `size` | `int` | `8` | Register size in bytes. |

### `FrameInfo`

Represents a single frame in a stack trace.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `index` | `int` | *(required)* | Frame index (0 is the innermost frame). |
| `function_name` | `Optional[str]` | `None` | Name of the function, if available. |
| `module_name` | `Optional[str]` | `None` | Name of the module containing this frame. |
| `pc` | `int` | *(required)* | Program counter value for this frame. |
| `file` | `Optional[str]` | `None` | Source file path, if debug info is available. |
| `line` | `Optional[int]` | `None` | Source line number, if debug info is available. |

### `StackTrace`

Represents a complete stack trace for a thread.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `frames` | `List[FrameInfo]` | *(required)* | Ordered list of stack frames. |
| `thread_id` | `int` | *(required)* | The thread ID this stack trace belongs to. |
| `thread_name` | `Optional[str]` | `None` | The thread name, if set. |

### `MemoryRegionInfo`

Describes a region of process memory and its permissions.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `start` | `int` | *(required)* | Start address of the memory region. |
| `end` | `int` | *(required)* | End address of the memory region. |
| `readable` | `bool` | *(required)* | Whether the region is readable. |
| `writable` | `bool` | *(required)* | Whether the region is writable. |
| `executable` | `bool` | *(required)* | Whether the region is executable. |
| `name` | `Optional[str]` | `None` | Name or label for the region (e.g., mapped file path). |

### `ModuleDetail`

Information about a loaded module (shared library or executable).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | *(required)* | Module file name. |
| `path` | `str` | *(required)* | Full path to the module on disk. |
| `uuid` | `Optional[str]` | `None` | UUID of the module binary, if available. |
| `base_address` | `int` | *(required)* | Base load address in the process address space. |

### `ProcessSnapshot`

A comprehensive snapshot of the debugged process state. Returned internally and used to build context for LLM queries.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `registers` | `List[RegisterInfo]` | *(required)* | Current register values. |
| `stack_trace` | `Optional[StackTrace]` | `None` | Stack trace for the current thread. |
| `memory_regions` | `List[MemoryRegionInfo]` | `[]` | Memory region mappings. |
| `modules` | `List[ModuleDetail]` | `[]` | Loaded modules. |
| `disassembly` | `str` | `""` | Disassembly around the current program counter. |
| `variables` | `List[Dict[str, Any]]` | `[]` | Local and argument variables in the current frame. |
| `process_state` | `str` | `""` | Current process state (e.g., `"stopped"`, `"running"`). |
| `stop_reason` | `str` | `""` | Reason the process stopped (e.g., `"breakpoint"`, `"signal"`). |
| `pc` | `Optional[int]` | `None` | Current program counter value. |

---

## LLM Types

```python
from morgul.core.types.llm import AgentStep, TranslateResponse
```

### `AgentStep`

Represents a single step in an autonomous agent loop. A list of these is returned by `Morgul.agent()`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `step_number` | `int` | *(required)* | Sequential step index (starting from 1). |
| `action` | `str` | *(required)* | Description of the action taken in this step. |
| `observation` | `str` | *(required)* | The result or output observed after executing the action. |
| `reasoning` | `str` | `""` | The agent's reasoning for choosing this action. |

### `TranslateResponse`

Internal type returned by the LLM translation layer when converting natural-language instructions to Python code or actions.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `actions` | `List[Action]` | `[]` | List of individual actions (for multi-step responses). |
| `code` | `str` | `""` | Single Python code block (alternative to actions list). |
| `reasoning` | `str` | `""` | The LLM's explanation of why this approach was chosen. |

---

## Config Types

```python
from morgul.core.types.config import (
    LLMConfig, CacheConfig, HealingConfig,
    AgentConfig, MorgulConfig
)
```

### `LLMConfig`

Configuration for the LLM provider.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `provider` | `str` | `"anthropic"` | LLM provider identifier: `"anthropic"`, `"openai"`, or `"ollama"`. |
| `model` | `str` | `"claude-sonnet-4-20250514"` | Model name or identifier. |
| `api_key` | `Optional[str]` | `None` | API key. If not set, the corresponding environment variable is used. |
| `base_url` | `Optional[str]` | `None` | Custom API endpoint URL. Required for Ollama. |
| `temperature` | `float` | `0.7` | Sampling temperature for LLM responses. |
| `max_tokens` | `int` | `4096` | Maximum number of tokens in LLM responses. |

### `CacheConfig`

Configuration for the content-addressed cache.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `True` | Whether caching is enabled. |
| `directory` | `str` | `".morgul/cache"` | Path to the cache storage directory. |

### `HealingConfig`

Configuration for the self-healing system.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `True` | Whether self-healing is enabled. |
| `max_retries` | `int` | `3` | Maximum number of retry attempts for a failed command. |

### `AgentConfig`

Configuration for the autonomous agent loop.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_steps` | `int` | `50` | Maximum number of iterations the agent will perform. |
| `timeout` | `float` | `300.0` | Maximum runtime for the agent in seconds. |
| `strategy` | `str` | `"depth-first"` | Default agent strategy: `"depth-first"`, `"breadth-first"`, or `"hypothesis-driven"`. |

### `MorgulConfig`

Top-level configuration object that aggregates all sub-configurations.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `llm` | `LLMConfig` | `LLMConfig()` | LLM provider configuration. |
| `cache` | `CacheConfig` | `CacheConfig()` | Cache configuration. |
| `healing` | `HealingConfig` | `HealingConfig()` | Self-healing configuration. |
| `agent` | `AgentConfig` | `AgentConfig()` | Agent loop configuration. |
| `verbose` | `bool` | `False` | Enable verbose debug logging. |
| `self_heal` | `bool` | `True` | Enable self-healing on command failures. |
