# Examples

Morgul ships with a collection of runnable examples in the `examples/` directory. This page explains how to set them up and what each one demonstrates.

---

## Prerequisites

All examples that debug a live process require the LLDB Python bindings on your `PYTHONPATH`:

```bash
export PYTHONPATH="$(lldb -P)"
```

You also need a configured LLM provider. Either set an environment variable:

```bash
export ANTHROPIC_API_KEY="sk-..."
# or
export OPENAI_API_KEY="sk-..."
```

Or create a `morgul.toml` in the project root (see [Configuration](configuration.md)).

---

## Building the test binaries

Most examples target one of three pre-built binaries. Build them all at once:

```bash
./examples/build_all.sh
```

Or build individually:

### General test binary

Used by most examples (`basic_act`, `self_healing_demo`, `agent_strategies`, etc.):

```bash
./examples/build_test_binary.sh
# Produces: /tmp/morgul_test
```

A simple C binary with `main`, `add`, `greet`, and `process_input` functions. Compiled with `-g -O0` for full debug symbols.

### Vulnerable image parser

Used by `vuln_triage.py`:

```bash
./examples/vuln_targets/build.sh
# Produces: /tmp/imgparse + /tmp/crash_input.mgl
```

A C binary with an intentional heap buffer overflow in its palette parser. The build script also generates a crash-inducing input file.

### Crackme

Used by `reverse_unknown.py`:

```bash
./examples/crackme/build.sh
# Produces: examples/crackme/crackme (stripped)

./examples/crackme/build.sh --debug
# Produces: examples/crackme/crackme (with symbols)
```

A C++ license validation binary for reverse engineering challenges.

---

## Example reference

### Getting started

| Example | Description | Binary |
|---------|-------------|--------|
| `basic_act.py` | Launch a target, set breakpoints, step through code with `act()` | `/tmp/morgul_test` |
| `observe_then_act.py` | Observe-then-act pattern for exploring unfamiliar binaries | `/tmp/morgul_test` |
| `try_it.py` | Quick smoke test using `act()` and `observe()` | `/tmp/morgul_test` |

```bash
PYTHONPATH="$(lldb -P)" uv run python examples/basic_act.py
```

### Structured extraction

| Example | Description | Binary |
|---------|-------------|--------|
| `extract_heap_objects.py` | Extract heap structures into typed Pydantic models | custom |
| `extract_vtable.py` | Extract C++ vtable information into structured data | custom |

### Agent mode

| Example | Description | Binary |
|---------|-------------|--------|
| `agent_strategies.py` | Compare depth-first, breadth-first, and hypothesis-driven strategies | `/tmp/morgul_test` |
| `agent_vuln_hunt.py` | Autonomous vulnerability hunting with the agent loop | `/tmp/morgul_test` |
| `agent_claude_sdk.py` | Run the agent using the Claude Agent SDK backend | `/tmp/morgul_test` |

```bash
PYTHONPATH="$(lldb -P)" uv run python examples/agent_strategies.py
```

### Security analysis

| Example | Description | Binary |
|---------|-------------|--------|
| `vuln_triage.py` | Full vulnerability triage: crash reproduction, analysis, and reporting | `/tmp/imgparse` |
| `reverse_unknown.py` | Reverse engineer an unknown binary with AI-guided analysis | any binary |
| `crash_triage.py` | Attach to a crashed process and diagnose the root cause | running process |
| `memory_forensics.py` | Search memory, read structures, extract patterns | custom |
| `xpc_sniffer.py` | Sniff XPC messages using the bridge API (no LLM calls) | running process |

```bash
# Vulnerability triage (build the target first)
./examples/vuln_targets/build.sh
PYTHONPATH="$(lldb -P)" uv run python examples/vuln_triage.py

# Reverse engineering with web dashboard
./examples/crackme/build.sh
PYTHONPATH="$(lldb -P)" uv run python examples/reverse_unknown.py \
  examples/crackme/crackme --args MORGUL-XXXX-YYYY-ZZZZ --dashboard
```

### Caching and self-healing

| Example | Description | Binary |
|---------|-------------|--------|
| `caching_demo.py` | Demonstrates content-addressed caching — first call hits LLM, repeat calls return instantly | `/tmp/morgul_test` |
| `self_healing_demo.py` | Demonstrates automatic retry and correction when generated code fails | `/tmp/morgul_test` |

```bash
PYTHONPATH="$(lldb -P)" uv run python examples/caching_demo.py
PYTHONPATH="$(lldb -P)" uv run python examples/self_healing_demo.py
PYTHONPATH="$(lldb -P)" uv run python examples/self_healing_demo.py --dashboard
```

### Configuration and patterns

| Example | Description | Binary |
|---------|-------------|--------|
| `config_providers.py` | Switch between Anthropic, OpenAI, and Ollama providers | -- |
| `async_session.py` | Use `AsyncMorgul` for concurrent or event-loop workflows | -- |
| `full_workflow.py` | End-to-end workflow combining all Morgul primitives | `/tmp/morgul_test` |
| `attach_and_inspect.py` | Attach to a running process by PID or name, inspect, detach | running process |

---

## Web dashboard

Most examples support a `--dashboard` flag that opens a browser-based split-pane view (LLDB on the left, AI reasoning on the right):

```bash
PYTHONPATH="$(lldb -P)" uv run python examples/vuln_triage.py --dashboard
PYTHONPATH="$(lldb -P)" uv run python examples/reverse_unknown.py binary --dashboard
PYTHONPATH="$(lldb -P)" uv run python examples/self_healing_demo.py --dashboard 9000
```

The dashboard stays alive after the analysis completes so you can browse the results. Press `Ctrl+C` to exit.
