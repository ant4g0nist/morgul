# Guide: Crash Triage

## Overview

This guide covers how to attach to a crashed or running process and analyze it with Morgul. The typical workflow is: attach, observe the crash state, extract a structured report, and optionally dive deeper with agent mode.

## Attaching to a Process

```python
from morgul.core import Morgul

with Morgul() as morgul:
    # Attach by PID
    morgul.attach(12345)

    # Or attach by name
    morgul.attach_by_name("my_process")
```

## Step-by-Step Workflow

### 1. Attach to the Process

Use `attach()` with a PID or `attach_by_name()` with the process name, as shown above.

### 2. Observe the Crash State

```python
obs = morgul.observe("describe the crash state - registers, stack, signal")
print(obs.description)
```

This gives you a natural-language summary of the current process state, including register values, the call stack, and the signal that caused the crash.

### 3. Extract a Structured Crash Report

```python
from pydantic import BaseModel

class CrashReport(BaseModel):
    crash_type: str
    faulting_address: int | None = None
    faulting_function: str | None = None
    signal: str | None = None
    root_cause: str
    exploitability: str
    stack_summary: list[str]

report = morgul.extract(
    "analyze the crash - root cause, exploitability, and classification",
    response_model=CrashReport,
)
print(f"Type: {report.crash_type}")
print(f"Root cause: {report.root_cause}")
print(f"Exploitability: {report.exploitability}")
```

The `extract()` method reads the live debugger state and returns a populated Pydantic model. The LLM examines registers, memory, the stack, and the signal to fill in each field.

### 4. Deep Dive with Agent Mode (If Needed)

```python
steps = morgul.agent(
    "trace backwards from the crash to find the root cause",
    strategy="depth-first",
    max_steps=20,
)
```

Agent mode lets the LLM autonomously issue debugger commands, reason about results, and iterate until it reaches a conclusion. Use this when the crash is not immediately obvious from the surface-level state.

## Tips

- Use `observe()` first to understand the state before extracting structured data. This lets you confirm the process is in the expected crash state and helps you write a better extraction prompt.
- Keep your `CrashReport` schema focused. Add fields only for information you actually need. Optional fields (with `None` defaults) are good for data that may not always be present.
- If agent mode is taking too many steps, tighten the task description or reduce `max_steps`.
