"""Demo of the new REPL agent features: llm_query, FINAL_VAR, iteration telemetry.

Showcases the RLM enhancements:
  1. Scaffold protection — bridge objects survive overwrite attempts
  2. Structured iteration telemetry — per-step code-block logging
  3. llm_query() — sub-queries to the LLM from within REPL code
  4. llm_query_batched() — concurrent sub-queries
  5. History compaction — automatic summarisation of long sessions
  6. FINAL_VAR() — return structured Python objects as the result

Usage:
  PYTHONPATH="$(lldb -P)" uv run python examples/repl_features_demo.py /path/to/binary
  PYTHONPATH="$(lldb -P)" uv run python examples/repl_features_demo.py /bin/ls
  PYTHONPATH="$(lldb -P)" uv run python examples/repl_features_demo.py /tmp/crackme -- XXX-XXXX-XXXX
  PYTHONPATH="$(lldb -P)" uv run python examples/repl_features_demo.py /bin/ls --dashboard
"""

import argparse
import sys

from morgul.core import Morgul
from morgul.core.events import ExecutionEvent, ExecutionEventType
from morgul.llm.events import LLMEvent


# ── Progress indicators ───────────────────────────────────────────────────

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


def _on_exec(event: ExecutionEvent) -> None:
    """Show execution events including sub-query calls."""
    if event.event_type == ExecutionEventType.REPL_STEP:
        step = event.metadata.get("step", "?")
        total = event.metadata.get("max_iterations", "?")
        sys.stderr.write(f"\n── Step {step}/{total} ──\n")
    elif event.event_type == ExecutionEventType.LLM_SUB_QUERY:
        prompt = event.metadata.get("prompt", "")[:80]
        batch = " (batch)" if event.metadata.get("batch") else ""
        sys.stderr.write(f"  [sub-query{batch}] {prompt}...\n")
    elif event.event_type == ExecutionEventType.CODE_END:
        if event.succeeded is False:
            sys.stderr.write(f"  [exec] FAILED ({event.duration:.2f}s)\n")
        else:
            sys.stderr.write(f"  [exec] ok ({event.duration:.2f}s)\n")


# ── Main ──────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(
    description="Demo the new REPL agent features (llm_query, FINAL_VAR, telemetry).",
)
parser.add_argument("binary", help="Path to the binary to analyze")
parser.add_argument(
    "target_args", nargs="*", default=None,
    help="Arguments to pass to the target binary (after --)",
)
parser.add_argument(
    "--iterations", type=int, default=15,
    help="Max REPL iterations (default: 15)",
)
parser.add_argument(
    "--dashboard", nargs="?", const=8546, type=int, metavar="PORT",
    help="Open web dashboard (default port 8546)",
)
args = parser.parse_args()

llm_cb = None if args.dashboard else _on_llm

if args.dashboard:
    sys.stdout = open("/dev/null", "w")  # noqa: SIM115

with Morgul(llm_event_callback=llm_cb, dashboard_port=args.dashboard) as m:
    m.start(args.binary, args=args.target_args)

    print("=" * 60)
    print("REPL Features Demo")
    print("=" * 60)
    print()

    # The task encourages the LLM to use the new features:
    #   - llm_query() for classifying individual functions
    #   - llm_query_batched() for parallel classification
    #   - FINAL_VAR() to return a structured dict as the result
    result = m.repl_agent(
        task=(
            "Enumerate the imported symbols from this binary. "
            "Group them by category (e.g. memory, I/O, string, math, process, other). "
            "\n\n"
            "Approach:\n"
            "1. List all imported symbols using the debugger.\n"
            "2. Use llm_query_batched() to classify batches of symbols into categories.\n"
            "3. Build a dict mapping category -> list of symbol names.\n"
            "4. Print a summary of each category and how many symbols it contains.\n"
            "5. Call FINAL_VAR('imports') to return the structured dict.\n"
            "\n"
            "Available helpers:\n"
            "- llm_query(prompt) -> str : ask a follow-up question\n"
            "- llm_query_batched(prompts) -> list[str] : ask up to 5 questions concurrently\n"
            "- FINAL_VAR('var_name') : return a namespace variable as structured output\n"
        ),
        max_iterations=args.iterations,
    )

    # ── Display results ───────────────────────────────────────────────
    print()
    print("=" * 60)
    print("Results")
    print("=" * 60)
    print(f"  Outcome:      {result.result}")
    print(f"  Steps:        {result.steps}")
    print(f"  Code blocks:  {result.code_blocks_executed}")
    print(f"  Iterations:   {len(result.iterations)}")

    if result.final_var is not None:
        print(f"\n  Structured output (FINAL_VAR):")
        if isinstance(result.final_var, dict):
            for category, symbols in result.final_var.items():
                count = len(symbols) if isinstance(symbols, list) else "?"
                print(f"    {category}: {count} symbols")
        else:
            print(f"    {result.final_var}")

    if result.variables:
        print(f"\n  Namespace variables:")
        for k, v in list(result.variables.items())[:10]:
            print(f"    {k} = {v[:80]}")

    # ── Telemetry summary ─────────────────────────────────────────────
    print(f"\n  Iteration telemetry:")
    for it in result.iterations:
        n_blocks = len(it.code_blocks)
        sub_queries = sum(b.llm_sub_queries for b in it.code_blocks)
        failed = sum(1 for b in it.code_blocks if not b.succeeded)
        status = f"{n_blocks} blocks"
        if sub_queries:
            status += f", {sub_queries} sub-queries"
        if failed:
            status += f", {failed} failed"
        print(f"    Step {it.step_number}: {status} ({it.duration:.2f}s)")

    print()
    print("=" * 60)
    print("Done")
    print("=" * 60)

    if args.dashboard:
        m.wait_for_dashboard()
