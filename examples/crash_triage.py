"""Crash triage: attach to a crashed process and diagnose the root cause.

Run this when a process has crashed or is stopped in a debugger.  Morgul will
observe the crash state, extract a structured crash report, and optionally run
the agent for deeper analysis.

Usage:
  PYTHONPATH="$(lldb -P)" uv run python examples/crash_triage.py <process-name-or-pid>
  PYTHONPATH="$(lldb -P)" uv run python examples/crash_triage.py my_crashing_app
  PYTHONPATH="$(lldb -P)" uv run python examples/crash_triage.py 12345
"""

import argparse
from typing import Optional

from pydantic import BaseModel

from morgul.core import Morgul


class CrashReport(BaseModel):
    """Structured crash report extracted by the LLM."""
    crash_address: int
    faulting_instruction: str
    signal: str
    function_name: Optional[str] = None
    root_cause: str
    severity: str  # "low", "medium", "high", "critical"
    registers_of_interest: dict[str, int] = {}


parser = argparse.ArgumentParser(description="Crash triage: attach and diagnose.")
parser.add_argument("process", help="Process name or PID to attach to")
args = parser.parse_args()

with Morgul() as morgul:
    # Attach by PID if numeric, otherwise by name
    if args.process.isdigit():
        morgul.attach(int(args.process))
    else:
        morgul.attach_by_name(args.process)

    # 1. Observe the crash state
    obs = morgul.observe("describe the crash — what happened and why")
    print(f"Crash summary: {obs.description}\n")

    # 2. Extract a structured crash report
    report = morgul.extract(
        instruction=(
            "Analyze the crash state. Identify the faulting instruction, "
            "the signal, the function name, and the most likely root cause. "
            "Rate severity as low/medium/high/critical."
        ),
        response_model=CrashReport,
    )

    print(f"Address:    0x{report.crash_address:x}")
    print(f"Instruction:{report.faulting_instruction}")
    print(f"Signal:     {report.signal}")
    print(f"Function:   {report.function_name}")
    print(f"Root cause: {report.root_cause}")
    print(f"Severity:   {report.severity}")

    if report.registers_of_interest:
        print("\nRegisters of interest:")
        for name, val in report.registers_of_interest.items():
            print(f"  {name} = 0x{val:x}")

    # 3. If the crash looks complex, let the agent dig deeper
    if report.severity in ("high", "critical"):
        print("\nSeverity is high — running agent for deeper analysis...\n")
        steps = morgul.agent(
            task=(
                f"The process crashed at 0x{report.crash_address:x} in "
                f"{report.function_name or 'unknown'}. Root cause appears to be: "
                f"{report.root_cause}. Investigate further: check the call chain, "
                "look for attacker-controlled input, and determine exploitability."
            ),
            strategy="depth-first",
            max_steps=15,
            timeout=60.0,
        )
        for step in steps:
            print(f"  Step {step.step_number}: {step.action}")
            print(f"    → {step.observation[:200]}")
