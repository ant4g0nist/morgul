# Core Concepts

This page covers the fundamental building blocks of Morgul. Understanding these concepts will help you get the most out of the framework.

## Sessions

A **session** is the main unit of interaction. It binds a debugger instance to Morgul's primitives, managing the lifecycle of the connection between Morgul's AI layer and the underlying LLDB process.

**Lifecycle**: `start(target_path)` or `attach(pid)` then use primitives then `end()`.

```python
with Morgul() as morgul:
    morgul.start("/path/to/binary")
    # ... use primitives ...
# session auto-cleaned up
```

Both synchronous (`Morgul`) and asynchronous (`AsyncMorgul`) variants are available. The context manager pattern shown above ensures cleanup happens automatically, even if an exception is raised.

You can also attach to a running process by PID:

```python
with Morgul() as morgul:
    morgul.attach(pid=12345)
    # ... use primitives ...
```

## The Three Primitives

Morgul exposes three core primitives that cover the full spectrum of debugging interactions:

### act(instruction)

Execute a debugging action described in natural language. Returns an `ActResult` containing the commands that were run and their output.

```python
result = morgul.act("set a breakpoint on main")
```

See [act() deep dive](act.md) for full details.

### extract(instruction, response_model)

Pull structured, typed data from the live process. You provide a Pydantic model describing the shape of the data you want, and Morgul returns a populated instance.

```python
vuln = morgul.extract("analyze the current function for overflow potential", VulnContext)
```

See [extract() deep dive](extract.md) for full details.

### observe(instruction)

Survey the process state and suggest next actions without executing anything. Returns an `ObserveResult` with a ranked list of suggested actions.

```python
obs = morgul.observe("what functions handle network input?")
```

See [observe() deep dive](observe.md) for full details.

## The Translation Pipeline

Every call to a Morgul primitive follows the same pipeline:

1. **Natural language instruction** -- you describe what you want in plain English.
2. **LLM (with process context)** -- the instruction is sent to the language model along with live state from the debugger.
3. **Python code** -- the LLM produces Python code using the bridge API (`process`, `target`, `frame`, `thread`, `debugger`, memory utilities).
4. **Execute via PythonExecutor** -- code runs in a persistent namespace with live bridge objects. Variables persist across `act()` calls.
5. **Result** -- output is captured and returned to you.

```
Natural Language Instruction
        |
        v
   LLM (with process context)
        |
        v
   Python Code (bridge API)
        |
        v
   PythonExecutor (persistent namespace)
        |
        v
   Result (ActResult / Model / ObserveResult)
```

## Context Builder

Morgul gathers live process state and prunes it to fit the LLM's token budget. The context builder collects:

```
Live Process
    |
Context Builder
    |
    +-- Registers
    +-- Stack trace
    +-- Disassembly
    +-- Variables
    +-- Modules
    |
Pruned Context Window
    |
    LLM
```

Priority ordering ensures the most relevant state is included first. For example, registers and the immediate stack trace take precedence over the full module list. This is what makes Morgul token-efficient -- rather than dumping the entire process state into every prompt, the context builder selects and ranks information based on what is most likely to be useful for the current instruction.

## Self-Healing

When generated code raises an exception, Morgul does not simply report the error. Instead, it:

1. Re-snapshots the process state to get a fresh view.
2. Feeds the Python traceback back to the LLM so it understands what went wrong.
3. Retries with an alternative approach.

This behavior is configurable via two settings:

- `self_heal` -- enable or disable the retry mechanism (default: enabled).
- `max_retries` -- how many times to retry before giving up (default: 3).

These can be set in `morgul.toml` or passed directly when constructing a session.

## Content-Addressed Caching

Analysis results are cached using a content-addressed scheme keyed on the actual bytes of the function being analyzed, not on memory addresses. This means that ASLR and relocation do not invalidate cached results. If you analyze the same function across multiple runs of the same binary, Morgul will reuse the cached analysis.

## Next Steps

- [act() -- Execute Debugging Actions](act.md)
- [extract() -- Structured Data Extraction](extract.md)
- [observe() -- Survey and Suggest](observe.md)
- [Agent Mode -- Autonomous Debugging](agent.md)
