<p align="center">
  <img src="assets/morgul-banner.png" alt="Morgul" width="100%" />
</p>

<h1 align="center">Morgul</h1>

<p align="center">
  <strong>The AI Debugger Automation Framework</strong><br/>
  <em>Enter the tower. Understand the sorcery.</em>
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> •
  <a href="#primitives">Primitives</a> •
  <a href="#agent-mode">Agent Mode</a> •
  <a href="#web-dashboard">Dashboard</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#roadmap">Roadmap</a> •
  <a href="#contributing">Contributing</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-Apache%202.0-black?style=flat-square" />
  <img src="https://img.shields.io/badge/python-3.10+-black?style=flat-square" />
  <img src="https://img.shields.io/badge/lldb-16+-black?style=flat-square" />
</p>

---

> **This project is experimental and under active development.** APIs, configuration formats, and internal behaviour may change without notice. Use at your own risk and expect rough edges. Currently, Morgul is in alpha, and only tested with OpenAI.

---

**Morgul** is a debugger automation framework that lets you control LLDB with natural language and code. By combining AI with the precision of low-level debugging, Morgul makes binary analysis flexible, repeatable, and actually autonomous.

Most reverse engineering tools force a choice: write brittle LLDB scripts that break across binaries, or paste decompiler output into ChatGPT and hope for the best. Morgul gives you both — deterministic debugger control when you know what you want, and AI-driven reasoning when you don't.

| Primitive | What it does | Example |
|---|---|---|
| `act()` | Translate natural language to Python code (bridge API) and execute | `act("break on the auth check")` |
| `extract()` | Pull structured, typed data from live process state | `extract("analyze for overflows", response_model=VulnContext)` |
| `observe()` | Survey the current state and suggest next actions | `observe("what functions touch user input?")` |
| `agent()` | Autonomous multi-step debugging with reasoning | `agent(task="find the use-after-free")` |

---

## Quickstart

```bash
pip install morgul
```

```python
from morgul.core import Morgul

with Morgul() as morgul:
    morgul.start("/path/to/binary")

    # Use act() for precise debugger actions
    result = morgul.act("set a breakpoint on main and continue to it")
    print(result.success, result.output)

    # Use extract() to pull structured data from the live process
    from pydantic import BaseModel

    class FuncInfo(BaseModel):
        name: str
        args: list[str]
        local_vars: list[str]

    info = morgul.extract(
        "extract the current function name, arguments, and local variables",
        response_model=FuncInfo,
    )

    # Use observe() to survey without acting
    obs = morgul.observe("what interesting functions handle user input?")
    print(obs.description)
    for action in obs.actions:
        print(f"  Suggested: {action.command} — {action.description}")

    # Use agent() for autonomous multi-step goals
    steps = morgul.agent(
        task="find the buffer overflow in the request parser",
        strategy="hypothesis-driven",
        max_steps=30,
    )
    for step in steps:
        print(f"Step {step.step_number}: {step.action}")
```

For async workflows, use `AsyncMorgul`:

```python
from morgul.core import AsyncMorgul

async with AsyncMorgul() as morgul:
    morgul.start("/path/to/binary")
    result = await morgul.act("set a breakpoint on main")
```

---

## Primitives

Morgul provides three atomic primitives that map natural language to debugger operations. Use them when you want precise control over what happens.

### `act(instruction)`

Perform a debugger action described in natural language. Returns an `ActResult` with `success`, `output`, and `message`.

```python
# Sets breakpoints intelligently — resolves symbols, handles mangled names
result = morgul.act("break on every Objective-C method that accesses the keychain")

# Steps with intent, not just line-by-line
result = morgul.act("step forward until we hit a branch that depends on user input")

# Patches on the fly
result = morgul.act("patch this comparison to always return true")

# Memory operations with context
result = morgul.act("dump the heap object pointed to by x0 and show me its vtable")

print(result.success)  # True/False
print(result.output)   # Raw output from execution
```

Under the hood, `act()` translates your instruction into Python code that uses the bridge API (`process`, `target`, `frame`, `thread`, `debugger`, memory utilities), executes it in a persistent namespace, and returns the result. Variables persist across `act()` calls within a session. It understands architecture-specific registers, calling conventions, and debug info formats.

If the generated code fails, **self-healing** kicks in: Morgul feeds the traceback back to the LLM, re-snapshots the process state, and retries with a corrected approach (up to `max_retries` times).

### `extract(instruction, response_model)`

