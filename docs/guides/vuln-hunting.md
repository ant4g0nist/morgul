# Guide: Vulnerability Hunting

## Overview

Use Morgul's agent mode to autonomously hunt for vulnerabilities in binaries. The agent issues debugger commands, inspects memory and control flow, forms hypotheses, and tests them -- all driven by the LLM.

## Basic Setup

```python
from morgul.core import Morgul

with Morgul() as morgul:
    morgul.start("./target_binary")

    steps = morgul.agent(
        task=(
            "Analyze this binary for potential buffer overflow vulnerabilities. "
            "Look for functions that handle user input (read, scanf, gets, strcpy, etc.). "
            "Set breakpoints on suspicious functions, examine their arguments, "
            "and determine if there are any unchecked buffer sizes."
        ),
        strategy="hypothesis-driven",
        max_steps=30,
        timeout=120.0,
    )

    for step in steps:
        print(f"Step {step.step_number}: {step.action}")
        print(f"  Observation: {step.observation[:200]}")
        if step.reasoning:
            print(f"  Reasoning: {step.reasoning[:200]}")
```

## Choosing a Strategy

The `strategy` parameter controls how the agent explores the target.

- **`hypothesis-driven`**: Best for targeted vulnerability hunting. The agent forms hypotheses about where vulnerabilities might be and tests them systematically. Start here for most vuln-hunting tasks.

- **`breadth-first`**: Good for initial reconnaissance. The agent maps the attack surface first -- listing functions, identifying input handlers, cataloging interesting symbols -- before going deep on any single path.

- **`depth-first`**: Good for tracing a specific suspicious code path end-to-end. Use this when you already know which function or code region to investigate and want the agent to follow it as far as possible.

## Writing Effective Task Descriptions

The quality of the task description directly affects the quality of the agent's work. Be specific about:

- **What kind of vulnerabilities to look for.** "Buffer overflows in string handling" is better than "find bugs."
- **What input sources to examine.** Name the functions or data paths: "user input from `read()` on the network socket" is better than "external input."
- **What success looks like.** "Determine if the buffer size is checked before the copy" gives the agent a clear stopping criterion.

Vague prompts lead to unfocused exploration. Specific prompts lead to actionable results.

## Interpreting Results

Each step in the returned list contains:

- **`action`**: The debugger command the agent issued (e.g., setting a breakpoint, reading memory, disassembling a function).
- **`observation`**: What the agent saw as a result of that action.
- **`reasoning`**: Why the agent chose that particular action -- what hypothesis it was testing or what it expected to find.

Walk through the steps sequentially to understand the agent's investigation path. Pay attention to the reasoning field: it reveals whether the agent is following a productive line of inquiry or going in circles. If you see repeated or circular reasoning, consider refining the task description and running again with fewer `max_steps`.
