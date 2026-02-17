"""Vulnerability triage with Morgul.

Given a binary and a crash-inducing input, let the AI autonomously
analyze the crash, find the root cause, and produce a vulnerability report.

No hardcoded hints — the agent discovers the vulnerability class,
root cause, and exploitability on its own.

Prerequisites:
  ./examples/vuln_targets/build.sh   # builds /tmp/imgparse + /tmp/crash_input.mgl

Run:
  PYTHONPATH="$(lldb -P)" uv run python examples/vuln_triage.py
  PYTHONPATH="$(lldb -P)" uv run python examples/vuln_triage.py --dashboard
  PYTHONPATH="$(lldb -P)" uv run python examples/vuln_triage.py --target /tmp/imgparse --input /tmp/crash_input.mgl
"""

import argparse
import sys
from typing import Optional

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


# ── Extraction schemas (generic — no target-specific fields) ────────────

class CrashAnalysis(BaseModel):
    """Initial crash triage."""
    crash_address: int
    faulting_instruction: str
    access_type: str              # "read", "write", "exec"
    signal: str                   # "SIGSEGV", "SIGBUS", "SIGABRT", etc.
    function_name: Optional[str] = None
    module_name: Optional[str] = None
    description: str
    registers_of_interest: dict[str, str] = {}


class VulnerabilityReport(BaseModel):
    """Final vulnerability report."""
    bug_class: str                # "heap-overflow", "use-after-free", etc.
    root_cause: str
    attack_surface: str
    corrupted_state: str
    exploitability: str           # "likely", "possible", "unlikely"
    exploitability_reasoning: str
    suggested_fix: str
    severity: str                 # "critical", "high", "medium", "low"
    cve_analogues: list[str] = []


# ── CLI ──────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="Vulnerability triage with Morgul.")
parser.add_argument("--target", default="/tmp/imgparse", help="Path to the vulnerable binary")
parser.add_argument("--input", default="/tmp/crash_input.mgl", help="Crash-inducing input file")
parser.add_argument("--iterations", type=int, default=20, help="Max REPL agent iterations")
parser.add_argument("--dashboard", nargs="?", const=8546, type=int,
                    metavar="PORT", help="Open web dashboard (default port 8546)")
args = parser.parse_args()

TARGET = args.target
CRASH_IN = args.input

llm_cb = None if args.dashboard else _on_llm

if args.dashboard:
    sys.stdout = open("/dev/null", "w")  # noqa: SIM115

# ── Analysis ─────────────────────────────────────────────────────────────

with Morgul(llm_event_callback=llm_cb, dashboard_port=args.dashboard) as morgul:

    # ── Phase 1: Crash reproduction ──────────────────────────────────
    print("=" * 60)
    print("PHASE 1: Crash reproduction")
    print("=" * 60)

    morgul.start(TARGET, args=[CRASH_IN])
    morgul.act("continue the process and let it run until it crashes or stops")

    obs = morgul.observe("what happened? describe the crash or stop reason")
    print(f"\n  {obs.description}\n")

    # ── Phase 2: Structured crash analysis ───────────────────────────
    print("=" * 60)
    print("PHASE 2: Crash analysis")
    print("=" * 60)

    crash = morgul.extract(
        instruction="analyze the crash — crash address, faulting instruction, "
                    "access type, signal, function, and any suspicious register values",
        response_model=CrashAnalysis,
    )

    print(f"\n  Address:     0x{crash.crash_address:x}")
    print(f"  Instruction: {crash.faulting_instruction}")
    print(f"  Access:      {crash.access_type}")
    print(f"  Signal:      {crash.signal}")
    print(f"  Function:    {crash.function_name or 'unknown'}")
    print(f"  Description: {crash.description}")
    if crash.registers_of_interest:
        print(f"  Key registers:")
        for reg, val in crash.registers_of_interest.items():
            print(f"    {reg} = {val}")

    # ── Phase 3: Autonomous deep analysis ────────────────────────────
    print("\n" + "=" * 60)
    print("PHASE 3: Autonomous analysis (repl_agent)")
    print("=" * 60)

    repl_result = morgul.repl_agent(
        task=(
            f"The process crashed at 0x{crash.crash_address:x} "
            f"({crash.signal} in {crash.function_name or 'unknown'}). "
            f"Crash description: {crash.description}\n\n"
            "Your job:\n"
            "1. Walk the call stack to find the application code responsible\n"
            "2. Inspect local variables, structs, and memory around the crash\n"
            "3. Identify the bug class (overflow, UAF, type confusion, etc.)\n"
            "4. Find the root cause — what input/field triggers it and why\n"
            "5. Determine what memory was corrupted and the consequences\n"
            "6. Assess exploitability\n"
        ),
        max_iterations=args.iterations,
    )

    print(f"\n  Completed in {repl_result.steps} steps "
          f"({repl_result.code_blocks_executed} code blocks)")
    print(f"\n  {repl_result.result}")

    # ── Phase 4: Final vulnerability report ──────────────────────────
    print("\n" + "=" * 60)
    print("PHASE 4: Vulnerability report")
    print("=" * 60)

    report = morgul.extract(
        instruction=(
            "Based on everything discovered so far, produce a vulnerability report. "
            f"Agent findings: {repl_result.result}\n\n"
            "Classify the bug, explain the root cause, describe the attack surface, "
            "what state gets corrupted, assess exploitability with reasoning, "
            "suggest a fix, rate severity, and list any similar known CVEs."
        ),
        response_model=VulnerabilityReport,
    )

    print(f"""
  ┌─────────────────────────────────────────────────────────┐
  │  VULNERABILITY REPORT                                   │
  ├─────────────────────────────────────────────────────────┤
  │  Bug class:      {report.bug_class:<39s} │
  │  Severity:       {report.severity:<39s} │
  │  Exploitability: {report.exploitability:<39s} │
  └─────────────────────────────────────────────────────────┘

  Root cause:
    {report.root_cause}

  Attack surface:
    {report.attack_surface}

  Corrupted state:
    {report.corrupted_state}

  Exploitability reasoning:
    {report.exploitability_reasoning}

  Suggested fix:
    {report.suggested_fix}""")

    if report.cve_analogues:
        print(f"\n  Similar CVEs:")
        for cve in report.cve_analogues:
            print(f"    - {cve}")

    print("\n" + "=" * 60)
    print("TRIAGE COMPLETE")
    print("=" * 60)

    # Keep the dashboard alive so the user can browse/refresh
    if args.dashboard:
        morgul.wait_for_dashboard()