Pull structured, typed data from the live process. Define a Pydantic model for the shape of what you need, and Morgul fills it in from the current process state.

```python
from pydantic import BaseModel

class VulnContext(BaseModel):
    function_name: str
    buffer_size: int
    max_input_size: int
    bounds_checked: bool
    input_controlled_args: list[str]
    stack_canary_present: bool

vuln = morgul.extract(
    "analyze the current function for buffer overflow potential",
    response_model=VulnContext,
)

if not vuln.bounds_checked and vuln.max_input_size > vuln.buffer_size:
    print(f"{vuln.function_name}: {vuln.max_input_size} into {vuln.buffer_size}-byte buffer")
```

`extract()` is the killer primitive. Instead of dumping 500 lines of decompiled C into a prompt, you define the shape of what you need and let Morgul's context builder gather exactly the right process state to answer it.

### `observe(instruction)`

Survey the process state and return possible next actions — without performing any of them. Returns an `ObserveResult` with a `description` and a ranked list of suggested `actions`.

```python
obs = morgul.observe("what attack surface is reachable from this entry point?")

print(obs.description)
for action in obs.actions:
    print(f"  {action.command} — {action.description}")

# Pick one and act on it
morgul.act(obs.actions[0].command)
```

`observe()` is your recon tool. It examines the current process state — registers, stack, disassembly, symbols — and suggests what's worth investigating next.

---

## Agent Mode

For complex, multi-step goals, hand control to an autonomous agent that loops through observe/act/extract/reason cycles. The `agent()` method returns a list of `AgentStep` objects describing what the agent did.

```python
steps = morgul.agent(
    task="reverse engineer the license validation algorithm",
    strategy="depth-first",  # or "breadth-first", "hypothesis-driven"
    max_steps=50,
    timeout=300.0,
)

for step in steps:
    print(f"Step {step.step_number}: {step.action}")
    print(f"  Reasoning: {step.reasoning}")
    print(f"  Result: {step.observation}")
```

### Agent Strategies

| Strategy | Behavior | Best For |
|---|---|---|
| `depth-first` | Follow one code path deeply before backtracking | Tracing specific flows, crash analysis |
| `breadth-first` | Survey all reachable functions, then dive into interesting ones | Attack surface mapping |
| `hypothesis-driven` | Form a hypothesis, test it, revise | Vulnerability hunting |

### REPL Agent

For interactive, iterative debugging with direct LLDB bridge access:

```python
result = morgul.repl_agent(
    task="trace the authentication flow and find logic flaws",
    max_iterations=30,
)
print(result.summary)
```

---

## The Context Builder

The hardest problem in AI-assisted RE isn't the LLM — it's deciding **what to show it**. A live process has thousands of functions, megabytes of mapped memory, and hundreds of threads. Dumping everything into a prompt is wasteful and noisy.

Morgul's context builder intelligently selects what the LLM sees:

```
┌─────────────────────────────────────────────────┐
│                  LIVE PROCESS                    │
│                                                  │
│  threads ─── stack frames ─── registers          │
│  memory maps ─── heap ─── loaded libraries       │
│  thousands of functions ─── debug symbols        │
└──────────────────────┬──────────────────────────┘
                       │
                  Context Builder
                       │
              ┌────────┼────────┐
              ▼        ▼        ▼
         ┌────────┐┌───────┐┌──────────┐
         │ Disas- ││ Proc  ││ Symbol   │
         │ sembly ││ State ││ Table    │
         │ View   ││ View  ││ View     │
         └────┬───┘└───┬───┘└────┬─────┘
              │        │         │
              ▼        ▼         ▼
    ┌──────────────────────────────────┐
    │     Pruned Context Window        │
    │                                  │
    │  • Current frame disassembly     │
    │  • Register state                │
    │  • Stack trace                   │
    │  • Relevant memory              │
    │  • Type info from DWARF         │
    │  • Symbol table                  │
    └──────────────┬───────────────────┘
                   │
                   ▼
                 ┌─────┐
                 │ LLM │
                 └─────┘
```

The context builder is what makes Morgul token-efficient. It prunes process state to the most relevant subset, keeping LLM calls focused and cost-effective.

---

## Web Dashboard

Watch the agent work in real time with a browser-based split-pane dashboard — LLDB execution on the left, AI reasoning on the right.

```python
with Morgul(dashboard_port=8546) as m:
    m.start("./crackme", args=["MORGUL-TEST-1234"])
    m.agent(task="reverse engineer the license validation algorithm")
    m.wait_for_dashboard()  # keep dashboard alive until Ctrl+C
```

