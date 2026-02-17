"""RLM-style REPL agent that writes Python code to debug with LLDB."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Optional

from morgul.core.agent.repl_prompts import REPL_NUDGE, REPL_SYSTEM_PROMPT, REPL_WRAP_UP
from morgul.core.events import (
    ExecutionEvent,
    ExecutionEventCallback,
    ExecutionEventType,
)
from morgul.core.primitives.executor import PythonExecutor, _truncate
from morgul.core.types.repl import REPLResult

if TYPE_CHECKING:
    from morgul.bridge.debugger import Debugger
    from morgul.bridge.process import Process
    from morgul.bridge.target import Target
    from morgul.llm import LLMClient

logger = logging.getLogger(__name__)

# Regex to extract ```python ... ``` code blocks from LLM responses.
_CODE_BLOCK_RE = re.compile(r"```python\s*\n(.*?)```", re.DOTALL)


def extract_code_blocks(text: str) -> list[str]:
    """Extract all ```python code blocks from *text*."""
    return _CODE_BLOCK_RE.findall(text)


class _DoneSignal(Exception):
    """Raised by the DONE() function to break out of execution."""

    def __init__(self, result: str):
        self.result = result


class REPLAgent:
    """RLM-style REPL agent that writes Python code to debug with LLDB.

    The LLM writes Python in ```python blocks. Code executes in a persistent
    namespace with live bridge objects (debugger, process, frame, etc.) and
    memory utilities. Variables persist across blocks. The LLM calls
    ``DONE("result")`` when finished.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        debugger: Debugger,
        target: Target,
        process: Process,
        max_iterations: int = 30,
        execution_callback: Optional[ExecutionEventCallback] = None,
    ):
        self.llm = llm_client
        self.max_iterations = max_iterations
        self._done = False
        self._result = ""
        self._code_blocks_executed = 0
        self._execution_callback = execution_callback

        # Use shared PythonExecutor for namespace and execution
        self.executor = PythonExecutor(
            debugger, target, process,
            execution_callback=execution_callback,
        )

        # Add DONE() to the namespace (REPL-specific)
        def _done_fn(result: str) -> None:
            """Signal that the analysis is complete."""
            raise _DoneSignal(result)

        self.executor.namespace["DONE"] = _done_fn

    @property
    def namespace(self) -> dict:
        """Expose the executor namespace for backward compatibility."""
        return self.executor.namespace

    def _execute(self, code: str) -> tuple[str, str]:
        """Execute *code* in the persistent namespace, capturing stdout/stderr.

        Returns (stdout, stderr).  If the code calls DONE(), sets self._done.
        """
        import contextlib
        import io
        import time
        import traceback

        if self._execution_callback is not None:
            self._execution_callback(ExecutionEvent(
                event_type=ExecutionEventType.CODE_START,
                code=code,
            ))

        t0 = time.monotonic()
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        succeeded = True

        try:
            with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
                exec(code, self.executor.namespace)  # noqa: S102
        except _DoneSignal as sig:
            self._done = True
            self._result = sig.result
            stdout_buf.write(f"\n[DONE] {sig.result}\n")
        except Exception:
            succeeded = False
            stderr_buf.write(traceback.format_exc())

        self._code_blocks_executed += 1
        self.executor.refresh()

        stdout = stdout_buf.getvalue()
        stderr = stderr_buf.getvalue()

        if self._execution_callback is not None:
            self._execution_callback(ExecutionEvent(
                event_type=ExecutionEventType.CODE_END,
                code=code,
                stdout=stdout,
                stderr=stderr,
                succeeded=succeeded,
                duration=time.monotonic() - t0,
            ))

        return stdout, stderr

    async def run(self, task: str) -> REPLResult:
        """Main loop: prompt → extract code → exec → feedback → repeat."""
        from morgul.llm.types import ChatMessage

        system_prompt = REPL_SYSTEM_PROMPT.format(task=task)

        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=f"Begin working on the task:\n{task}"),
        ]

        for step in range(1, self.max_iterations + 1):
            logger.debug("REPL agent step %d/%d", step, self.max_iterations)

            if self._execution_callback is not None:
                self._execution_callback(ExecutionEvent(
                    event_type=ExecutionEventType.REPL_STEP,
                    metadata={
                        "step": step,
                        "max_iterations": self.max_iterations,
                    },
                ))

            response = await self.llm.chat(messages=messages)
            content = response.content or ""

            # Emit the LLM response for the display
            if self._execution_callback is not None:
                self._execution_callback(ExecutionEvent(
                    event_type=ExecutionEventType.LLM_RESPONSE,
                    metadata={"content": content, "step": step},
                ))

            # Append the assistant's response
            messages.append(ChatMessage(role="assistant", content=content))

            code_blocks = extract_code_blocks(content)

            if not code_blocks:
                # LLM is thinking without writing code — nudge it
                messages.append(ChatMessage(role="user", content=REPL_NUDGE))
                continue

            # Execute each code block and collect results
            results_text_parts: list[str] = []
            for code in code_blocks:
                stdout, stderr = self._execute(code)
                part = f"```python\n{code}```\n"
                if stdout.strip():
                    part += f"stdout:\n```\n{_truncate(stdout)}\n```\n"
                if stderr.strip():
                    part += f"stderr:\n```\n{_truncate(stderr)}\n```\n"
                if not stdout.strip() and not stderr.strip():
                    part += "(no output)\n"
                results_text_parts.append(part)

                if self._done:
                    break

            feedback = "Execution results:\n\n" + "\n".join(results_text_parts)

            # Nudge the LLM to wrap up when approaching the iteration limit
            remaining = self.max_iterations - step
            if remaining <= 2 and not self._done:
                feedback += f"\n\n{REPL_WRAP_UP}"

            messages.append(ChatMessage(role="user", content=feedback))

            if self._done:
                return REPLResult(
                    result=self._result,
                    steps=step,
                    code_blocks_executed=self._code_blocks_executed,
                    variables=self._snapshot_variables(),
                )

        # Max iterations reached
        return REPLResult(
            result="Max iterations reached without DONE() being called.",
            steps=self.max_iterations,
            code_blocks_executed=self._code_blocks_executed,
            variables=self._snapshot_variables(),
        )

    def _snapshot_variables(self) -> dict[str, str]:
        """Capture user-defined variables from the namespace as strings."""
        skip = {
            "debugger", "target", "process", "thread", "frame",
            "read_string", "read_pointer", "read_uint8", "read_uint16",
            "read_uint32", "read_uint64", "search_memory", "DONE",
            "struct", "binascii", "json", "re", "collections", "math",
            "__builtins__",
            # Python builtins we injected
            "print", "range", "len", "int", "str", "float", "bool",
            "list", "dict", "tuple", "set", "bytes", "bytearray",
            "hex", "oct", "bin", "abs", "min", "max", "sum",
            "sorted", "reversed", "enumerate", "zip", "map", "filter",
            "isinstance", "type", "hasattr", "getattr", "setattr",
            "repr", "chr", "ord", "format", "round", "pow", "divmod",
            "hash", "id", "dir", "vars", "any", "all", "next", "iter",
            "slice", "Exception", "ValueError", "TypeError", "KeyError",
            "IndexError", "AttributeError", "RuntimeError", "StopIteration",
            "True", "False", "None",
        }
        result: dict[str, str] = {}
        for key, value in self.executor.namespace.items():
            if key.startswith("_") or key in skip:
                continue
            try:
                result[key] = repr(value)[:200]
            except Exception:
                result[key] = "<unrepresentable>"
        return result
