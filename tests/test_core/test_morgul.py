"""Tests for Morgul and AsyncMorgul orchestrators."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from morgul.core.types.actions import Action, ActResult, ObserveResult
from morgul.core.types.config import MorgulConfig
from morgul.core.types.llm import AgentStep


class _SampleModel(BaseModel):
    name: str


def _make_morgul(config=None):
    """Build a Morgul with mocked internals."""
    with patch("morgul.bridge.Debugger") as mock_dbg_cls, \
         patch("morgul.llm.create_llm_client") as mock_create:
        mock_dbg_cls.return_value = MagicMock()
        mock_create.return_value = AsyncMock()
        from morgul.core.morgul import Morgul
        return Morgul(config=config or MorgulConfig())


def _make_async_morgul(config=None):
    """Build an AsyncMorgul with mocked internals."""
    with patch("morgul.bridge.Debugger") as mock_dbg_cls, \
         patch("morgul.llm.create_llm_client") as mock_create:
        mock_dbg_cls.return_value = MagicMock()
        mock_create.return_value = AsyncMock()
        from morgul.core.morgul import AsyncMorgul
        return AsyncMorgul(config=config or MorgulConfig())


def _start_morgul(morgul):
    """Set up mocked target/process so that .process/.target don't raise."""
    mock_target = MagicMock()
    mock_process = MagicMock()
    mock_process.pid = 123
    mock_process.selected_thread = MagicMock()
    mock_process.selected_thread.selected_frame = MagicMock()
    mock_target.launch.return_value = mock_process
    session = getattr(morgul, "_session", None)
    if session is None:
        return
    async_session = getattr(session, "_async_session", session)
    async_session.debugger.create_target.return_value = mock_target
    morgul.start("/tmp/a.out")


class TestMorgul:
    @pytest.fixture()
    def morgul(self):
        return _make_morgul()

    def test_init_with_config(self, morgul):
        assert morgul.config is not None
        assert morgul.config.llm.provider == "anthropic"

    def test_init_loads_default_config(self):
        m = _make_morgul()
        assert m.config.llm.provider == "anthropic"

    def test_init_with_config_path(self, tmp_path):
        toml_file = tmp_path / "morgul.toml"
        toml_file.write_text('[llm]\nprovider = "openai"\nmodel = "gpt-4o"\n')
        with patch("morgul.bridge.Debugger") as mock_dbg_cls, \
             patch("morgul.llm.create_llm_client") as mock_create:
            mock_dbg_cls.return_value = MagicMock()
            mock_create.return_value = AsyncMock()
            from morgul.core.morgul import Morgul
            m = Morgul(config_path=str(toml_file))
        assert m.config.llm.provider == "openai"
        assert m.config.llm.model == "gpt-4o"

    def test_verbose_enables_debug_logging(self):
        config = MorgulConfig(verbose=True)
        with patch("morgul.bridge.Debugger") as mock_dbg_cls, \
             patch("morgul.llm.create_llm_client") as mock_create, \
             patch("logging.basicConfig") as mock_log:
            mock_dbg_cls.return_value = MagicMock()
            mock_create.return_value = AsyncMock()
            from morgul.core.morgul import Morgul
            Morgul(config=config)
        mock_log.assert_called_once_with(level=logging.DEBUG)

    def test_start(self, morgul):
        mock_target = MagicMock()
        mock_process = MagicMock()
        mock_process.pid = 123
        mock_process.selected_thread = MagicMock()
        mock_process.selected_thread.selected_frame = MagicMock()
        mock_target.launch.return_value = mock_process
        morgul._session._async_session.debugger.create_target.return_value = mock_target

        morgul.start("/tmp/a.out")

    def test_end(self, morgul):
        morgul._session._async_session._process = MagicMock()
        morgul._session._async_session._target = MagicMock()
        morgul.end()

    def test_context_manager(self):
        m = _make_morgul()
        with m:
            assert m is not None

    def test_attach(self, morgul):
        mock_target = MagicMock()
        mock_process = MagicMock()
        mock_process.pid = 456
        mock_process.selected_thread = MagicMock()
        mock_process.selected_thread.selected_frame = MagicMock()
        morgul._session._async_session.debugger.attach.return_value = (mock_target, mock_process)
        morgul.attach(456)

    def test_attach_by_name(self, morgul):
        mock_target = MagicMock()
        mock_process = MagicMock()
        mock_process.pid = 789
        mock_process.selected_thread = MagicMock()
        mock_process.selected_thread.selected_frame = MagicMock()
        morgul._session._async_session.debugger.attach_by_name.return_value = (mock_target, mock_process)
        morgul.attach_by_name("Safari")

    def test_act_delegates_to_session(self, morgul):
        _start_morgul(morgul)
        expected = ActResult(
            success=True,
            message="done",
            actions=[Action(command="bt", description="bt")],
        )
        morgul._session._async_session._act_handler.act = AsyncMock(return_value=expected)
        result = morgul.act("show backtrace")
        assert isinstance(result, ActResult)
        assert result.success is True

    def test_observe_delegates_to_session(self, morgul):
        _start_morgul(morgul)
        expected = ObserveResult(
            actions=[Action(command="bt", description="bt")],
            description="stopped at main",
        )
        morgul._session._async_session._observe_handler.observe = AsyncMock(return_value=expected)
        result = morgul.observe()
        assert isinstance(result, ObserveResult)
        assert result.description == "stopped at main"

    def test_observe_with_instruction(self, morgul):
        _start_morgul(morgul)
        expected = ObserveResult(actions=[], description="heap looks fine")
        morgul._session._async_session._observe_handler.observe = AsyncMock(return_value=expected)
        result = morgul.observe("check the heap")
        assert result.description == "heap looks fine"

    def test_extract_delegates_to_session(self, morgul):
        _start_morgul(morgul)
        expected = _SampleModel(name="test")
        morgul._session._async_session._extract_handler.extract = AsyncMock(return_value=expected)
        result = morgul.extract("get name", response_model=_SampleModel)
        assert isinstance(result, _SampleModel)
        assert result.name == "test"

    def test_agent_delegates_to_session(self, morgul):
        _start_morgul(morgul)
        steps = [AgentStep(step_number=1, action="act(bt)", observation="frame 0", reasoning="need bt")]
        # Patch AgentHandler so agent() returns our canned steps
        with patch("morgul.core.session.AgentHandler") as mock_handler_cls:
            mock_handler = AsyncMock()
            mock_handler.run = AsyncMock(return_value=steps)
            mock_handler_cls.return_value = mock_handler
            result = morgul.agent("find bugs", strategy="depth-first", max_steps=5)
        assert len(result) == 1
        assert result[0].action == "act(bt)"