```bash
# From the CLI examples
PYTHONPATH="$(lldb -P)" uv run python examples/reverse_unknown.py \
  examples/crackme/crackme --args MORGUL-XXXX-YYYY-ZZZZ \
  --dashboard \
  --task "find the license validation algorithm"
```

The dashboard uses zero external dependencies (no CDN, no npm) — it's a self-contained HTML page served by a stdlib `asyncio` HTTP server. Events stream via SSE with auto-reconnect, history replay for late-joining clients, and a session-end summary.

---

## Caching & Self-Healing

### Content-Addressed Caching *(experimental)*

Morgul caches results keyed by content (instruction + process state), not addresses. ASLR and relocation don't invalidate the cache.

```python
# First time: LLM analyzes (slow, costs tokens)
result = morgul.act("set a breakpoint on main")

# Second time, same instruction at same state: instant cache hit
result = morgul.act("set a breakpoint on main")  # no LLM call
```

Caching applies to all three primitives (`act`, `extract`, `observe`). For `act()`, only successful results are cached — if self-healing was needed, the final healed result is stored so subsequent calls skip the entire heal cycle.

```toml
# morgul.toml
[cache]
enabled = true              # default
directory = ".morgul/cache"  # default
```

### Self-Healing

When generated code fails at runtime, Morgul doesn't just raise an error. It feeds the traceback back to the LLM, re-snapshots the process state, and asks for a corrected approach.

```python
# You wrote this against v1.0 — function was renamed in v1.1
result = morgul.act("break on validate_license")
# First attempt fails (symbol not found), Morgul re-snapshots,
# LLM sees the updated symbol table, and retries with the correct name
# Result: success — breakpoint set on the renamed function
```

```toml
[healing]
max_retries = 3
```

---

## Configuration

Morgul is configured via a `morgul.toml` file in the working directory, or by passing a `MorgulConfig` object directly.

```toml
# morgul.toml
verbose = false
self_heal = true
dashboard_port = 8546

[llm]
provider = "anthropic"            # "anthropic", "openai", or "ollama"
model = "claude-sonnet-4-20250514"
temperature = 0.5
max_tokens = 4096
# api_key = "sk-..."             # or set ANTHROPIC_API_KEY / OPENAI_API_KEY env var
# base_url = "http://localhost:11434"  # required for ollama

[cache]
enabled = true
directory = ".morgul/cache"

[healing]
max_retries = 3

[agent]
max_steps = 50
timeout = 300.0
strategy = "depth-first"
```

Or configure programmatically:

```python
from morgul.core import Morgul
from morgul.core.types.config import MorgulConfig, LLMConfig

config = MorgulConfig(
    llm=LLMConfig(
        provider="openai",
        model="gpt-4o",
    ),
    self_heal=True,
)

with Morgul(config=config) as morgul:
    morgul.start("/path/to/binary")
    ...
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     Your Script / Agent                   │
│                                                          │
│   morgul.act()    morgul.extract()    morgul.observe()    │
└────────────────────────┬─────────────────────────────────┘
                         │
                    Morgul Core
                         │
          ┌──────────────┼──────────────┐
          │              │              │
    ┌─────▼─────┐  ┌────▼─────┐  ┌────▼──────┐
    │ Translate  │  │ Context  │  │  Cache    │
    │ Engine     │  │ Builder  │  │  Layer    │
    │            │  │          │  │           │
    │ NL → Code  │  │ Process  │  │ Content-  │
    │ (bridge    │  │ state →  │  │ addressed │
    │  API)      │  │          │  │           │
    │            │  │ pruned   │  │ analysis  │
    │            │  │ context  │  │ results   │
    └─────┬─────┘  └────┬─────┘  └────┬──────┘
          │              │              │
          ▼              ▼              ▼
    ┌─────────────────────────────────────────┐
    │              Morgul Bridge               │
    │                                         │
    │         MCP Server (lisa.py)             │
    │            LLDB Python API              │
    └────────────────┬────────────────────────┘
                     │
                     ▼
              ┌─────────────┐
              │ Live Process │
              └─────────────┘
```

### Components

**Morgul Core** — The SDK that developers interact with. Exposes `act()`, `extract()`, `observe()`, and `agent()`. Handles LLM routing, schema validation, and orchestration.

