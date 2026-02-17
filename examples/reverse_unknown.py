"""Reverse engineer an unknown binary with Morgul's AI primitives.

This is where Morgul shines: you don't know the binary, you don't know
the symbols, you don't know where to look. The AI figures it out.

Usage:
  PYTHONPATH="$(lldb -P)" uv run python examples/reverse_unknown.py /path/to/binary
  PYTHONPATH="$(lldb -P)" uv run python examples/reverse_unknown.py /path/to/binary --task "find the license check"
"""

import argparse
import sys

from pydantic import BaseModel

from morgul.core import Morgul
from morgul.llm.events import LLMEvent


# ── Progress indicator ──────────────────────────────────────────────────

def _on_llm(event: LLMEvent, is_start: bool) -> None:
    if is_start:
        label = event.model_type or event.method
        sys.stderr.write(f"  [llm: {label}...]\r")
        sys.stderr.flush()
    elif not event.error:
        tokens = ""
        if event.usage:
            tokens = f" {event.usage.input_tokens}+{event.usage.output_tokens}tok"
        sys.stderr.write(f"  [llm: {event.duration:.1f}s{tokens}]    \n")
        sys.stderr.flush()


# ── Extraction schemas ──────────────────────────────────────────────────

class BinaryOverview(BaseModel):
    """High-level summary of a binary."""
    binary_type: str          # "CLI tool", "daemon", "GUI app", "dylib", etc.
    language_hints: list[str] # ["C", "C++", "ObjC", "Swift", "Rust", ...]
    interesting_imports: list[str]  # notable library functions used
    entry_function: str       # name of the entry point
    summary: str              # one-paragraph description


class FunctionOfInterest(BaseModel):
    """A function worth investigating further."""
    name: str
    address: int
    reason: str               # why this function is interesting
    category: str             # "crypto", "network", "auth", "parsing", "IPC", etc.


class FunctionAnalysis(BaseModel):
    """Deep analysis of a single function."""
    name: str
    purpose: str              # what this function does
    args_description: str     # what the arguments are
    return_description: str   # what it returns
    notable_calls: list[str]  # interesting functions it calls
    security_notes: str       # any security-relevant observations


# ── Main ────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="Reverse engineer an unknown binary.")
parser.add_argument("binary", help="Path to the binary to analyze")
parser.add_argument("--args", nargs="*", default=None, help="Arguments to pass to the target binary")
parser.add_argument("--task", default=None, help="Specific task or question about the binary")
parser.add_argument("--depth", type=int, default=3, help="How many functions to deep-dive into")
parser.add_argument("--dashboard", nargs="?", const=8546, type=int,
                    metavar="PORT", help="Open web dashboard (default port 8546)")
args = parser.parse_args()

# When --dashboard is active, the web display handles all output; suppress stdout and the old LLM callback.
llm_cb = None if args.dashboard else _on_llm

if args.dashboard:
    sys.stdout = open("/dev/null", "w")  # noqa: SIM115

with Morgul(llm_event_callback=llm_cb, dashboard_port=args.dashboard) as m:
    m.start(args.binary, args=args.args)

    # ── Phase 1: Recon ──────────────────────────────────────────────
    print(f"═══ Phase 1: Reconnaissance ═══\n")

    obs = m.observe("What kind of binary is this? What are the interesting symbols and imports?")
    print(f"{obs.description}\n")

    overview = m.extract(
        "Analyze the loaded modules, symbols, and entry point. "
        "What kind of binary is this? What language is it written in? "
        "What notable library functions does it import?",
        response_model=BinaryOverview,
    )
    print(f"Type:     {overview.binary_type}")
    print(f"Language: {', '.join(overview.language_hints)}")
    print(f"Entry:    {overview.entry_function}")
    print(f"Imports:  {', '.join(overview.interesting_imports[:10])}")
    print(f"\n{overview.summary}\n")

    # ── Phase 2: Find interesting functions ──────────────────────────
    print(f"═══ Phase 2: Identify targets ═══\n")

    task_hint = ""
    if args.task:
        task_hint = f" Focus on functions related to: {args.task}"

    m.act(f"Set a breakpoint on the entry point and continue to it")

    obs2 = m.observe(
        f"Now that we're at the entry point, what functions look most "
        f"interesting for reverse engineering?{task_hint}"
    )
    print(f"{obs2.description}\n")
    print("Suggested next steps:")
    for i, action in enumerate(obs2.actions):
        print(f"  [{i}] {action.description}")
    print()

    # ── Phase 3: Deep dive ──────────────────────────────────────────
    print(f"═══ Phase 3: Deep dive (top {args.depth} functions) ═══\n")

    if args.task:
        # Use the REPL agent for open-ended investigation
        print(f"Task: {args.task}\n")
        result = m.repl_agent(
            f"You are analyzing the binary at {args.binary}. "
            f"Your task: {args.task}. "
            f"Here is what we know so far:\n{overview.summary}\n\n"
            f"Investigate the binary, set breakpoints on relevant functions, "
            f"step through them, and report your findings.",
            max_iterations=15,
        )
        print(f"\n{'─' * 60}")
        print(f"REPL agent result ({result.steps} steps, {result.code_blocks_executed} code blocks):")
        print(f"{result.result}")
        if result.variables:
            print(f"\nVariables discovered:")
            for k, v in result.variables.items():
                print(f"  {k} = {v}")
    else:
        # Explore the top N most interesting functions
        for i in range(min(args.depth, len(obs2.actions))):
            action = obs2.actions[i]
            print(f"── [{i + 1}/{args.depth}] {action.description} ──\n")

            m.act(action.description)

            analysis = m.extract(
                f"Analyze the current function in depth: what does it do, "
                f"what are its arguments, what does it return, what notable "
                f"functions does it call, and any security observations?",
                response_model=FunctionAnalysis,
            )

            print(f"  Function: {analysis.name}")
            print(f"  Purpose:  {analysis.purpose}")
            print(f"  Args:     {analysis.args_description}")
            print(f"  Returns:  {analysis.return_description}")
            print(f"  Calls:    {', '.join(analysis.notable_calls[:5])}")
            if analysis.security_notes:
                print(f"  Security: {analysis.security_notes}")
            print()

    print("═══ Done ═══")

    # Keep the dashboard alive so the user can browse/refresh
    if args.dashboard:
        m.wait_for_dashboard()
