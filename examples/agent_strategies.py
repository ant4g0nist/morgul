"""Compare agent strategies on the same target.

Morgul supports three agent strategies:
  - depth-first:       Follow one code path deeply before backtracking.
  - breadth-first:     Survey all reachable functions, then dive in.
  - hypothesis-driven: Form a hypothesis, test it, revise.

This example runs the same task with each strategy and compares the results.
"""

from morgul.core import Morgul

TARGET = "/tmp/morgul_test"
TASK = (
    "Analyze this binary for functions that handle string input. "
    "Determine if any of them have potential buffer overflow vulnerabilities."
)
MAX_STEPS = 15
TIMEOUT = 60.0

strategies = ["depth-first", "breadth-first", "hypothesis-driven"]

for strategy in strategies:
    print(f"\n{'=' * 60}")
    print(f"  Strategy: {strategy}")
    print(f"{'=' * 60}\n")

    with Morgul() as morgul:
        morgul.start(TARGET)

        steps = morgul.agent(
            task=TASK,
            strategy=strategy,
            max_steps=MAX_STEPS,
            timeout=TIMEOUT,
        )

        print(f"Completed in {len(steps)} steps:\n")
        for step in steps:
            print(f"  [{step.step_number}] {step.action}")
            if step.reasoning:
                print(f"      Why: {step.reasoning[:120]}")
            print(f"      Saw: {step.observation[:120]}")
            print()
