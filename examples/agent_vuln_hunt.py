"""Example: autonomous agent mode for vulnerability hunting."""

from morgul.core import Morgul

with Morgul() as morgul:
    morgul.start("/tmp/morgul_test")

    # Run the autonomous agent with hypothesis-driven strategy
    steps = morgul.agent(
        task=(
            "Analyze this binary for potential buffer overflow vulnerabilities. "
            "Look for functions that handle user input (read, scanf, gets, strcpy, etc.). "
            "Set breakpoints on suspicious functions, examine their arguments, "
            "and determine if there are any unchecked buffer sizes."
        ),
        strategy="hypothesis-driven",
        max_steps=30,
        timeout=120.0,
    )

    print(f"Agent completed in {len(steps)} steps:\n")
    for step in steps:
        print(f"Step {step.step_number}: {step.action}")
        print(f"  Observation: {step.observation[:200]}")
        if step.reasoning:
            print(f"  Reasoning: {step.reasoning[:200]}")
        print()
