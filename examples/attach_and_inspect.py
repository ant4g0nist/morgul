"""Attach to a running process, inspect its state, and detach.

This is the "bring your own process" pattern.  Instead of launching a
binary, attach to something already running — useful for inspecting
servers, daemons, or GUI applications.
"""

import sys

from pydantic import BaseModel

from morgul.core import Morgul


class ThreadInfo(BaseModel):
    """Summary of threads in the attached process."""
    num_threads: int
    thread_names: list[str]
    current_function: str
    stack_depth: int


def main():
    if len(sys.argv) < 2:
        print("Usage: python attach_and_inspect.py <pid_or_name>")
        print("  python attach_and_inspect.py 12345")
        print("  python attach_and_inspect.py Safari")
        sys.exit(1)

    target = sys.argv[1]

    with Morgul() as morgul:
        # Attach by PID or process name
        if target.isdigit():
            print(f"Attaching to PID {target}...")
            morgul.attach(int(target))
        else:
            print(f"Attaching to process '{target}'...")
            morgul.attach_by_name(target)

        # Observe the current state
        obs = morgul.observe("describe all threads and what they are doing")
        print(f"\nProcess state:\n{obs.description}\n")

        # Extract structured thread information
        info = morgul.extract(
            instruction=(
                "List all threads, their names, and what function each is in. "
                "Report the stack depth of the current thread."
            ),
            response_model=ThreadInfo,
        )
        print(f"Threads: {info.num_threads}")
        for name in info.thread_names:
            print(f"  - {name}")
        print(f"Current function: {info.current_function}")
        print(f"Stack depth: {info.stack_depth}")

        # Suggest what to look at next
        obs2 = morgul.observe("what is the most interesting thread to investigate?")
        print(f"\nSuggestion: {obs2.description}")
        if obs2.actions:
            print(f"  Try: {obs2.actions[0].command}")


if __name__ == "__main__":
    main()
