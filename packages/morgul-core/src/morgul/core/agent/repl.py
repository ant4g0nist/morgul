"""RLM REPL agent that writes Python code to debug with LLDB."""

from __future__ import annotations

import asyncio
import contextlib
import io
import logging
import re
import time
import traceback
from typing import TYPE_CHECKING, Optional

from morgul.core.agent.repl_logger import REPLLogger
from morgul.core.agent.repl_prompts import (
    REPL_NUDGE,
    REPL_SYSTEM_PROMPT,
    REPL_WRAP_UP,
    format_tools_section,
)
from morgul.core.events import (
    ExecutionEvent,
    ExecutionEventCallback,
    ExecutionEventType,
)
from morgul.core.primitives.executor import RESERVED_NAMES, PythonExecutor, _truncate
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


class _FinalVarSignal(Exception):
    """Raised by FINAL_VAR() to return a structured variable."""

    def __init__(self, var_name: str, value: object):
        self.var_name = var_name
        self.value = value


class REPLAgent:
    """RLM REPL agent that writes Python code to debug with LLDB.

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
        llm_query_budget: int = 5,
        llm_query_timeout: float = 30.0,
        compaction_threshold_pct: float = 0.75,
        context_window_tokens: int = 200_000,
        log_path: Optional[str] = None,
        tools: Optional[dict] = None,
        persistent: bool = False,
    ):
        self.llm = llm_client
        self.max_iterations = max_iterations
        self._done = False
        self._result = ""
        self._code_blocks_executed = 0
        self._execution_callback = execution_callback
        self._llm_query_budget = llm_query_budget
        self._llm_query_timeout = llm_query_timeout
        self._llm_query_calls_this_iteration = 0
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._compaction_threshold = int(context_window_tokens * compaction_threshold_pct)
        self._context_window_tokens = context_window_tokens

        # Use shared PythonExecutor for namespace and execution
        self.executor = PythonExecutor(
            debugger, target, process,
            execution_callback=execution_callback,
        )

        # Add DONE() to the namespace (REPL-specific)
        def _done_fn(result: str) -> None:
            """Signal that the analysis is complete."""
            raise _DoneSignal(result)

        self.executor.update_scaffold("DONE", _done_fn)

        # Add FINAL_VAR() to the namespace
        self._last_final_var: Optional[object] = None

        def _final_var_fn(variable_name: str) -> None:
            """Return a structured variable as the result."""
            if variable_name not in self.executor.namespace:
                raise NameError(f"Variable {variable_name!r} not found in namespace")
            value = self.executor.namespace[variable_name]
            raise _FinalVarSignal(variable_name, value)

        self.executor.update_scaffold("FINAL_VAR", _final_var_fn)

        # Register llm_query and llm_query_batched in scaffold
        self.executor.update_scaffold("llm_query", self._make_llm_query_fn())
        self.executor.update_scaffold("llm_query_batched", self._make_llm_query_batched_fn())

        from pathlib import Path

        self._logger = REPLLogger(log_path=Path(log_path) if log_path else None)

        # Custom tools injection
        self._tool_descriptions: list[tuple[str, str]] = []
        if tools:
            self._tool_descriptions = self.executor.inject_tools(tools)

        # Multi-turn persistence
        self.persistent = persistent
        self._message_history: list = []

    @property
    def namespace(self) -> dict:
        """Expose the executor namespace for backward compatibility."""
        return self.executor.namespace

    def _make_llm_query_fn(self):
        """Create the llm_query() closure injected into the REPL namespace."""
        def llm_query(prompt: str, timeout: Optional[float] = None) -> str:
            """Ask the LLM a sub-question from within REPL code."""
            if self._llm_query_calls_this_iteration >= self._llm_query_budget:
                raise RuntimeError(
                    f"llm_query budget exceeded: {self._llm_query_budget} calls per iteration"
                )
            if self._loop is None:
                raise RuntimeError("llm_query is only available during run()")

            effective_timeout = timeout if timeout is not None else self._llm_query_timeout

            from morgul.llm.types import ChatMessage

            async def _do_query():
                resp = await self.llm.chat(messages=[
                    ChatMessage(role="user", content=prompt),
                ])
                return resp.content or ""

            future = asyncio.run_coroutine_threadsafe(_do_query(), self._loop)
            try:
                result = future.result(timeout=effective_timeout)
            except TimeoutError:
                future.cancel()
                raise TimeoutError(
                    f"llm_query timed out after {effective_timeout}s"
                )

            self._llm_query_calls_this_iteration += 1

            # Emit event
            if self._execution_callback is not None:
                self._execution_callback(ExecutionEvent(
                    event_type=ExecutionEventType.LLM_SUB_QUERY,
                    metadata={"prompt": prompt[:200], "response": result[:200]},
                ))

            return result

        return llm_query

    def _make_llm_query_batched_fn(self):
        """Create the llm_query_batched() closure for concurrent sub-queries."""
        _MAX_BATCH_SIZE = 5

        def llm_query_batched(prompts: list[str], timeout: Optional[float] = None) -> list[str]:
            """Ask multiple sub-questions concurrently."""
            if len(prompts) > _MAX_BATCH_SIZE:
                raise ValueError(
                    f"Batch size {len(prompts)} exceeds maximum of {_MAX_BATCH_SIZE}"
                )
            needed = self._llm_query_calls_this_iteration + len(prompts)
            if needed > self._llm_query_budget:
                raise RuntimeError(
                    f"llm_query budget exceeded: need {len(prompts)} calls but only "
                    f"{self._llm_query_budget - self._llm_query_calls_this_iteration} remaining"
                )
            if self._loop is None:
                raise RuntimeError("llm_query_batched is only available during run()")

            effective_timeout = timeout if timeout is not None else 60.0

            from morgul.llm.types import ChatMessage

            async def _do_batch():
                async def _single(prompt: str) -> str:
                    resp = await self.llm.chat(messages=[
                        ChatMessage(role="user", content=prompt),
                    ])
                    return resp.content or ""

                return await asyncio.gather(*[_single(p) for p in prompts])

            future = asyncio.run_coroutine_threadsafe(_do_batch(), self._loop)
            try:
                results = future.result(timeout=effective_timeout)
            except TimeoutError:
                future.cancel()
                raise TimeoutError(
                    f"llm_query_batched timed out after {effective_timeout}s"
                )

            self._llm_query_calls_this_iteration += len(prompts)

            # Emit events for each sub-query
            if self._execution_callback is not None:
                for prompt, result in zip(prompts, results):
                    self._execution_callback(ExecutionEvent(
                        event_type=ExecutionEventType.LLM_SUB_QUERY,
                        metadata={
                            "prompt": prompt[:200],
                            "response": result[:200],
                            "batch": True,
                        },
                    ))

            return list(results)

        return llm_query_batched

    def _execute_sync(self, code: str) -> tuple[str, str]:
        """Pure sync execution of code. Called from thread pool during run().

        Returns (stdout, stderr). If the code calls DONE(), sets self._done.
        """
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
        except _FinalVarSignal as sig:
            self._done = True
            self._result = f"FINAL_VAR({sig.var_name!r})"
            self._last_final_var = sig.value
            stdout_buf.write(f"\n[FINAL_VAR] {sig.var_name} = {repr(sig.value)[:200]}\n")
        except Exception:
            succeeded = False
            stderr_buf.write(traceback.format_exc())

        self._code_blocks_executed += 1
        self.executor._restore_scaffold()
        self.executor.refresh()

        return stdout_buf.getvalue(), stderr_buf.getvalue()

    def _execute(self, code: str) -> tuple[str, str]:
        """Sync wrapper — emits events around _execute_sync. For backward compat."""
        if self._execution_callback is not None:
            self._execution_callback(ExecutionEvent(
                event_type=ExecutionEventType.CODE_START,
                code=code,
            ))

        t0 = time.monotonic()
        stdout, stderr = self._execute_sync(code)
        succeeded = not stderr.strip() or self._done

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

    async def _execute_async(self, code: str) -> tuple[str, str]:
        """Async execution — runs exec in thread pool to free the event loop.

        This allows llm_query() inside exec to call back into the event loop.
        """
        if self._execution_callback is not None:
            self._execution_callback(ExecutionEvent(
                event_type=ExecutionEventType.CODE_START,
                code=code,
            ))

        t0 = time.monotonic()
        loop = asyncio.get_running_loop()
        stdout, stderr = await loop.run_in_executor(None, self._execute_sync, code)
        succeeded = not stderr.strip() or self._done

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

    @staticmethod
    def _estimate_tokens(messages) -> int:
        """Rough token estimate: ~4 chars per token."""
        return sum(len(m.content) for m in messages) // 4

    async def _compact_history(self, messages) -> list:
        """Summarize older messages to free context space."""
        from morgul.llm.types import ChatMessage

        if len(messages) <= 5:
            return messages

        system = messages[0]
        recent = messages[-4:]
        middle = messages[1:-4]

        summary_text = "\n".join(
            f"[{m.role}]: {m.content[:500]}" for m in middle
        )
        summary_resp = await self.llm.chat(messages=[
            ChatMessage(
                role="user",
                content=(
                    "Summarize the following REPL session history concisely, "
                    "preserving key findings, variable names, and important results:\n\n"
                    + summary_text
                ),
            ),
        ])
        compacted = ChatMessage(
            role="user",
            content=f"[Compacted history]\n{summary_resp.content or ''}",
        )
        return [system, compacted] + recent

    async def run(self, task: str) -> REPLResult:
        """Main loop: prompt → extract code → exec → feedback → repeat."""
        from morgul.llm.types import ChatMessage

        # Reset per-turn state (but NOT namespace/history for persistent mode)
        self._done = False
        self._result = ""
        self._last_final_var = None

        # Refresh bridge objects to current debugger state
        self.executor.refresh()

        self._loop = asyncio.get_running_loop()

        tools_section = format_tools_section(self._tool_descriptions)
        system_prompt = REPL_SYSTEM_PROMPT.format(
            task=task,
            llm_query_budget=self._llm_query_budget,
            custom_tools_section=tools_section,
        )

        # If persistent and we have prior history, restore it
        if self.persistent and self._message_history:
            messages = list(self._message_history)
            messages.append(ChatMessage(role="user", content=f"New task:\n{task}"))
        else:
            messages: list[ChatMessage] = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=f"Begin working on the task:\n{task}"),
            ]

        for step in range(1, self.max_iterations + 1):
            logger.debug("REPL agent step %d/%d", step, self.max_iterations)

            # Compact history if approaching context limit
            if self._estimate_tokens(messages) > self._compaction_threshold:
                messages = await self._compact_history(messages)

            # Reset per-iteration llm_query budget
            self._llm_query_calls_this_iteration = 0

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

            # Begin iteration tracking
            self._logger.begin_iteration(step, content)

            # Execute each code block and collect results
            results_text_parts: list[str] = []
            for code in code_blocks:
                self._logger.begin_code_block()
                sub_queries_before = self._llm_query_calls_this_iteration
                stdout, stderr = await self._execute_async(code)
                succeeded = not stderr.strip() or self._done
                self._logger.end_code_block(
                    code=code, stdout=stdout, stderr=stderr, succeeded=succeeded,
                    llm_sub_queries=self._llm_query_calls_this_iteration - sub_queries_before,
                )
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

            self._logger.end_iteration()

            feedback = "Execution results:\n\n" + "\n".join(results_text_parts)

            # Nudge the LLM to wrap up when approaching the iteration limit
            remaining = self.max_iterations - step
            if remaining <= 2 and not self._done:
                feedback += f"\n\n{REPL_WRAP_UP}"

            messages.append(ChatMessage(role="user", content=feedback))

            if self._done:
                if self.persistent:
                    self._message_history = list(messages)
                return REPLResult(
                    result=self._result,
                    steps=step,
                    code_blocks_executed=self._code_blocks_executed,
                    variables=self._snapshot_variables(),
                    iterations=self._logger.iterations,
                    final_var=self._serialize_final_var(),
                )

        # Max iterations reached
        if self.persistent:
            self._message_history = list(messages)
        return REPLResult(
            result="Max iterations reached without DONE() being called.",
            steps=self.max_iterations,
            code_blocks_executed=self._code_blocks_executed,
            variables=self._snapshot_variables(),
            iterations=self._logger.iterations,
        )

    def _serialize_final_var(self):
        """Serialize _last_final_var for inclusion in REPLResult."""
        if self._last_final_var is None:
            return None
        import json as _json
        try:
            _json.dumps(self._last_final_var)
            return self._last_final_var
        except (TypeError, ValueError):
            return repr(self._last_final_var)

    def _snapshot_variables(self) -> dict[str, str]:
        """Capture user-defined variables from the namespace as strings."""
        skip = self.executor._scaffold.keys()
        result: dict[str, str] = {}
        for key, value in self.executor.namespace.items():
            if key.startswith("_") or key in skip:
                continue
            try:
                result[key] = repr(value)[:200]
            except Exception:
                result[key] = "<unrepresentable>"
        return result