**Translate Engine** — Converts natural language instructions into Python code using the bridge API. The LLM generates code that operates on live bridge objects (`process`, `target`, `frame`, `thread`, `debugger`) and memory utilities. Code executes in a persistent namespace via `PythonExecutor`, so variables persist across `act()` calls.

**Context Builder** — Gathers and prunes process state into a token-efficient context window. Pulls from LLDB's runtime state, debug symbols (DWARF), and the symbol table.

**Cache Layer** — Content-addressed cache of analysis results. Keyed on instruction + context content (not addresses), so ASLR and relocation don't invalidate results.

**Morgul Bridge** — The low-level interface to the debugger. Built on [lisa.py](https://github.com/ant4g0nist/lisa.py)'s MCP server. Exposes structured tool calls that the upper layers consume.

---

## Examples

The `examples/` directory contains runnable scripts. See [examples documentation](docs/getting-started/examples.md) for full setup instructions.

```bash
# Build the test binary
./examples/build_test_binary.sh

# Basic usage
PYTHONPATH="$(lldb -P)" uv run python examples/basic_act.py

# Autonomous agent with web dashboard
PYTHONPATH="$(lldb -P)" uv run python examples/reverse_unknown.py \
  examples/crackme/crackme --args MORGUL-XXXX-YYYY-ZZZZ --dashboard

# Caching demo
PYTHONPATH="$(lldb -P)" uv run python examples/caching_demo.py

# Self-healing demo
PYTHONPATH="$(lldb -P)" uv run python examples/self_healing_demo.py --dashboard

# Vulnerability triage
./examples/vuln_targets/build.sh
PYTHONPATH="$(lldb -P)" uv run python examples/vuln_triage.py
```

---

## Supported Targets

| Platform | Architectures | Status |
|---|---|---|
| macOS | arm64, x86_64 | Full support |
| Linux | arm64, x86_64 | Full support |
| iOS | arm64 | Via remote debug |
| Android | arm64 | In progress |
| Windows (PE) | x86_64 | Planned |

### Supported Models

Morgul is model-agnostic. Configure the provider and model in `morgul.toml` or via `MorgulConfig`:

```toml
[llm]
provider = "anthropic"
model = "claude-sonnet-4-20250514"  # recommended

# Or OpenAI
# provider = "openai"
# model = "gpt-4o"

# Or fully local via Ollama
# provider = "ollama"
# model = "deepseek-r1"
# base_url = "http://localhost:11434"
```

---

## Roadmap

Features under consideration for future releases — none of these exist in the codebase today:

- **Agent event streaming** — Stream agent reasoning in real time for live visibility into the observe/act/reason loop
- **Vulnerability scanner** — A pattern-matching engine for sweeping binaries against known vulnerability signatures
- **Custom tool registration** — A decorator API for registering domain-specific tools that the agent can autonomously invoke
- **Morgul Cloud** — Hosted debug sandboxes on demand. Upload a binary, get an isolated container with LLDB + Morgul, analyze from anywhere
- **Ghidra integration** — Headless decompilation as an additional context source for the context builder
- **Pre-built signatures** — Ship pre-analyzed summaries for common system libraries (libc, Foundation, OpenSSL)
- **Fuzzer integration** — Closed-loop fuzzer harness generation and crash triage

---

## Standing on the Shoulders of

Morgul wouldn't exist without these projects:

- **[lisa.py](https://github.com/ant4g0nist/lisa.py)** — MCP integration for LLDB by [@ant4g0nist](https://github.com/ant4g0nist). The bridge that makes this possible.
- **[Polar](https://github.com/ant4g0nist/polar)** — LLM plugin for LLDB by [@ant4g0nist](https://github.com/ant4g0nist). The proof that this idea works.
- **[Stagehand](https://github.com/browserbase/stagehand)** — Browserbase's AI browser automation framework. The architectural blueprint.
- **[LLDB](https://lldb.llvm.org/)** — The LLVM debugger. The engine under the hood.

---

## Contributing

We're focused on improving **reliability > extensibility > speed > cost** in that order.

The highest-impact contributions right now:

1. **Context builder heuristics** — Better strategies for what process state to include in the LLM context
2. **Translate engine accuracy** — More robust NL to Python code translation, especially for complex memory operations
3. **Platform support** — Android and Windows targets
4. **Benchmarks** — Reproducible evals for vuln-finding accuracy against known-vulnerable binaries

Open an issue or submit a PR.

---

<p align="center">
  <em>"Do not come between the researcher and their prey."</em>
</p>

<p align="center">
  Apache License 2.0 · Copyright 2025 ant4g0nist
</p>
