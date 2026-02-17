# Morgul -- The AI Debugger Automation Framework

> *Enter the tower. Understand the sorcery.*

Morgul lets you control LLDB using natural language. It combines large language models with the LLDB scripting bridge to give you precision debugging through simple, human-readable commands. A small set of powerful primitives lets an AI agent drive a real debugger on your behalf.

---

## What It Looks Like

```python
from morgul.core import Morgul

with Morgul() as morgul:
    morgul.start("/path/to/binary")
    result = morgul.act("set a breakpoint on main and continue")
    obs    = morgul.observe("what functions touch user input?")
    vuln   = morgul.extract("analyze for buffer overflows", VulnContext)
```

---

## Feature Highlights

- **Three primitives** -- `act()`, `extract()`, and `observe()` -- cover the full surface of debugger interaction.
- **Autonomous agent mode** with multiple strategies for automated crash triage, vulnerability analysis, and root-cause investigation.
- **Content-addressed caching** *(experimental)* that survives ASLR. Breakpoints and analysis results are anchored to binary content, not absolute addresses.
- **Self-healing across binary versions.** When a target binary is recompiled or patched, Morgul adapts its breakpoints and scripts automatically.
- **Multi-provider LLM support.** Use Anthropic (Claude), OpenAI (GPT-4), or Ollama for fully local, air-gapped operation.
- **Sync and async APIs.** Integrate Morgul into scripts, CI pipelines, or interactive sessions with equal ease.

---

## Quick Links

- [Getting Started](getting-started/installation.md) -- Install Morgul and run your first debugging session.
- [Examples](getting-started/examples.md) -- Runnable examples with setup instructions.
- [Core Concepts](basics/core-concepts.md) -- Understand the three primitives and the agent architecture.
- [API Reference](reference/api.md) -- Full reference for the Python API.
- [Guides](guides/crash-triage.md) -- Walkthroughs for common tasks like crash triage and vulnerability analysis.

---

## Supported Platforms

| Platform    | Architectures   | Status           |
| ----------- | --------------- | ---------------- |
| macOS       | arm64, x86_64   | Full support     |
| Linux       | arm64, x86_64   | Full support     |
| iOS         | arm64           | Via remote debug |
| Android     | arm64           | In progress      |
| Windows PE  | x86_64          | Planned          |

---

## Supported Models

| Provider  | Models         | Notes                              |
| --------- | -------------- | ---------------------------------- |
| Anthropic | Claude         | Recommended for complex analysis   |
| OpenAI    | GPT-4          | Broad availability                 |
| Ollama    | Local models   | Air-gapped and offline operation   |

Morgul is model-agnostic at its core. Any provider that exposes a chat-completion interface can be wired in through the provider abstraction layer.
