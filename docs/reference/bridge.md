# Bridge Reference (morgul-bridge)

> Most users interact with Morgul through the high-level `Morgul` class. The bridge API is used internally but documented here for advanced usage.

The bridge layer (`morgul.bridge`) provides a Pythonic wrapper around LLDB's SB API, handling low-level debugger operations. The high-level `Morgul` class delegates all debugger interactions to this layer.

---

## `Debugger` class

```python
from morgul.bridge import Debugger
```

### Constructor

```python
Debugger()
```

Creates a new LLDB debugger instance. Raises `RuntimeError` if the `lldb` Python module is not available.

Supports use as a context manager:

```python
with Debugger() as dbg:
    target = dbg.create_target("/path/to/binary")
    # ...
# Debugger is destroyed automatically on exit.
```

---

### `create_target`

```python
def create_target(self, path: str) -> Target
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | *(required)* | Path to the executable to load as a debug target. |

**Returns**: `Target` -- An LLDB `SBTarget` object.

Creates a debug target from an executable path. The target is loaded but no process is launched yet.

---

### `attach`

```python
def attach(self, pid: int) -> Tuple[Target, Process]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pid` | `int` | *(required)* | Process ID to attach to. |

**Returns**: `Tuple[Target, Process]` -- A tuple of the LLDB target and the attached process.

Attaches the debugger to a running process by its PID. The process is stopped after attachment completes.

---

### `attach_by_name`

```python
def attach_by_name(self, name: str) -> Tuple[Target, Process]
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | *(required)* | Name of the process to attach to. |

**Returns**: `Tuple[Target, Process]` -- A tuple of the LLDB target and the attached process.

Attaches the debugger to a running process by its name. Searches for a matching process and attaches to it.

---

### `execute_command`

```python
def execute_command(self, command: str) -> CommandResult
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `command` | `str` | *(required)* | An LLDB command string to execute (e.g., `"breakpoint set -n main"`). |

**Returns**: `CommandResult`

Executes a raw LLDB command and returns the result, including output text, error text, and a success flag.

---

### `destroy`

```python
def destroy(self) -> None
```

**Returns**: `None`

Destroys the debugger instance and releases all associated resources. Called automatically when using the context manager.

---

### Properties

| Property | Type | Access | Description |
|----------|------|--------|-------------|
| `async_mode` | `bool` | read/write | Controls whether the debugger operates in asynchronous mode. When `True`, commands return immediately and events must be handled manually. Default is `False`. |

---

## Bridge Types

### Enums

```python
from morgul.bridge import ProcessState, StopReason
```

#### `ProcessState`

Represents the state of a debugged process.

| Value | Description |
|-------|-------------|
| `INVALID` | The process state is invalid or unknown. |
| `UNLOADED` | The process has not been loaded. |
| `CONNECTED` | Connected to a remote debug server. |
| `ATTACHING` | Currently attaching to a process. |
| `LAUNCHING` | Currently launching a process. |
| `STOPPED` | The process is stopped (e.g., at a breakpoint). |
| `RUNNING` | The process is currently running. |
| `STEPPING` | The process is mid-step operation. |
| `CRASHED` | The process has crashed. |
| `DETACHED` | The debugger has detached from the process. |
| `EXITED` | The process has exited. |
| `SUSPENDED` | The process is suspended. |

#### `StopReason`

Describes why a process or thread stopped.

| Value | Description |
|-------|-------------|
| `INVALID` | The stop reason is invalid or unknown. |
| `NONE` | No specific stop reason. |
| `TRACE` | Stopped due to a trace (single-step). |
| `BREAKPOINT` | Stopped at a breakpoint. |
| `WATCHPOINT` | Stopped at a watchpoint. |
| `SIGNAL` | Stopped due to a signal. |
| `EXCEPTION` | Stopped due to an exception. |
| `EXEC` | Stopped after an exec system call. |
| `PLAN_COMPLETE` | A thread plan completed. |
| `THREAD_EXITING` | The thread is exiting. |
| `INSTRUMENTATION` | Stopped due to instrumentation. |

---

### Data Classes

All bridge data classes are frozen (immutable after creation).

```python
from morgul.bridge import (
    RegisterValue, Variable, MemoryRegion, ModuleInfo, CommandResult
)
```

#### `RegisterValue`

A CPU register name and its current value.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Register name (e.g., `"rax"`, `"pc"`). |
| `value` | `int` | Current integer value. |
| `size` | `int` | Register size in bytes. |

#### `Variable`

A variable visible in the current scope.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Variable name. |
| `type_name` | `str` | Type of the variable as a string. |
| `value` | `str` | String representation of the variable's value. |
| `address` | `Optional[int]` | Memory address of the variable, if applicable. |
| `size` | `Optional[int]` | Size of the variable in bytes, if known. |

#### `MemoryRegion`

A contiguous region of process memory.

| Field | Type | Description |
|-------|------|-------------|
| `start` | `int` | Start address. |
| `end` | `int` | End address. |
| `readable` | `bool` | Whether the region has read permission. |
| `writable` | `bool` | Whether the region has write permission. |
| `executable` | `bool` | Whether the region has execute permission. |
| `name` | `Optional[str]` | Name or label (e.g., mapped file path). |

#### `ModuleInfo`

Information about a loaded shared library or executable.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Module file name. |
| `path` | `str` | Full file path on disk. |
| `uuid` | `str` | UUID of the binary. |
| `base_address` | `int` | Base load address in the process. |

#### `CommandResult`

Result of executing a raw LLDB command.

| Field | Type | Description |
|-------|------|-------------|
| `output` | `str` | Standard output from the command. |
| `error` | `str` | Error output from the command. |
| `succeeded` | `bool` | Whether the command completed successfully. |
