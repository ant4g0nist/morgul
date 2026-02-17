"""Complete end-to-end workflow: start, act, observe, extract, agent, end.

This example demonstrates every Morgul primitive in a single session, showing
how they compose into a full reverse engineering workflow.
"""

from typing import Optional

from pydantic import BaseModel

from morgul.core import Morgul


class FunctionProfile(BaseModel):
    """Profile of a function extracted by the LLM."""
    name: str
    num_basic_blocks: Optional[int] = None
    has_loops: bool = False
    calls: list[str] = []
    security_notes: str = ""


class SecurityAssessment(BaseModel):
    """High-level security assessment of the binary."""
    risk_level: str  # "low", "medium", "high", "critical"
    vulnerabilities_found: int
    summary: str
    recommendations: list[str] = []


with Morgul() as morgul:
    # === 1. Start ===
    print("=== Starting target ===")
    morgul.start("/tmp/morgul_test")

    # === 2. Act — set up the debugging session ===
    print("\n=== Setting up ===")
    result = morgul.act("set a breakpoint on main and continue")
    print(f"  {result.message}")

    result = morgul.act("step into the first function call")
    print(f"  {result.message}")

    # === 3. Observe — understand where we are ===
    print("\n=== Observing ===")
    obs = morgul.observe()
    print(f"  State: {obs.description}")
    print(f"  Suggestions: {len(obs.actions)}")
    for a in obs.actions[:3]:
        print(f"    - {a.command}: {a.description}")

    # === 4. Extract — pull structured data ===
    print("\n=== Extracting function profile ===")
    profile = morgul.extract(
        instruction=(
            "Analyze the current function. Identify its name, estimate the "
            "number of basic blocks, whether it has loops, what functions it "
            "calls, and any security-relevant observations."
        ),
        response_model=FunctionProfile,
    )
    print(f"  Function: {profile.name}")
    print(f"  Blocks: {profile.num_basic_blocks}")
    print(f"  Loops: {profile.has_loops}")
    print(f"  Calls: {', '.join(profile.calls) or 'none'}")
    if profile.security_notes:
        print(f"  Security: {profile.security_notes}")

    # === 5. Agent — autonomous deep analysis ===
    print("\n=== Running agent ===")
    steps = morgul.agent(
        task=(
            f"Starting from {profile.name}, trace the data flow of user input "
            "through the binary. Set breakpoints on called functions, examine "
            "their arguments, and determine if input is ever used unsafely."
        ),
        strategy="hypothesis-driven",
        max_steps=20,
        timeout=90.0,
    )
    print(f"  Completed in {len(steps)} steps")
    for step in steps:
        print(f"  [{step.step_number}] {step.action}")

    # === 6. Final extraction — security assessment ===
    print("\n=== Final assessment ===")
    assessment = morgul.extract(
        instruction=(
            "Based on everything observed so far, provide a security assessment. "
            "Rate the risk level, count vulnerabilities found, summarize findings, "
            "and list recommendations."
        ),
        response_model=SecurityAssessment,
    )
    print(f"  Risk: {assessment.risk_level}")
    print(f"  Vulnerabilities: {assessment.vulnerabilities_found}")
    print(f"  Summary: {assessment.summary}")
    for rec in assessment.recommendations:
        print(f"    - {rec}")

# Session automatically cleaned up by context manager
print("\n=== Done ===")
