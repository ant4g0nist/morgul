# Quickstart

Your first Morgul session in 60 seconds.

## Step 1: Configure your LLM provider

Morgul needs access to a large language model. Set the appropriate environment variable for your provider:

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
# or
export OPENAI_API_KEY="your-api-key-here"
```

Alternatively, create a `morgul.toml` file in your working directory:

```toml
[llm]
provider = "anthropic"
model = "claude-sonnet-4-20250514"
```

## Step 2: Run your first session

Here is a complete working example that launches a binary, sets a breakpoint, and inspects program state -- all through natural language:

```python
from morgul.core import Morgul

with Morgul() as morgul:
    # Launch a target binary
    morgul.start("/usr/bin/ls", args=["-la"])

    # Use natural language to control the debugger
    result = morgul.act("set a breakpoint on main")
    print(f"Success: {result.success} - {result.message}")

    # Continue to the breakpoint
    morgul.act("continue execution")

    # Observe the current state
    obs = morgul.observe("what is the current state of the program?")
    print(f"State: {obs.description}")
    for action in obs.actions:
        print(f"  Suggested: {action.command} - {action.description}")

    # Step through
    result = morgul.act("step over the next instruction")
    print(f"Step: {result.output}")
```

## What happened

In the example above, Morgul performed the following behind the scenes:

1. Created an LLDB debugging session targeting `/usr/bin/ls`.
2. Translated natural language instructions ("set a breakpoint on main") into concrete LLDB commands (`breakpoint set --name main`).
3. Executed those commands against the live process.
4. Used the LLM to observe and summarize the process state, including suggested next actions.

You write intent; Morgul figures out the debugger commands.

## Web Dashboard

Add `dashboard_port` to watch the session in your browser with a split-pane view (LLDB on the left, AI reasoning on the right):

```python
with Morgul(dashboard_port=8546) as morgul:
    morgul.start("/usr/bin/ls", args=["-la"])
    # Browser opens http://127.0.0.1:8546 automatically
    morgul.act("set a breakpoint on main")
    morgul.act("continue execution")
```

## Next steps

- [Core Concepts](../basics/core-concepts.md) -- understand the architecture and key abstractions
- [act()](../basics/act.md) -- the action interface in detail
- [extract()](../basics/extract.md) -- pull structured data from debugger state
- [observe()](../basics/observe.md) -- inspect and summarize program state