class TestAsyncMorgul:
    @pytest.fixture()
    def async_morgul(self):
        return _make_async_morgul()

    def test_init(self, async_morgul):
        assert async_morgul.config is not None

    def test_start(self, async_morgul):
        mock_target = MagicMock()
        mock_process = MagicMock()
        mock_process.pid = 123
        mock_process.selected_thread = MagicMock()
        mock_process.selected_thread.selected_frame = MagicMock()
        mock_target.launch.return_value = mock_process
        async_morgul._session.debugger.create_target.return_value = mock_target
        async_morgul.start("/tmp/a.out")

    def test_end(self, async_morgul):
        async_morgul._session._process = MagicMock()
        async_morgul._session._target = MagicMock()
        async_morgul.end()

    async def test_async_context_manager(self):
        m = _make_async_morgul()
        async with m:
            assert m is not None

    async def test_act(self):
        m = _make_async_morgul()
        mock_target = MagicMock()
        mock_process = MagicMock()
        mock_process.pid = 1
        mock_process.selected_thread = MagicMock()
        mock_process.selected_thread.selected_frame = MagicMock()
        mock_target.launch.return_value = mock_process
        m._session.debugger.create_target.return_value = mock_target
        m.start("/tmp/a.out")

        expected = ActResult(
            success=True, message="ok",
            actions=[Action(command="bt", description="bt")],
        )
        m._session._act_handler.act = AsyncMock(return_value=expected)
        result = await m.act("show backtrace")
        assert result.success is True

    async def test_observe(self):
        m = _make_async_morgul()
        mock_target = MagicMock()
        mock_process = MagicMock()
        mock_process.pid = 1
        mock_process.selected_thread = MagicMock()
        mock_process.selected_thread.selected_frame = MagicMock()
        mock_target.launch.return_value = mock_process
        m._session.debugger.create_target.return_value = mock_target
        m.start("/tmp/a.out")

        expected = ObserveResult(actions=[], description="all good")
        m._session._observe_handler.observe = AsyncMock(return_value=expected)
        result = await m.observe()
        assert result.description == "all good"

    async def test_extract(self):
        m = _make_async_morgul()
        mock_target = MagicMock()
        mock_process = MagicMock()
        mock_process.pid = 1
        mock_process.selected_thread = MagicMock()
        mock_process.selected_thread.selected_frame = MagicMock()
        mock_target.launch.return_value = mock_process
        m._session.debugger.create_target.return_value = mock_target
        m.start("/tmp/a.out")

        expected = _SampleModel(name="hello")
        m._session._extract_handler.extract = AsyncMock(return_value=expected)
        result = await m.extract("get name", response_model=_SampleModel)
        assert result.name == "hello"

    async def test_agent(self):
        m = _make_async_morgul()
        mock_target = MagicMock()
        mock_process = MagicMock()
        mock_process.pid = 1
        mock_process.selected_thread = MagicMock()
        mock_process.selected_thread.selected_frame = MagicMock()
        mock_target.launch.return_value = mock_process
        m._session.debugger.create_target.return_value = mock_target
        m.start("/tmp/a.out")

        steps = [AgentStep(step_number=1, action="done", observation="found it")]
        with patch("morgul.core.session.AgentHandler") as mock_cls:
            mock_h = AsyncMock()
            mock_h.run = AsyncMock(return_value=steps)
            mock_cls.return_value = mock_h
            result = await m.agent("hunt vulns", max_steps=3)
        assert len(result) == 1
