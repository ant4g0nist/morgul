# act() - Execute Debugging Actions

The `act()` primitive translates natural language instructions into Python code using the bridge API, executes the code against the live process, and returns the result. Under the hood, the LLM generates Python code that uses bridge objects (`process`, `target`, `frame`, `thread`, `debugger`) and memory utilities -- the same execution model as the REPL agent.

## Signature

```python
morgul.act(instruction: str) -> ActResult
```

## ActResult

The return value is an `ActResult` with the following fields:

| Field | Type | Description |
|---|---|---|
| `success` | `bool` | Whether the code executed successfully |
| `message` | `str` | LLM's reasoning about what it did |
| `actions` | `List[Action]` | Actions that were generated |
| `output` | `str` | Captured stdout/stderr from execution |

Each `Action` in the list has:

| Field | Type | Description |
|---|---|---|
| `code` | `str` | Python code that was executed via the bridge API |
| `command` | `str` | Legacy LLDB CLI command (for backward compatibility) |
| `description` | `str` | Human-readable explanation of the action |
| `args` | `Dict[str, Any]` | Additional arguments |

## Execution Model

When you call `act()`, Morgul:

1. Captures a snapshot of the current process state (registers, stack, disassembly, etc.).
2. Sends the instruction + context to the LLM, which generates Python code using the bridge API.
3. Executes the code in a **persistent namespace** via `PythonExecutor` -- variables persist across `act()` calls within a session.
4. Returns the captured output.

The bridge API objects available in the execution namespace include:

- `process`, `thread`, `frame`, `target`, `debugger` -- live debugger objects
- `read_string()`, `read_pointer()`, `read_uint8/16/32/64()`, `search_memory()` -- memory utilities
- `struct`, `binascii`, `json`, `re`, `collections`, `math` -- stdlib modules

## Examples

```python
# Set breakpoints
result = morgul.act("set a breakpoint on main")

# Step through code
result = morgul.act("step over the next instruction")

# Memory operations
result = morgul.act("dump the heap object pointed to by x0")

# Complex operations
result = morgul.act("break on every Objective-C method that accesses the keychain")
```

## Inspecting Results

Every `ActResult` gives you full visibility into what Morgul did and why:

```python
result = morgul.act("set a breakpoint on main")
print(f"Success: {result.success}")
print(f"Reasoning: {result.message}")
for action in result.actions:
    print(f"  Code: {action.code}")
    print(f"  Description: {action.description}")
print(f"Output: {result.output}")
```

The `message` field contains the LLM's reasoning, which is useful for understanding why a particular approach was chosen. The `actions` list shows exactly what was generated, so you always have a clear audit trail.

## Variable Persistence

Variables defined in one `act()` call persist to subsequent calls within the same session:

```python
# First call: store a value
morgul.act("read the value at register x0 and save it as a variable")

# Second call: can reference the variable from the first call
morgul.act("read 64 bytes from the address we saved earlier")
```

This is possible because `act()` uses the same `PythonExecutor` instance throughout the session, maintaining a persistent namespace.

## Self-Healing

If the generated code raises an exception and `self_heal` is enabled (the default), Morgul will:

1. Re-snapshot the current process state.
2. Feed the Python traceback back to the LLM so it understands what went wrong.
3. Retry with an alternative approach.

This continues up to `max_retries` times (default: 3). For example, if code references an attribute that doesn't exist on a bridge object, the LLM can correct the approach on retry using the error context.

## Async Usage

When using `AsyncMorgul`, the `act()` method is awaitable:

```python
async with AsyncMorgul() as morgul:
    morgul.start("/path/to/binary")
    result = await morgul.act("set a breakpoint on main")
```

## See Also

- [extract() - Structured Data Extraction](extract.md)
- [observe() - Survey and Suggest](observe.md)
- [API Reference](../reference/api.md)
