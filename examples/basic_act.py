"""Basic example: launch a target and use act() to set breakpoints and step."""

from morgul.core import Morgul

# Create Morgul with default config (reads morgul.toml if present)
with Morgul() as morgul:
    # Launch a target binary
    morgul.start("/tmp/morgul_test")

    # Use natural language to set a breakpoint
    result = morgul.act("set a breakpoint on main")
    print(f"Act result: {result.success} — {result.message}")
    for action in result.actions:
        print(f"  Executed: {action.command}")

    # Continue to the breakpoint
    result = morgul.act("continue execution")
    print(f"Continue: {result.success}")

    # Observe the current state
    obs = morgul.observe("what is the current state of the program?")
    print(f"\nObservation: {obs.description}")
    for action in obs.actions:
        print(f"  Suggested: {action.command} — {action.description}")

    # Step through a few instructions
    result = morgul.act("step over the next instruction")
    print(f"\nStep: {result.success} — {result.output}")
