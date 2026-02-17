"""Example: Run the autonomous agent using Claude Agent SDK backend.

Reads agentic_provider from morgul.toml. Run from a regular terminal (not inside Claude Code):

    PYTHONPATH="/opt/homebrew/Cellar/llvm/21.1.8_1/libexec/python3.14/site-packages" \
        uv run --python 3.14 python examples/agent_claude_sdk.py
"""

from morgul.core import Morgul

TARGET = "/tmp/morgul_test"
TASK = (
    "Analyze the main function of this binary. "
    "Identify what it does, what functions it calls, and summarize its behavior."
)

with Morgul() as morgul:
    morgul.start(TARGET)

    print(f"Target: {TARGET}")
    print(f"Task: {TASK}\n")

    steps = morgul.agent(task=TASK)

    print(f"\nCompleted in {len(steps)} steps:\n")
    for step in steps:
        print(f"  [{step.step_number}] {step.action}")
        if step.observation:
            print(f"      Result: {step.observation[:200]}")
        print()
