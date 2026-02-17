"""Self-healing demonstration: Morgul recovers from command failures.

When act() generates code that fails (e.g. wrong API usage, bad address),
Morgul feeds the error back to the LLM and retries with a corrected approach.
This example shows the self-healing pipeline in action.

Prerequisites:
  ./examples/build_test_binary.sh   # builds /tmp/morgul_test

Run:
  PYTHONPATH="$(lldb -P)" uv run python examples/self_healing_demo.py
  PYTHONPATH="$(lldb -P)" uv run python examples/self_healing_demo.py --dashboard
"""

import argparse
import sys

from morgul.core import Morgul
from morgul.core.types.config import load_config
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


# ── CLI ─────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="Self-healing demo with Morgul.")
parser.add_argument("--dashboard", nargs="?", const=8546, type=int,
                    metavar="PORT", help="Open web dashboard (default port 8546)")
args = parser.parse_args()

llm_cb = None if args.dashboard else _on_llm

if args.dashboard:
    sys.stdout = open("/dev/null", "w")  # noqa: SIM115

# ── Demo ────────────────────────────────────────────────────────────────

config = load_config()
config.self_heal = True
config.healing.enabled = True
config.healing.max_retries = 3


def show_result(result):
    """Print an act() result, highlighting self-healing if it occurred."""
    print(f"\n  Success: {result.success}")
    if "Healed" in result.message:
        print(f"  >> Self-healing activated! <<")
        print(f"  Healing: {result.message[:200]}")
    print(f"  Output:  {result.output[:300]}")


with Morgul(config=config, llm_event_callback=llm_cb, dashboard_port=args.dashboard) as morgul:
    morgul.start("/tmp/morgul_test", args=["Morgul"])

    # ── Step 1: Breakpoint + continue (baseline — should work) ─────
    print("=" * 60)
    print("STEP 1: Set breakpoint on main (baseline)")
    print("=" * 60)

    result = morgul.act("set a breakpoint on main and continue to it")
    show_result(result)

    # ── Step 2: Step to a known point ──────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 2: Step over the add() call and read 'result'")
    print("=" * 60)

    result = morgul.act(
        "step over instructions until we pass the call to add(), "
        "then print the value of the 'result' variable"
    )
    show_result(result)

    # ── Step 3: Read stack memory (likely needs healing) ───────────
    # Reading raw memory via the bridge API is tricky — the LLM
    # often gets the API wrong on the first try.
    print("\n" + "=" * 60)
    print("STEP 3: Read 64 bytes from the stack pointer")
    print("=" * 60)

    result = morgul.act(
        "read and display 64 bytes of raw memory starting from "
        "the current stack pointer, formatted as hex dump"
    )
    show_result(result)

    # ── Step 4: Disassemble current function ───────────────────────
    print("\n" + "=" * 60)
    print("STEP 4: Disassemble current function")
    print("=" * 60)

    result = morgul.act("disassemble the current function we're stopped in")
    show_result(result)

    # Keep dashboard alive for browsing
    if args.dashboard:
        morgul.wait_for_dashboard()

# ── Step 5: Same tricky task but with healing disabled ─────────────
# Reading raw memory often fails on the first LLM attempt (wrong API
# usage).  With healing enabled (step 3) the error is fed back and the
# LLM self-corrects.  Here we disable healing so the first failure sticks.

print("\n" + "=" * 60)
print("STEP 5: Read raw memory WITHOUT self-healing")
print("=" * 60)

no_heal_config = load_config()
no_heal_config.self_heal = False

with Morgul(config=no_heal_config, llm_event_callback=llm_cb) as morgul2:
    morgul2.start("/tmp/morgul_test")
    morgul2.act("set a breakpoint on main and continue to it")

    result = morgul2.act(
        "read 32 bytes of raw memory from the address of the 'buf' "
        "local variable inside the greet function and print as hex"
    )
    show_result(result)
    if not result.success:
        print("  (No self-healing — the error was not retried)")

print("\n" + "=" * 60)
print("DEMO COMPLETE")
print("=" * 60)
