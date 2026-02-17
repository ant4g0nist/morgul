"""Observe-then-act pattern: let Morgul suggest actions, then execute them.

This is the recommended workflow when you are exploring an unfamiliar binary.
Instead of guessing LLDB commands, ask Morgul what is interesting and act on
its suggestions.
"""

from morgul.core import Morgul

with Morgul() as morgul:
    morgul.start("/tmp/morgul_test")

    # Set an initial breakpoint and run to it
    morgul.act("set a breakpoint on main and continue")

    # --- Phase 1: Observe the state ---
    obs = morgul.observe()
    print(f"State: {obs.description}\n")
    print("Suggested actions:")
    for i, action in enumerate(obs.actions):
        print(f"  [{i}] {action.command} — {action.description}")

    # --- Phase 2: Act on the top suggestion ---
    if obs.actions:
        top = obs.actions[0]
        print(f"\nExecuting top suggestion: {top.command}")
        result = morgul.act(top.description)
        print(f"  Success: {result.success}")
        print(f"  Output: {result.output[:200]}")

    # --- Phase 3: Targeted observe after acting ---
    obs2 = morgul.observe("did the previous action reveal anything interesting?")
    print(f"\nFollow-up: {obs2.description}")
    for action in obs2.actions:
        print(f"  Next: {action.command} — {action.description}")
