"""Async API: use AsyncMorgul for concurrent or event-loop workflows.

AsyncMorgul provides the same primitives as Morgul but all methods are
coroutines.  Use this when integrating Morgul into an async application,
a Jupyter notebook, or a pipeline that already has an event loop.
"""

import asyncio
from typing import Optional

from pydantic import BaseModel

from morgul.core import AsyncMorgul


class FunctionSummary(BaseModel):
    name: str
    num_args: int
    return_type: Optional[str] = None
    description: str


async def main():
    async with AsyncMorgul() as morgul:
        morgul.start("/tmp/morgul_test")

        # All primitives are awaitable
        result = await morgul.act("set a breakpoint on main and continue")
        print(f"act: {result.success} — {result.message}")

        obs = await morgul.observe("what functions are reachable from here?")
        print(f"\nobserve: {obs.description}")
        for a in obs.actions:
            print(f"  → {a.command}")

        summary = await morgul.extract(
            instruction="Summarize the current function: name, arguments, purpose.",
            response_model=FunctionSummary,
        )
        print(f"\nextract: {summary.name}({summary.num_args} args)")
        print(f"  {summary.description}")

        # Run agent asynchronously
        steps = await morgul.agent(
            task="Step through the function and identify side effects.",
            strategy="depth-first",
            max_steps=10,
            timeout=30.0,
        )
        print(f"\nagent: {len(steps)} steps")
        for step in steps:
            print(f"  [{step.step_number}] {step.action}: {step.observation[:100]}")


if __name__ == "__main__":
    asyncio.run(main())
