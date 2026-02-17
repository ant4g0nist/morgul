"""Tests for Session and AsyncSession."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from morgul.core.types.actions import Action, ActResult, ObserveResult
from morgul.core.types.config import MorgulConfig
from morgul.core.types.llm import AgentStep


class SampleModel(BaseModel):
    name: str
    value: int


def _make_async_session():
    """Build an AsyncSession with mocked Debugger and LLM client."""
    with patch("morgul.bridge.Debugger") as mock_dbg_cls, \
         patch("morgul.llm.create_llm_client") as mock_create:
        mock_dbg_cls.return_value = MagicMock()
        mock_create.return_value = AsyncMock()
        from morgul.core.session import AsyncSession
        return AsyncSession(MorgulConfig())


def _make_session():
    """Build a Session with mocked Debugger and LLM client."""
    with patch("morgul.bridge.Debugger") as mock_dbg_cls, \
         patch("morgul.llm.create_llm_client") as mock_create:
        mock_dbg_cls.return_value = MagicMock()
        mock_create.return_value = AsyncMock()
        from morgul.core.session import Session
        return Session(MorgulConfig())


def _start_async_session(session):
    """Start a session with mocked target/process."""
    mock_target = MagicMock()
    mock_process = MagicMock()
    mock_process.pid = 123
    mock_process.selected_thread = MagicMock()
    mock_process.selected_thread.selected_frame = MagicMock()
    mock_target.launch.return_value = mock_process
    session.debugger.create_target.return_value = mock_target
    session.start("/tmp/a.out")
    return session


class TestAsyncSession:
    @pytest.fixture()
    def session(self):
        return _make_async_session()

    @pytest.fixture()
    def started_session(self):
        return _start_async_session(_make_async_session())

    def test_init(self, session):
        assert session.debugger is not None
        assert session.llm_client is not None

    def test_init_no_act_handler(self, session):
        """ActHandler is None before start/attach."""
        assert session._act_handler is None

    def test_start(self, session):
        mock_target = MagicMock()
        mock_process = MagicMock()
        mock_process.pid = 123
        mock_process.selected_thread = MagicMock()
        mock_process.selected_thread.selected_frame = MagicMock()
        mock_target.launch.return_value = mock_process
        session.debugger.create_target.return_value = mock_target

        session.start("/tmp/a.out")
        assert session._target is not None
        assert session._process is not None
        assert session._act_handler is not None

    def test_start_with_args(self, session):
        mock_target = MagicMock()
        mock_process = MagicMock()
        mock_process.pid = 123
        mock_process.selected_thread = MagicMock()
        mock_process.selected_thread.selected_frame = MagicMock()
        mock_target.launch.return_value = mock_process
        session.debugger.create_target.return_value = mock_target

        session.start("/tmp/a.out", args=["-la"])
        mock_target.launch.assert_called_once_with(args=["-la"])

    def test_attach(self, session):
        mock_target = MagicMock()
        mock_process = MagicMock()
        mock_process.pid = 456
        mock_process.selected_thread = MagicMock()
        mock_process.selected_thread.selected_frame = MagicMock()
        session.debugger.attach.return_value = (mock_target, mock_process)

        session.attach(456)
        assert session._target is not None
        assert session._act_handler is not None

    def test_attach_by_name(self, session):
        mock_target = MagicMock()
        mock_process = MagicMock()
        mock_process.pid = 789
        mock_process.selected_thread = MagicMock()
        mock_process.selected_thread.selected_frame = MagicMock()
        session.debugger.attach_by_name.return_value = (mock_target, mock_process)

        session.attach_by_name("Safari")
        assert session._process is not None
        assert session._act_handler is not None

    def test_process_raises_without_start(self, session):
        with pytest.raises(RuntimeError, match="No process"):
            _ = session.process

    def test_target_raises_without_start(self, session):
        with pytest.raises(RuntimeError, match="No target"):
            _ = session.target

    async def test_act_raises_without_start(self, session):
        """act() raises before start/attach since _act_handler is None."""
        with pytest.raises(RuntimeError, match="No process"):
            await session.act("test")

    def test_end(self, session):
        session._process = MagicMock()
        session._target = MagicMock()
        session._act_handler = MagicMock()
        session.end()
        assert session._process is None
        assert session._target is None
        assert session._act_handler is None

    def test_end_kill_failure_ignored(self, session):
        session._process = MagicMock()
        session._process.kill.side_effect = Exception("already dead")
        session._target = MagicMock()
        session.end()  # Should not raise
        assert session._process is None

    async def test_context_manager(self):
        session = _make_async_session()
        async with session as s:
            assert s is not None

    # -- primitive method tests -----------------------------------------------

    async def test_act(self, started_session):
        expected = ActResult(
            success=True, message="ok",
            actions=[Action(code="print('bt')", description="bt")],
        )
        started_session._act_handler.act = AsyncMock(return_value=expected)
        result = await started_session.act("show backtrace")
        assert result.success is True
        started_session._act_handler.act.assert_called_once()

    async def test_observe(self, started_session):
        expected = ObserveResult(actions=[], description="stopped")
        started_session._observe_handler.observe = AsyncMock(return_value=expected)
        result = await started_session.observe()
        assert result.description == "stopped"

    async def test_observe_with_instruction(self, started_session):
        expected = ObserveResult(actions=[], description="heap ok")
        started_session._observe_handler.observe = AsyncMock(return_value=expected)
        result = await started_session.observe("check the heap")
        assert result.description == "heap ok"

    async def test_extract(self, started_session):
        expected = SampleModel(name="test", value=42)
        started_session._extract_handler.extract = AsyncMock(return_value=expected)
        result = await started_session.extract("get data", response_model=SampleModel)
        assert isinstance(result, SampleModel)
        assert result.value == 42

    async def test_agent(self, started_session):
        steps = [AgentStep(step_number=1, action="done", observation="found")]
        with patch("morgul.core.session.AgentHandler") as mock_cls:
            mock_h = AsyncMock()
            mock_h.run = AsyncMock(return_value=steps)
            mock_cls.return_value = mock_h
            result = await started_session.agent("find bugs")
        assert len(result) == 1
        assert result[0].action == "done"

    async def test_agent_uses_config_defaults(self, started_session):
        steps = []
        with patch("morgul.core.session.AgentHandler") as mock_cls:
            mock_h = AsyncMock()
            mock_h.run = AsyncMock(return_value=steps)
            mock_cls.return_value = mock_h
            await started_session.agent("task")
            # Should have used config defaults (max_steps=50, timeout=300)
            _, kwargs = mock_cls.call_args
            assert kwargs["max_steps"] == 50
            assert kwargs["timeout"] == 300.0


class TestSession:
    @pytest.fixture()
    def session(self):
        return _make_session()

    def test_init(self, session):
        assert session._async_session is not None

    def test_start(self, session):
        mock_target = MagicMock()
        mock_process = MagicMock()
        mock_process.pid = 123
        mock_process.selected_thread = MagicMock()
        mock_process.selected_thread.selected_frame = MagicMock()
        mock_target.launch.return_value = mock_process
        session._async_session.debugger.create_target.return_value = mock_target

        session.start("/tmp/a.out")

    def test_end(self, session):
        session._async_session._process = MagicMock()
        session._async_session._target = MagicMock()
        session.end()

    def test_context_manager(self):
        session = _make_session()
        with session as s:
            assert s is not None

    def test_act(self):
        session = _make_session()
        _start_async_session(session._async_session)
        expected = ActResult(
            success=True, message="ok",
            actions=[Action(code="print('bt')", description="bt")],
        )
        session._async_session._act_handler.act = AsyncMock(return_value=expected)
        result = session.act("show backtrace")
        assert result.success is True

    def test_observe(self):
        session = _make_session()
        _start_async_session(session._async_session)
        expected = ObserveResult(actions=[], description="stopped")
        session._async_session._observe_handler.observe = AsyncMock(return_value=expected)
        result = session.observe()
        assert result.description == "stopped"

    def test_extract(self):
        session = _make_session()
        _start_async_session(session._async_session)
        expected = SampleModel(name="x", value=1)
        session._async_session._extract_handler.extract = AsyncMock(return_value=expected)
        result = session.extract("get", response_model=SampleModel)
        assert result.name == "x"
