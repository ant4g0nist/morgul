"""Morgul — top-level orchestrator."""

from __future__ import annotations

import logging
from typing import List, Optional, Type, TypeVar

from pydantic import BaseModel

from morgul.core.session import AsyncSession, Session
from morgul.core.types.actions import ActResult, ObserveResult
from morgul.core.types.config import MorgulConfig, load_config
from morgul.core.types.llm import AgentStep
from morgul.core.types.repl import REPLResult

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class Morgul:
    """Top-level orchestrator for the Morgul debugger automation framework.

    Usage:
        morgul = Morgul()
        morgul.start("/path/to/binary")
        result = morgul.act("set a breakpoint on main")
        info = morgul.observe("what functions are available")
        morgul.end()

    Or as a context manager:
        with Morgul() as morgul:
            morgul.start("/path/to/binary")
            result = morgul.act("set a breakpoint on main")
    """

    def __init__(
        self,
        config: Optional[MorgulConfig] = None,
        config_path: Optional[str] = None,
        llm_event_callback=None,
        visible: Optional[bool] = None,
        dashboard_port: Optional[int] = None,
    ):
        if config is not None:
            self.config = config
        else:
            self.config = load_config(config_path)

        if visible is not None:
            self.config.visible = visible
        if dashboard_port is not None:
            self.config.dashboard_port = dashboard_port

        self._session = Session(self.config, llm_event_callback=llm_event_callback)
        self._async_session = self._session._async_session

        if self.config.verbose:
            logging.basicConfig(level=logging.DEBUG)

    def start(self, target_path: str, args: Optional[List[str]] = None) -> None:
        """Create a target and launch it."""
        self._session.start(target_path, args)

    def attach(self, pid: int) -> None:
        """Attach to a running process by PID."""
        self._session.attach(pid)

    def attach_by_name(self, name: str) -> None:
        """Attach to a running process by name."""
        self._session.attach_by_name(name)

    def act(self, instruction: str) -> ActResult:
        """Execute a natural language debugging instruction."""
        return self._session.act(instruction)

    def extract(self, instruction: str, response_model: Type[T]) -> T:
        """Extract structured data from the current process state."""
        return self._session.extract(instruction, response_model)

    def observe(self, instruction: Optional[str] = None) -> ObserveResult:
        """Observe the current state and suggest actions."""
        return self._session.observe(instruction)

    def agent(
        self,
        task: str,
        strategy: str = "depth-first",
        max_steps: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> List[AgentStep]:
        """Run the autonomous agent on a task."""
        return self._session.agent(task, strategy, max_steps, timeout)

    def repl_agent(
        self,
        task: str,
        max_iterations: int = 30,
    ) -> REPLResult:
        """Run an RLM-style REPL agent with LLDB bridge access."""
        return self._session.repl_agent(task, max_iterations)

    def wait_for_dashboard(self) -> None:
        """Block until Ctrl+C, keeping the web dashboard alive for browsing.

        Call this after the analysis is complete but before the script
        exits so users can still browse / refresh the dashboard.
        Does nothing if no dashboard is active.
        """
        self._session.wait_for_dashboard()

    def end(self) -> None:
        """End the session and clean up."""
        self._session.end()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.end()


class AsyncMorgul:
    """Async version of the Morgul orchestrator."""

    def __init__(
        self,
        config: Optional[MorgulConfig] = None,
        config_path: Optional[str] = None,
        llm_event_callback=None,
        visible: Optional[bool] = None,
        dashboard_port: Optional[int] = None,
    ):
        if config is not None:
            self.config = config
        else:
            self.config = load_config(config_path)

        if visible is not None:
            self.config.visible = visible
        if dashboard_port is not None:
            self.config.dashboard_port = dashboard_port

        self._session = AsyncSession(self.config, llm_event_callback=llm_event_callback)

        if self.config.verbose:
            logging.basicConfig(level=logging.DEBUG)

    def start(self, target_path: str, args: Optional[List[str]] = None) -> None:
        """Create a target and launch it."""
        self._session.start(target_path, args)

    def attach(self, pid: int) -> None:
        """Attach to a running process by PID."""
        self._session.attach(pid)

    def attach_by_name(self, name: str) -> None:
        """Attach to a running process by name."""
        self._session.attach_by_name(name)

    async def act(self, instruction: str) -> ActResult:
        """Execute a natural language debugging instruction."""
        return await self._session.act(instruction)

    async def extract(self, instruction: str, response_model: Type[T]) -> T:
        """Extract structured data from the current process state."""
        return await self._session.extract(instruction, response_model)

    async def observe(self, instruction: Optional[str] = None) -> ObserveResult:
        """Observe the current state and suggest actions."""
        return await self._session.observe(instruction)

    async def agent(
        self,
        task: str,
        strategy: str = "depth-first",
        max_steps: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> List[AgentStep]:
        """Run the autonomous agent on a task."""
        return await self._session.agent(task, strategy, max_steps, timeout)

    async def repl_agent(
        self,
        task: str,
        max_iterations: int = 30,
    ) -> REPLResult:
        """Run an RLM-style REPL agent with LLDB bridge access."""
        return await self._session.repl_agent(task, max_iterations)

    def wait_for_dashboard(self) -> None:
        """Block until Ctrl+C, keeping the web dashboard alive for browsing."""
        self._session.wait_for_dashboard()

    def end(self) -> None:
        """End the session and clean up."""
        self._session.end()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.end()
