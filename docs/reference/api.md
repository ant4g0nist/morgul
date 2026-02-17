# API Reference

This page documents the public API of the Morgul debugger automation framework.

```python
from morgul.core import Morgul, AsyncMorgul
```

---

## `Morgul` (synchronous)

The primary interface for debugger automation. All methods are synchronous and block until completion.

### Constructor

```python
Morgul(
    config: Optional[MorgulConfig] = None,
    config_path: Optional[str] = None,
    llm_event_callback=None,
    visible: Optional[bool] = None,
    dashboard_port: Optional[int] = None,
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `config` | `Optional[MorgulConfig]` | `None` | A `MorgulConfig` object with all settings. Takes highest precedence. |
| `config_path` | `Optional[str]` | `None` | Path to a `morgul.toml` configuration file. |
| `llm_event_callback` | `Optional[Callable]` | `None` | Callback `(event, is_start)` fired on every LLM request/response. |
| `visible` | `Optional[bool]` | `None` | **Deprecated.** Alias for `dashboard_port=8546`. |
| `dashboard_port` | `Optional[int]` | `None` | Start a web dashboard on this port. Opens a browser with a split-pane LLDB/Chat view. Events stream via SSE. |

Creates a new Morgul instance. If neither `config` nor `config_path` is provided, Morgul looks for `morgul.toml` in the current working directory, then falls back to default values.

Supports use as a context manager:

```python
with Morgul() as m:
    m.start("/path/to/binary")
    result = m.act("set a breakpoint at main")
```

---

### `start`

```python
def start(self, target_path: str, args: Optional[List[str]] = None) -> None
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_path` | `str` | *(required)* | Absolute or relative path to the executable to debug. |
| `args` | `Optional[List[str]]` | `None` | Command-line arguments to pass to the target process. |

**Returns**: `None`

Launches the target executable under LLDB control. The process is created and stopped at the entry point, ready for debugging commands.

---

### `attach`

```python
def attach(self, pid: int) -> None
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pid` | `int` | *(required)* | The process ID to attach to. |

**Returns**: `None`

Attaches the debugger to a running process by its PID. The process is stopped once attached.

---

### `attach_by_name`

```python
def attach_by_name(self, name: str) -> None
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | *(required)* | The process name to search for and attach to. |

**Returns**: `None`

Attaches the debugger to a running process by its name. If multiple processes share the same name, the behavior depends on the underlying LLDB implementation.

---

### `act`

```python
def act(self, instruction: str) -> ActResult
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `instruction` | `str` | *(required)* | A natural-language instruction describing what to do. |

**Returns**: `ActResult`

Translates a natural-language instruction into Python code using the bridge API, executes it in a persistent namespace, and returns the results. Variables persist across `act()` calls within a session. This is the primary method for interacting with the debugger using plain English.

---

### `extract`

```python
def extract(self, instruction: str, response_model: Type[T]) -> T
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `instruction` | `str` | *(required)* | A natural-language query describing what data to extract. |
| `response_model` | `Type[T]` | *(required)* | A Pydantic model class defining the shape of the extracted data. |

**Returns**: `T` -- An instance of `response_model` populated with the extracted data.

Queries the current debugger state and extracts structured data according to the provided Pydantic model. Useful for programmatic access to debugger information.

---

### `observe`

```python
def observe(self, instruction: Optional[str] = None) -> ObserveResult
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `instruction` | `Optional[str]` | `None` | Optional focus hint for the observation. |

**Returns**: `ObserveResult`

Captures and summarizes the current debugger state, including registers, stack trace, and variables. Returns suggested Python code snippets using the bridge API. If an instruction is provided, the observation is focused on the relevant aspects.

---

### `agent`

```python
def agent(
    self,
    task: str,
    strategy: str = "depth-first",
    max_steps: Optional[int] = None,
    timeout: Optional[float] = None
) -> List[AgentStep]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `task` | `str` | *(required)* | A natural-language description of the debugging task to accomplish. |
| `strategy` | `str` | `"depth-first"` | The agent strategy: `"depth-first"`, `"breadth-first"`, or `"hypothesis-driven"`. |
| `max_steps` | `Optional[int]` | `None` | Maximum number of agent iterations. Falls back to config value if not set. |
| `timeout` | `Optional[float]` | `None` | Maximum runtime in seconds. Falls back to config value if not set. |

**Returns**: `List[AgentStep]`

Runs an autonomous agent loop that plans and executes a series of debugging actions to accomplish the given task. Each step includes the action taken, the observation from that action, and the agent's reasoning.

---

### `end`

```python
def end(self) -> None
```

**Returns**: `None`

Terminates the debug session and cleans up all resources, including the LLDB debugger instance and any running processes. Called automatically when using the context manager.

---

## `AsyncMorgul` (asynchronous)

An asynchronous version of `Morgul`. The constructor, `start`, `attach`, `attach_by_name`, and `end` methods have the same signatures as the synchronous version. The following methods are asynchronous:

- `async def act(self, instruction: str) -> ActResult`
- `async def extract(self, instruction: str, response_model: Type[T]) -> T`
- `async def observe(self, instruction: Optional[str] = None) -> ObserveResult`
- `async def agent(self, task: str, strategy: str = "depth-first", max_steps: Optional[int] = None, timeout: Optional[float] = None) -> List[AgentStep]`

Supports `async with` for use as an asynchronous context manager:

```python
async with AsyncMorgul() as m:
    m.start("/path/to/binary")
    result = await m.act("set a breakpoint at main")
```

All parameters, return types, and behaviors are identical to their synchronous counterparts.
