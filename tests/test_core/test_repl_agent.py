"""Tests for the REPL agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from morgul.core.agent.repl import REPLAgent, extract_code_blocks
from morgul.core.types.repl import REPLResult
from morgul.llm.types import LLMResponse, Usage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(content: str) -> LLMResponse:
    return LLMResponse(
        content=content,
        tool_calls=None,
        usage=Usage(input_tokens=100, output_tokens=50),
    )


def _mock_llm(*responses: str) -> AsyncMock:
    """Return a mock LLM client that yields the given responses in order."""
    client = AsyncMock()
    client.chat.side_effect = [_make_response(r) for r in responses]
    return client


def _mock_process():
    frame = MagicMock()
    frame.pc = 0x100003F00
    frame.function_name = "main"
    frame.variables.return_value = []
    frame.evaluate_expression.return_value = "42"
    frame.disassemble.return_value = "push rbp"
    frame.registers = []

    thread = MagicMock()
    thread.selected_frame = frame
    thread.get_frames.return_value = [frame]

    process = MagicMock()
    process.selected_thread = thread
    process.read_memory.return_value = b"\xde\xad\xbe\xef" * 16
    process.pid = 12345
    process.state = "stopped"
    process._sb = MagicMock()
    return process


def _make_agent(llm, max_iterations=10):
    debugger = MagicMock()
    target = MagicMock()
    process = _mock_process()
    return REPLAgent(
        llm_client=llm,
        debugger=debugger,
        target=target,
        process=process,
        max_iterations=max_iterations,
    )


# ---------------------------------------------------------------------------
# extract_code_blocks
# ---------------------------------------------------------------------------

class TestExtractCodeBlocks:
    def test_single_block(self):
        text = "Here is code:\n```python\nprint('hello')\n```\nDone."
        blocks = extract_code_blocks(text)
        assert len(blocks) == 1
        assert "print('hello')" in blocks[0]

    def test_multiple_blocks(self):
        text = (
            "Step 1:\n```python\nx = 1\n```\n"
            "Step 2:\n```python\ny = x + 1\n```\n"
        )
        blocks = extract_code_blocks(text)
        assert len(blocks) == 2
        assert "x = 1" in blocks[0]
        assert "y = x + 1" in blocks[1]

    def test_no_blocks(self):
        text = "I'm thinking about this problem..."
        blocks = extract_code_blocks(text)
        assert blocks == []

    def test_non_python_block_ignored(self):
        text = "```c\nint main() {}\n```"
        blocks = extract_code_blocks(text)
        assert blocks == []

    def test_multiline_code(self):
        text = "```python\nfor i in range(10):\n    print(i)\n```"
        blocks = extract_code_blocks(text)
        assert len(blocks) == 1
        assert "for i in range(10):" in blocks[0]


# ---------------------------------------------------------------------------
# REPLAgent namespace
# ---------------------------------------------------------------------------

class TestNamespace:
    def test_bridge_objects_present(self):
        agent = _make_agent(_mock_llm())
        ns = agent.namespace
        assert "debugger" in ns
        assert "target" in ns
        assert "process" in ns
        assert "thread" in ns
        assert "frame" in ns

    def test_memory_utilities_present(self):
        agent = _make_agent(_mock_llm())
        ns = agent.namespace
        assert callable(ns["read_string"])
        assert callable(ns["read_pointer"])
        assert callable(ns["read_uint8"])
        assert callable(ns["read_uint16"])
        assert callable(ns["read_uint32"])
        assert callable(ns["read_uint64"])
        assert callable(ns["search_memory"])

    def test_stdlib_present(self):
        agent = _make_agent(_mock_llm())
        ns = agent.namespace
        import struct
        assert ns["struct"] is struct

    def test_done_function_present(self):
        agent = _make_agent(_mock_llm())
        assert callable(agent.namespace["DONE"])


# ---------------------------------------------------------------------------
# Code execution
# ---------------------------------------------------------------------------

class TestExecute:
    def test_stdout_capture(self):
        agent = _make_agent(_mock_llm())
        stdout, stderr = agent._execute("print('hello world')")
        assert "hello world" in stdout
        assert stderr == ""

    def test_stderr_on_error(self):
        agent = _make_agent(_mock_llm())
        stdout, stderr = agent._execute("1/0")
        assert "ZeroDivisionError" in stderr

    def test_variable_persistence(self):
        agent = _make_agent(_mock_llm())
        agent._execute("my_var = 42")
        stdout, _ = agent._execute("print(my_var)")
        assert "42" in stdout

    def test_done_signal(self):
        agent = _make_agent(_mock_llm())
        stdout, stderr = agent._execute('DONE("analysis complete")')
        assert agent._done is True
        assert agent._result == "analysis complete"
        assert "[DONE]" in stdout

    def test_code_blocks_counter(self):
        agent = _make_agent(_mock_llm())
        agent._execute("x = 1")
        agent._execute("y = 2")
        assert agent._code_blocks_executed == 2

    def test_thread_frame_refresh(self):
        agent = _make_agent(_mock_llm())
        original_frame = agent.namespace["frame"]
        # Execute code that doesn't change state
        agent._execute("x = 1")
        # Frame should still be present (refreshed from process)
        assert agent.namespace["frame"] is not None


# ---------------------------------------------------------------------------
# Full run loop
# ---------------------------------------------------------------------------

class TestRun:
    @pytest.mark.asyncio
    async def test_done_stops_loop(self):
        llm = _mock_llm(
            "Let me check:\n```python\nprint('checking')\n```",
            "Found it:\n```python\nDONE('overflow is 956 bytes')\n```",
        )
        agent = _make_agent(llm, max_iterations=10)
        result = await agent.run("Analyze the crash")

        assert isinstance(result, REPLResult)
        assert result.result == "overflow is 956 bytes"
        assert result.steps == 2
        assert result.code_blocks_executed == 2

    @pytest.mark.asyncio
    async def test_max_iterations(self):
        # LLM always returns code but never calls DONE
        responses = [
            f"```python\nprint('step {i}')\n```" for i in range(5)
        ]
        llm = _mock_llm(*responses)
        agent = _make_agent(llm, max_iterations=5)
        result = await agent.run("Analyze something")

        assert "Max iterations" in result.result
        assert result.steps == 5

    @pytest.mark.asyncio
    async def test_nudge_on_no_code(self):
        llm = _mock_llm(
            "I'm thinking about this...",  # No code block → nudge
            "```python\nDONE('done thinking')\n```",
        )
        agent = _make_agent(llm, max_iterations=10)
        result = await agent.run("Analyze something")

        assert result.result == "done thinking"
        # Step 1 was the thinking response, step 2 had the code
        assert result.steps == 2

    @pytest.mark.asyncio
    async def test_error_feedback(self):
        llm = _mock_llm(
            "```python\n1/0\n```",  # Error
            "```python\nDONE('recovered')\n```",
        )
        agent = _make_agent(llm, max_iterations=10)
        result = await agent.run("Do something")

        assert result.result == "recovered"
        # The error was fed back so the LLM could recover
        assert llm.chat.call_count == 2

    @pytest.mark.asyncio
    async def test_multiple_code_blocks_in_one_response(self):
        llm = _mock_llm(
            "Step 1:\n```python\nx = 10\n```\nStep 2:\n```python\nprint(x * 2)\n```",
            "```python\nDONE('done')\n```",
        )
        agent = _make_agent(llm, max_iterations=10)
        result = await agent.run("Compute something")

        assert result.result == "done"
        assert result.code_blocks_executed == 3  # x=10, print, DONE

    @pytest.mark.asyncio
    async def test_variables_in_result(self):
        llm = _mock_llm(
            "```python\noverflow_size = 956\n```",
            "```python\nDONE('found it')\n```",
        )
        agent = _make_agent(llm, max_iterations=10)
        result = await agent.run("Find the overflow")

        assert "overflow_size" in result.variables
        assert "956" in result.variables["overflow_size"]

    @pytest.mark.asyncio
    async def test_bridge_objects_accessible_in_code(self):
        llm = _mock_llm(
            "```python\npid = process.pid\nprint(f'PID: {pid}')\n```",
            "```python\nDONE('got pid')\n```",
        )
        agent = _make_agent(llm, max_iterations=10)
        result = await agent.run("Get process info")

        assert result.result == "got pid"


# ---------------------------------------------------------------------------
# REPLResult model
# ---------------------------------------------------------------------------

class TestREPLResult:
    def test_model_fields(self):
        r = REPLResult(
            result="done",
            steps=5,
            code_blocks_executed=8,
            variables={"x": "42"},
        )
        assert r.result == "done"
        assert r.steps == 5
        assert r.code_blocks_executed == 8
        assert r.variables == {"x": "42"}

    def test_default_variables(self):
        r = REPLResult(result="done", steps=1, code_blocks_executed=1)
        assert r.variables == {}
