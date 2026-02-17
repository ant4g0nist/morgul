"""Quick smoke test: launch a target and use act/observe."""

from morgul.core import Morgul

with Morgul() as m:
    m.start("/tmp/test_morgul")

    # Natural language → LLDB commands
    result = m.act("set a breakpoint on the add function")
    print(f"Act: {result.success} — {result.message}")

    result = m.act("continue execution")
    print(f"Continue: {result.success}")

    # Observe what's happening
    obs = m.observe("what are the function arguments?")
    print(f"\nObservation: {obs.description}")
    for a in obs.actions:
        print(f"  → {a.command}: {a.description}")

    # Extract structured data
    from pydantic import BaseModel

    class FunctionArgs(BaseModel):
        arg1: int
        arg2: int
        function_name: str

    args = m.extract("what are the arguments to the current function?", FunctionArgs)
    print(f"\nExtracted: {args.function_name}({args.arg1}, {args.arg2})")
