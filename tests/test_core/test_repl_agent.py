"""Tests for the REPL agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from morgul.core.agent.repl import REPLAgent, extract_code_blocks
from morgul.core.session import AsyncSession
from morgul.core.types.config import AgentConfig, MorgulConfig
from morgul.core.types.llm import AgentStep
from morgul.core.types.repl import REPLCodeBlock, REPLIteration, REPLResult
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

class TestScaffoldProtection:
    def test_done_survives_overwrite(self):
        agent = _make_agent(_mock_llm())
        original_done = agent.namespace["DONE"]
        agent._execute("DONE = 'bad'")
        assert agent.namespace["DONE"] is original_done
        assert callable(agent.namespace["DONE"])


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
    async def test_iterations_populated(self):
        llm = _mock_llm(
            "```python\nprint('step1')\n```",
            "```python\nDONE('done')\n```",
        )
        agent = _make_agent(llm, max_iterations=10)
        result = await agent.run("Test iterations")

        assert len(result.iterations) == 2
        assert result.iterations[0].step_number == 1
        assert len(result.iterations[0].code_blocks) == 1
        assert result.iterations[0].code_blocks[0].code == "print('step1')\n"

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
# Sub-query telemetry accounting
# ---------------------------------------------------------------------------

class TestSubQueryAccounting:
    @pytest.mark.asyncio
    async def test_per_block_sub_query_count(self):
        """llm_sub_queries should be per-block delta, not cumulative."""
        # Block 1 calls llm_query once; block 2 calls llm_query once.
        # Each block should record 1, not 1 and 2.
        llm = AsyncMock()
        llm.chat.side_effect = [
            # Step 1: two code blocks in one response
            _make_response(
                '```python\nr1 = llm_query("q1")\nprint(r1)\n```\n'
                '```python\nr2 = llm_query("q2")\nprint(r2)\n```'
            ),
            # Sub-query response for q1
            _make_response("a1"),
            # Sub-query response for q2
            _make_response("a2"),
            # Step 2: done
            _make_response("```python\nDONE('done')\n```"),
        ]
        agent = _make_agent(llm, max_iterations=10)
        result = await agent.run("Test accounting")

        assert result.result == "done"
        # First iteration had 2 code blocks
        iter0 = result.iterations[0]
        assert len(iter0.code_blocks) == 2
        assert iter0.code_blocks[0].llm_sub_queries == 1
        assert iter0.code_blocks[1].llm_sub_queries == 1


# ---------------------------------------------------------------------------
# llm_query tests
# ---------------------------------------------------------------------------

class TestLLMQuery:
    @pytest.mark.asyncio
    async def test_llm_query_basic(self):
        """llm_query() should call the LLM and return the response."""
        # Main chat responses + sub-query response
        # The mock will serve responses in order: first two for main chat,
        # but llm_query calls chat() too, so we need extra responses.
        llm = AsyncMock()
        llm.chat.side_effect = [
            # Step 1: main chat
            _make_response(
                '```python\nresult = llm_query("What is 2+2?")\nprint(result)\n```'
            ),
            # Sub-query response (called from within exec)
            _make_response("4"),
            # Step 2: main chat
            _make_response("```python\nDONE('done')\n```"),
        ]
        agent = _make_agent(llm, max_iterations=10)
        result = await agent.run("Test query")

        assert result.result == "done"
        # llm.chat called 3 times: step1 main, sub-query, step2 main
        assert llm.chat.call_count == 3

    @pytest.mark.asyncio
    async def test_llm_query_budget_exceeded(self):
        """Exceeding the per-iteration budget should raise RuntimeError."""
        # Build code that calls llm_query more times than the budget
        code_lines = []
        for i in range(6):
            code_lines.append(f'r{i} = llm_query("q{i}")')
        code = "\n".join(code_lines)

        llm = AsyncMock()
        responses = [
            _make_response(f"```python\n{code}\n```"),
        ]
        # Add sub-query responses (only 5 will succeed, 6th should fail)
        for i in range(5):
            responses.append(_make_response(f"answer{i}"))
        # After error, LLM should recover
        responses.append(_make_response("```python\nDONE('recovered')\n```"))
        llm.chat.side_effect = responses

        agent = _make_agent(llm, max_iterations=10)
        agent._llm_query_budget = 5
        result = await agent.run("Test budget")

        assert result.result == "recovered"

    @pytest.mark.asyncio
    async def test_llm_query_event_emitted(self):
        """LLM_SUB_QUERY events should be fired."""
        from morgul.core.events import ExecutionEventType

        events = []

        def capture(event):
            events.append(event)

        llm = AsyncMock()
        llm.chat.side_effect = [
            _make_response('```python\nresult = llm_query("test")\n```'),
            _make_response("sub-answer"),  # sub-query
            _make_response("```python\nDONE('done')\n```"),
        ]

        debugger = MagicMock()
        target = MagicMock()
        process = _mock_process()
        agent = REPLAgent(
            llm_client=llm,
            debugger=debugger,
            target=target,
            process=process,
            max_iterations=10,
            execution_callback=capture,
        )
        await agent.run("Test events")

        sub_query_events = [
            e for e in events if e.event_type == ExecutionEventType.LLM_SUB_QUERY
        ]
        assert len(sub_query_events) >= 1


# ---------------------------------------------------------------------------
# llm_query_batched tests
# ---------------------------------------------------------------------------

class TestLLMQueryBatched:
    @pytest.mark.asyncio
    async def test_batched_basic(self):
        """llm_query_batched should return responses for all prompts."""
        llm = AsyncMock()
        llm.chat.side_effect = [
            # Step 1: main chat
            _make_response(
                '```python\nresults = llm_query_batched(["q1", "q2", "q3"])\nprint(results)\n```'
            ),
            # 3 concurrent sub-query responses
            _make_response("a1"),
            _make_response("a2"),
            _make_response("a3"),
            # Step 2: main chat
            _make_response("```python\nDONE('done')\n```"),
        ]
        agent = _make_agent(llm, max_iterations=10)
        result = await agent.run("Test batched")

        assert result.result == "done"

    @pytest.mark.asyncio
    async def test_batched_exceeds_max_size(self):
        """Batched queries exceeding max size should raise ValueError."""
        llm = AsyncMock()
        prompts_code = "[" + ", ".join(f'"q{i}"' for i in range(6)) + "]"
        llm.chat.side_effect = [
            _make_response(
                f'```python\nresults = llm_query_batched({prompts_code})\n```'
            ),
            # After error, recover
            _make_response("```python\nDONE('recovered')\n```"),
        ]
        agent = _make_agent(llm, max_iterations=10)
        result = await agent.run("Test batch size")

        assert result.result == "recovered"

    @pytest.mark.asyncio
    async def test_batched_shares_budget(self):
        """Batched queries share the per-iteration budget with llm_query."""
        # Use 3 of 5 budget via batched, then 2 single, then budget error
        code = (
            'results = llm_query_batched(["q1", "q2", "q3"])\n'
            'r4 = llm_query("q4")\n'
            'r5 = llm_query("q5")\n'
            'r6 = llm_query("q6")\n'  # Should exceed budget
        )
        llm = AsyncMock()
        llm.chat.side_effect = [
            _make_response(f"```python\n{code}\n```"),
            # 3 batched responses
            _make_response("a1"),
            _make_response("a2"),
            _make_response("a3"),
            # 2 single responses (q4, q5)
            _make_response("a4"),
            _make_response("a5"),
            # q6 should fail with budget error — no LLM call needed
            # After error, LLM recovers
            _make_response("```python\nDONE('recovered')\n```"),
        ]
        agent = _make_agent(llm, max_iterations=10)
        agent._llm_query_budget = 5
        result = await agent.run("Test shared budget")

        assert result.result == "recovered"


# ---------------------------------------------------------------------------
# Compaction tests
# ---------------------------------------------------------------------------

class TestCompaction:
    def test_estimate_tokens(self):
        from morgul.llm.types import ChatMessage

        agent = _make_agent(_mock_llm())
        messages = [
            ChatMessage(role="user", content="a" * 400),  # 100 tokens
            ChatMessage(role="assistant", content="b" * 800),  # 200 tokens
        ]
        tokens = agent._estimate_tokens(messages)
        assert tokens == 300  # (400 + 800) // 4

    @pytest.mark.asyncio
    async def test_compaction_triggered(self):
        """When history exceeds threshold, compaction should summarize."""
        # Create an agent with a very low threshold so compaction triggers
        llm = AsyncMock()
        responses = []
        # Generate enough responses to fill context
        for i in range(4):
            responses.append(_make_response(f"```python\nprint('step {i}')\n```"))
        # Compaction summary response
        responses.append(_make_response("Summary of previous work"))
        # Final step after compaction
        responses.append(_make_response("```python\nDONE('done')\n```"))
        llm.chat.side_effect = responses

        debugger = MagicMock()
        target = MagicMock()
        process = _mock_process()
        agent = REPLAgent(
            llm_client=llm,
            debugger=debugger,
            target=target,
            process=process,
            max_iterations=10,
            compaction_threshold_pct=0.01,  # Very low threshold
            context_window_tokens=100,  # Very small window
        )
        result = await agent.run("Test compaction")

        assert result.result == "done"
        # The compaction LLM call should have been made
        assert llm.chat.call_count > 4  # main calls + compaction call

    @pytest.mark.asyncio
    async def test_compaction_preserves_system_and_recent(self):
        """Compaction should keep the system prompt and last 4 messages."""
        from morgul.llm.types import ChatMessage

        agent = _make_agent(_mock_llm())
        # Mock the LLM for the summary call
        agent.llm.chat = AsyncMock(
            return_value=_make_response("Summary of history"),
        )

        system = ChatMessage(role="system", content="system prompt")
        messages = [system]
        # Add 10 middle messages
        for i in range(10):
            messages.append(ChatMessage(role="user", content=f"msg {i}"))
        # Last 4
        recent = messages[-4:]

        result = await agent._compact_history(messages)

        # First message is system prompt
        assert result[0].content == "system prompt"
        # Second is the compacted summary
        assert "[Compacted history]" in result[1].content
        # Last 4 are preserved
        assert result[-4:] == recent
        assert len(result) == 6  # system + compacted + 4 recent

    @pytest.mark.asyncio
    async def test_no_compaction_below_threshold(self):
        """No compaction should happen when under the threshold."""
        llm = _mock_llm(
            "```python\nprint('hi')\n```",
            "```python\nDONE('done')\n```",
        )
        debugger = MagicMock()
        target = MagicMock()
        process = _mock_process()
        agent = REPLAgent(
            llm_client=llm,
            debugger=debugger,
            target=target,
            process=process,
            max_iterations=10,
            compaction_threshold_pct=0.75,
            context_window_tokens=200_000,  # Very large - won't trigger
        )
        result = await agent.run("Simple task")

        assert result.result == "done"
        # Only 2 main chat calls, no compaction call
        assert llm.chat.call_count == 2


# ---------------------------------------------------------------------------
# FINAL_VAR tests
# ---------------------------------------------------------------------------

class TestFinalVar:
    @pytest.mark.asyncio
    async def test_final_var_returns_dict(self):
        llm = _mock_llm(
            '```python\nresults = {"vuln": "overflow", "size": 956}\nFINAL_VAR("results")\n```',
        )
        agent = _make_agent(llm, max_iterations=10)
        result = await agent.run("Analyze crash")

        assert result.final_var == {"vuln": "overflow", "size": 956}
        assert "FINAL_VAR" in result.result

    @pytest.mark.asyncio
    async def test_final_var_missing_variable(self):
        llm = _mock_llm(
            '```python\nFINAL_VAR("nonexistent")\n```',
            "```python\nDONE('recovered')\n```",
        )
        agent = _make_agent(llm, max_iterations=10)
        result = await agent.run("Test missing var")

        # The first block should fail with NameError, then LLM recovers
        assert result.result == "recovered"

    @pytest.mark.asyncio
    async def test_done_still_works_alongside_final_var(self):
        llm = _mock_llm(
            "```python\nDONE('classic done')\n```",
        )
        agent = _make_agent(llm, max_iterations=10)
        result = await agent.run("Test backward compat")

        assert result.result == "classic done"
        assert result.final_var is None

    @pytest.mark.asyncio
    async def test_final_var_serializes_complex_types(self):
        """Non-JSON-serializable objects should fallback to repr."""
        llm = _mock_llm(
            '```python\nobj = set([1, 2, 3])\nFINAL_VAR("obj")\n```',
        )
        agent = _make_agent(llm, max_iterations=10)
        result = await agent.run("Test complex type")

        # Sets are not JSON-serializable, so repr is used
        assert isinstance(result.final_var, str)
        assert "1" in result.final_var


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


# ---------------------------------------------------------------------------
# REPL-as-default-strategy tests
# ---------------------------------------------------------------------------

class TestREPLResultToSteps:
    """Unit tests for AsyncSession._repl_result_to_steps."""

    def _make_session(self):
        """Build an AsyncSession with mocked internals."""
        with patch.object(AsyncSession, "__init__", lambda self, *a, **kw: None):
            session = AsyncSession.__new__(AsyncSession)
        return session

    def test_converts_iterations_to_steps(self):
        session = self._make_session()
        repl_result = REPLResult(
            result="done",
            steps=2,
            code_blocks_executed=3,
            iterations=[
                REPLIteration(
                    step_number=1,
                    llm_response="Let me check the registers",
                    code_blocks=[
                        REPLCodeBlock(code="print('hello')\n", stdout="hello\n", stderr=""),
                    ],
                ),
                REPLIteration(
                    step_number=2,
                    llm_response="Found the issue",
                    code_blocks=[
                        REPLCodeBlock(code="x = 1\n", stdout="", stderr=""),
                        REPLCodeBlock(code="DONE('done')\n", stdout="[DONE]\n", stderr=""),
                    ],
                ),
            ],
        )
        steps = session._repl_result_to_steps(repl_result)
        assert len(steps) == 2
        assert all(isinstance(s, AgentStep) for s in steps)
        assert steps[0].step_number == 1
        assert steps[0].action == "repl_exec"
        assert "print('hello')" in steps[0].observation
        assert "hello" in steps[0].observation
        assert steps[1].step_number == 2
        assert "Found the issue" in steps[1].reasoning

    def test_empty_iterations_fallback(self):
        session = self._make_session()
        repl_result = REPLResult(
            result="nothing happened",
            steps=0,
            code_blocks_executed=0,
            iterations=[],
        )
        steps = session._repl_result_to_steps(repl_result)
        assert len(steps) == 1
        assert steps[0].action == "done"
        assert steps[0].observation == "nothing happened"

    def test_stderr_included(self):
        session = self._make_session()
        repl_result = REPLResult(
            result="error",
            steps=1,
            code_blocks_executed=1,
            iterations=[
                REPLIteration(
                    step_number=1,
                    llm_response="oops",
                    code_blocks=[
                        REPLCodeBlock(code="1/0\n", stdout="", stderr="ZeroDivisionError"),
                    ],
                ),
            ],
        )
        steps = session._repl_result_to_steps(repl_result)
        assert "ZeroDivisionError" in steps[0].observation


class TestAgentREPLRouting:
    """Test that agent(strategy='repl') routes to REPLAgent."""

    @pytest.mark.asyncio
    async def test_agent_default_strategy_is_repl(self):
        """Calling agent() with no strategy should use REPL path."""
        with patch.object(AsyncSession, "__init__", lambda self, *a, **kw: None):
            session = AsyncSession.__new__(AsyncSession)

        session.config = MorgulConfig()
        session.llm_client = MagicMock()
        session.debugger = MagicMock()
        session._target = MagicMock()
        session._process = _mock_process()
        session._execution_callback = None

        mock_repl_result = REPLResult(
            result="analysis complete",
            steps=1,
            code_blocks_executed=1,
            iterations=[
                REPLIteration(
                    step_number=1,
                    llm_response="Done",
                    code_blocks=[
                        REPLCodeBlock(code="DONE('analysis complete')\n", stdout="[DONE]\n"),
                    ],
                ),
            ],
        )

        with patch.object(REPLAgent, "run", new_callable=AsyncMock, return_value=mock_repl_result) as mock_run:
            steps = await session.agent("Analyze the crash")

        mock_run.assert_called_once_with("Analyze the crash")
        assert isinstance(steps, list)
        assert all(isinstance(s, AgentStep) for s in steps)
        assert len(steps) == 1
        assert steps[0].action == "repl_exec"

    @pytest.mark.asyncio
    async def test_agent_explicit_repl_strategy(self):
        """Calling agent(strategy='repl') should route to REPLAgent."""
        with patch.object(AsyncSession, "__init__", lambda self, *a, **kw: None):
            session = AsyncSession.__new__(AsyncSession)

        session.config = MorgulConfig()
        session.llm_client = MagicMock()
        session.debugger = MagicMock()
        session._target = MagicMock()
        session._process = _mock_process()
        session._execution_callback = None

        mock_repl_result = REPLResult(
            result="done", steps=1, code_blocks_executed=1,
            iterations=[
                REPLIteration(step_number=1, llm_response="ok", code_blocks=[
                    REPLCodeBlock(code="DONE('done')\n", stdout="[DONE]\n"),
                ]),
            ],
        )

        with patch.object(REPLAgent, "run", new_callable=AsyncMock, return_value=mock_repl_result):
            steps = await session.agent("task", strategy="repl")

        assert isinstance(steps, list)
        assert all(isinstance(s, AgentStep) for s in steps)

    @pytest.mark.asyncio
    async def test_agent_depth_first_still_works(self):
        """Calling agent(strategy='depth-first') should bypass REPL path."""
        with patch.object(AsyncSession, "__init__", lambda self, *a, **kw: None):
            session = AsyncSession.__new__(AsyncSession)

        session.config = MorgulConfig()
        session.llm_client = MagicMock()
        session.debugger = MagicMock()
        session._target = MagicMock()
        session._process = _mock_process()
        session._execution_callback = None

        mock_steps = [AgentStep(step_number=1, action="done", observation="ok", reasoning="ok")]

        with patch("morgul.core.session.AgentHandler") as MockHandler:
            handler_instance = MockHandler.return_value
            handler_instance.run = AsyncMock(return_value=mock_steps)
            steps = await session.agent("task", strategy="depth-first")

        assert steps == mock_steps
        MockHandler.assert_called_once()


# ---------------------------------------------------------------------------
# Custom tools injection tests
# ---------------------------------------------------------------------------

class TestCustomTools:
    def test_inject_tools_in_namespace(self):
        """Tools injected via constructor are available in namespace."""
        my_fn = lambda x: x * 2
        llm = _mock_llm()
        debugger = MagicMock()
        target = MagicMock()
        process = _mock_process()
        agent = REPLAgent(
            llm_client=llm,
            debugger=debugger,
            target=target,
            process=process,
            tools={"my_helper": my_fn, "BLOCK_SIZE": 4096},
        )
        assert agent.namespace["my_helper"] is my_fn
        assert agent.namespace["BLOCK_SIZE"] == 4096

    def test_inject_tools_rich_format(self):
        """Rich format tools are injected correctly."""
        my_fn = lambda addr: addr
        llm = _mock_llm()
        debugger = MagicMock()
        target = MagicMock()
        process = _mock_process()
        agent = REPLAgent(
            llm_client=llm,
            debugger=debugger,
            target=target,
            process=process,
            tools={"decode_header": {"tool": my_fn, "description": "Parse header"}},
        )
        assert agent.namespace["decode_header"] is my_fn
        assert agent._tool_descriptions == [("decode_header", "Parse header")]

    def test_inject_tools_reserved_name_rejected(self):
        """Tools with reserved names are rejected at construction."""
        llm = _mock_llm()
        debugger = MagicMock()
        target = MagicMock()
        process = _mock_process()
        with pytest.raises(ValueError, match="conflicts with reserved name"):
            REPLAgent(
                llm_client=llm,
                debugger=debugger,
                target=target,
                process=process,
                tools={"DONE": lambda: None},
            )

    def test_inject_tools_scaffold_protected(self):
        """Injected tools survive overwrite in exec."""
        my_fn = lambda: "original"
        llm = _mock_llm()
        debugger = MagicMock()
        target = MagicMock()
        process = _mock_process()
        agent = REPLAgent(
            llm_client=llm,
            debugger=debugger,
            target=target,
            process=process,
            tools={"my_tool": my_fn},
        )
        agent._execute("my_tool = 'overwritten'")
        assert agent.namespace["my_tool"] is my_fn

    @pytest.mark.asyncio
    async def test_inject_tools_in_system_prompt(self):
        """Tool descriptions appear in the LLM system prompt."""
        my_fn = lambda: None
        llm = AsyncMock()
        llm.chat.side_effect = [
            _make_response("```python\nDONE('done')\n```"),
        ]
        debugger = MagicMock()
        target = MagicMock()
        process = _mock_process()
        agent = REPLAgent(
            llm_client=llm,
            debugger=debugger,
            target=target,
            process=process,
            tools={"decode_header": {"tool": my_fn, "description": "Parse Mach-O header"}},
        )
        await agent.run("test task")

        # Check the system prompt in the first chat call
        first_call_messages = llm.chat.call_args_list[0].kwargs.get(
            "messages", llm.chat.call_args_list[0].args[0] if llm.chat.call_args_list[0].args else []
        )
        system_msg = first_call_messages[0]
        assert "Custom Tools" in system_msg.content
        assert "decode_header" in system_msg.content
        assert "Parse Mach-O header" in system_msg.content

    @pytest.mark.asyncio
    async def test_tools_via_repl_agent(self):
        """End-to-end: tools accessible through session.repl_agent(tools=...)."""
        my_fn = lambda: 42

        with patch.object(AsyncSession, "__init__", lambda self, *a, **kw: None):
            session = AsyncSession.__new__(AsyncSession)

        session.config = MorgulConfig()
        session.llm_client = MagicMock()
        session.debugger = MagicMock()
        session._target = MagicMock()
        session._process = _mock_process()
        session._execution_callback = None
        session._persistent_repl = None

        mock_repl_result = REPLResult(
            result="done", steps=1, code_blocks_executed=1,
            iterations=[
                REPLIteration(step_number=1, llm_response="ok", code_blocks=[
                    REPLCodeBlock(code="DONE('done')\n", stdout="[DONE]\n"),
                ]),
            ],
        )

        with patch.object(REPLAgent, "run", new_callable=AsyncMock, return_value=mock_repl_result):
            with patch.object(REPLAgent, "__init__", return_value=None) as mock_init:
                result = await session.repl_agent("task", tools={"helper": my_fn})

        # Verify tools was passed through
        mock_init.assert_called_once()
        call_kwargs = mock_init.call_args.kwargs
        assert call_kwargs.get("tools") == {"helper": my_fn}


# ---------------------------------------------------------------------------
# Multi-turn persistence tests
# ---------------------------------------------------------------------------

class TestMultiTurnPersistence:
    @pytest.mark.asyncio
    async def test_persistent_namespace_survives(self):
        """Variable from turn 1 is accessible in turn 2."""
        llm = AsyncMock()
        llm.chat.side_effect = [
            # Turn 1
            _make_response("```python\nmy_var = 42\nDONE('set var')\n```"),
            # Turn 2
            _make_response("```python\nprint(my_var)\nDONE('got var')\n```"),
        ]
        debugger = MagicMock()
        target = MagicMock()
        process = _mock_process()
        agent = REPLAgent(
            llm_client=llm,
            debugger=debugger,
            target=target,
            process=process,
            persistent=True,
        )
        result1 = await agent.run("Set a variable")
        assert result1.result == "set var"
        assert agent.namespace["my_var"] == 42

        result2 = await agent.run("Read the variable")
        assert result2.result == "got var"

    @pytest.mark.asyncio
    async def test_persistent_history_carries_over(self):
        """LLM sees prior conversation context in persistent mode."""
        llm = AsyncMock()
        llm.chat.side_effect = [
            # Turn 1
            _make_response("```python\nDONE('turn1 done')\n```"),
            # Turn 2
            _make_response("```python\nDONE('turn2 done')\n```"),
        ]
        debugger = MagicMock()
        target = MagicMock()
        process = _mock_process()
        agent = REPLAgent(
            llm_client=llm,
            debugger=debugger,
            target=target,
            process=process,
            persistent=True,
        )
        await agent.run("First task")
        await agent.run("Second task")

        # The second call to llm.chat should have the history from turn 1
        second_call_messages = llm.chat.call_args_list[1].kwargs.get(
            "messages", llm.chat.call_args_list[1].args[0] if llm.chat.call_args_list[1].args else []
        )
        # Should have: system, user(turn1), assistant(turn1), user(feedback), user(New task:...)
        assert len(second_call_messages) > 2
        # One of the messages should contain "New task:" with the second task
        all_content = " ".join(m.content for m in second_call_messages)
        assert "New task:" in all_content
        assert "Second task" in all_content

    @pytest.mark.asyncio
    async def test_persistent_done_resets_between_turns(self):
        """_done resets so new task can run."""
        llm = AsyncMock()
        llm.chat.side_effect = [
            _make_response("```python\nDONE('turn1')\n```"),
            _make_response("```python\nDONE('turn2')\n```"),
        ]
        debugger = MagicMock()
        target = MagicMock()
        process = _mock_process()
        agent = REPLAgent(
            llm_client=llm,
            debugger=debugger,
            target=target,
            process=process,
            persistent=True,
        )
        result1 = await agent.run("Task 1")
        assert result1.result == "turn1"
        assert agent._done is True

        result2 = await agent.run("Task 2")
        assert result2.result == "turn2"

    @pytest.mark.asyncio
    async def test_persistent_code_blocks_cumulative(self):
        """Code block count is cumulative across turns."""
        llm = AsyncMock()
        llm.chat.side_effect = [
            _make_response("```python\nx = 1\n```\n```python\nDONE('t1')\n```"),
            _make_response("```python\ny = 2\n```\n```python\nDONE('t2')\n```"),
        ]
        debugger = MagicMock()
        target = MagicMock()
        process = _mock_process()
        agent = REPLAgent(
            llm_client=llm,
            debugger=debugger,
            target=target,
            process=process,
            persistent=True,
        )
        result1 = await agent.run("Task 1")
        assert result1.code_blocks_executed == 2

        result2 = await agent.run("Task 2")
        assert result2.code_blocks_executed == 4  # cumulative

    @pytest.mark.asyncio
    async def test_persistent_session_level(self):
        """session.repl_agent(persistent=True) reuses agent across calls."""
        with patch.object(AsyncSession, "__init__", lambda self, *a, **kw: None):
            session = AsyncSession.__new__(AsyncSession)

        session.config = MorgulConfig()
        session.llm_client = MagicMock()
        session.debugger = MagicMock()
        session._target = MagicMock()
        session._process = _mock_process()
        session._execution_callback = None
        session._persistent_repl = None

        mock_result = REPLResult(
            result="done", steps=1, code_blocks_executed=1,
            iterations=[],
        )

        with patch("morgul.core.session.REPLAgent") as MockREPLAgent:
            mock_agent = MockREPLAgent.return_value
            mock_agent.run = AsyncMock(return_value=mock_result)
            await session.repl_agent("task 1", persistent=True)
            await session.repl_agent("task 2", persistent=True)

        # REPLAgent should only be constructed once
        assert MockREPLAgent.call_count == 1
        # But run() should be called twice
        assert mock_agent.run.call_count == 2

    @pytest.mark.asyncio
    async def test_non_persistent_is_fresh(self):
        """Default behavior: each call creates a fresh agent."""
        llm = AsyncMock()
        llm.chat.side_effect = [
            _make_response("```python\nmy_var = 42\nDONE('t1')\n```"),
            _make_response("```python\nprint(my_var)\n```"),
            _make_response("```python\nDONE('t2')\n```"),
        ]
        debugger = MagicMock()
        target = MagicMock()
        process = _mock_process()

        agent1 = REPLAgent(
            llm_client=llm,
            debugger=debugger,
            target=target,
            process=process,
        )
        result1 = await agent1.run("Set var")
        assert result1.result == "t1"

        # Fresh agent should NOT have my_var
        agent2 = REPLAgent(
            llm_client=llm,
            debugger=debugger,
            target=target,
            process=process,
        )
        result2 = await agent2.run("Read var")
        # The second agent will get a NameError on my_var, then recover
        assert result2.result == "t2"

    @pytest.mark.asyncio
    async def test_session_end_clears_persistent_repl(self):
        """Session.end() clears the persistent REPL agent."""
        with patch.object(AsyncSession, "__init__", lambda self, *a, **kw: None):
            session = AsyncSession.__new__(AsyncSession)

        session._persistent_repl = MagicMock()
        session._web_display = None
        session._visible_display = None
        session._process = None
        session._target = None
        session._act_handler = None
        session.debugger = MagicMock()

        session.end()
        assert session._persistent_repl is None
