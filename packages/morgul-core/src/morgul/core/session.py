"""Session — binds a debugger target/process to Morgul primitives."""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, Type, TypeVar

from pydantic import BaseModel

from morgul.core.agent.handler import AgentHandler
from morgul.core.agent.repl import REPLAgent
from morgul.core.agent.strategies import AgentStrategy
from morgul.core.primitives.act import ActHandler
from morgul.core.primitives.extract import ExtractHandler
from morgul.core.primitives.observe import ObserveHandler
from morgul.core.types.actions import ActResult, ObserveResult
from morgul.core.types.config import MorgulConfig
from morgul.core.types.llm import AgentStep
from morgul.core.types.repl import REPLResult

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class AsyncSession:
    """Async session binding a debugger to Morgul primitives.

    Lifecycle: start(target_path) or attach(pid) → primitives → end()
    """

    def __init__(self, config: MorgulConfig, llm_event_callback=None, execution_callback=None):
        from morgul.bridge import Debugger
        from morgul.llm import InstrumentedLLMClient, create_llm_client
        from morgul.llm.types import ModelConfig

        self.config = config
        self.debugger = Debugger()
        self._visible_display = None
        self._web_display = None
        self._execution_callback = execution_callback

        # If dashboard_port is set and no custom callback, create a WebDisplay
        if config.dashboard_port is not None and execution_callback is None:
            from morgul.core.display.web import WebDisplay

            self._web_display = WebDisplay(port=config.dashboard_port)
            self._execution_callback = self._web_display.on_execution_event
            _user_llm_cb = llm_event_callback
            def _combined_llm_cb(event, is_start):
                self._web_display.on_llm_event(event, is_start)
                if _user_llm_cb is not None:
                    _user_llm_cb(event, is_start)
            llm_event_callback = _combined_llm_cb

        # Fallback: if visible=True but no dashboard_port (shouldn't happen with validator),
        # use the Rich TUI
        elif config.visible and execution_callback is None:
            from morgul.core.display import VisibleDisplay

            self._visible_display = VisibleDisplay()
            self._execution_callback = self._visible_display.on_execution_event
            _user_llm_cb = llm_event_callback
            def _combined_llm_cb(event, is_start):
                self._visible_display.on_llm_event(event, is_start)
                if _user_llm_cb is not None:
                    _user_llm_cb(event, is_start)
            llm_event_callback = _combined_llm_cb

        model_config = ModelConfig(
            provider=config.llm.provider,
            model_name=config.llm.model,
            api_key=config.llm.api_key,
            base_url=config.llm.base_url,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
        )
        raw_client = create_llm_client(model_config)
        if llm_event_callback is not None:
            self.llm_client = InstrumentedLLMClient(raw_client, llm_event_callback)
        else:
            self.llm_client = raw_client

        self._target = None
        self._process = None

        # Content-addressed cache (optional)
        self._cache = None
        if config.cache.enabled:
            from morgul.core.cache import ContentCache, FileStorage

            storage = FileStorage(directory=config.cache.directory)
            self._cache = ContentCache(storage=storage)

        # ActHandler is created lazily after target/process are available
        self._act_handler: ActHandler | None = None
        self._extract_handler = ExtractHandler(llm_client=self.llm_client, cache=self._cache)
        self._observe_handler = ObserveHandler(llm_client=self.llm_client, cache=self._cache)

    def _init_handlers(self) -> None:
        """Create handlers that require target/process."""
        self._act_handler = ActHandler(
            llm_client=self.llm_client,
            debugger=self.debugger,
            target=self._target,
            process=self._process,
            self_heal=self.config.self_heal,
            max_retries=self.config.healing.max_retries,
            execution_callback=self._execution_callback,
            cache=self._cache,
        )

    def start(self, target_path: str, args: Optional[List[str]] = None) -> None:
        """Create a target and launch it."""
        if self._web_display is not None:
            self._web_display.start()
        elif self._visible_display is not None:
            self._visible_display.start()
        self._target = self.debugger.create_target(target_path)
        self._process = self._target.launch(args=args)
        self._init_handlers()
        logger.info("Started target: %s (pid=%d)", target_path, self._process.pid)

    def attach(self, pid: int) -> None:
        """Attach to a running process."""
        self._target, self._process = self.debugger.attach(pid)
        self._init_handlers()
        logger.info("Attached to pid=%d", pid)

    def attach_by_name(self, name: str) -> None:
        """Attach to a process by name."""
        self._target, self._process = self.debugger.attach_by_name(name)
        self._init_handlers()
        logger.info("Attached to %s (pid=%d)", name, self._process.pid)

    @property
    def process(self):
        if self._process is None:
            raise RuntimeError("No process. Call start() or attach() first.")
        return self._process

    @property
    def target(self):
        if self._target is None:
            raise RuntimeError("No target. Call start() or attach() first.")
        return self._target

    async def act(self, instruction: str) -> ActResult:
        """Execute a natural language debugging instruction."""
        if self._act_handler is None:
            raise RuntimeError("No process. Call start() or attach() first.")
        return await self._act_handler.act(instruction, self.process)

    async def extract(self, instruction: str, response_model: Type[T]) -> T:
        """Extract structured data from the current process state."""
        return await self._extract_handler.extract(instruction, self.process, response_model)

    async def observe(self, instruction: Optional[str] = None) -> ObserveResult:
        """Observe the current state and suggest actions."""
        return await self._observe_handler.observe(self.process, instruction)

    async def agent(
        self,
        task: str,
        strategy: str = "depth-first",
        max_steps: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> List[AgentStep]:
        """Run the autonomous agent on a task.

        If ``config.agent.agentic_provider`` is set (e.g. "claude-code" or "codex"),
        delegates to an SDK-managed agentic backend. Otherwise falls through to the
        existing AgentHandler with manual tool loop.
        """
        agent_cfg = self.config.agent

        # ── Agentic backend path ──────────────────────────────────────
        if agent_cfg.agentic_provider:
            from morgul.core.agent.tools import AGENT_TOOLS
            from morgul.llm.agentic import AgenticResult, create_agentic_client

            agentic_client = create_agentic_client(
                provider=agent_cfg.agentic_provider,
                model=agent_cfg.agentic_model,
                api_key=agent_cfg.agentic_api_key,
                cli_path=agent_cfg.agentic_cli_path,
            )

            # Build a tool_executor that routes calls to the existing _execute_tool logic.
            handler = AgentHandler(
                llm_client=self.llm_client,
                debugger=self.debugger,
                process=self.process,
                strategy=AgentStrategy(strategy),
                max_steps=max_steps or agent_cfg.max_steps,
                timeout=timeout or agent_cfg.timeout,
            )

            async def tool_executor(name: str, args: dict) -> str:
                return await handler._execute_tool(name, args)

            agentic_result: AgenticResult = await agentic_client.run_agent(
                task=task,
                tools=AGENT_TOOLS,
                tool_executor=tool_executor,
                max_iterations=max_steps or agent_cfg.max_steps,
            )

            # Convert AgenticResult into List[AgentStep] for compatibility.
            steps: List[AgentStep] = []
            for i, tc in enumerate(agentic_result.tool_calls, 1):
                steps.append(
                    AgentStep(
                        step_number=i,
                        action=f"{tc['name']}({tc.get('arguments', {})})",
                        observation=tc.get("result", ""),
                        reasoning="",
                    )
                )
            if not steps:
                steps.append(
                    AgentStep(
                        step_number=1,
                        action="done",
                        observation=agentic_result.result,
                        reasoning=agentic_result.result,
                    )
                )
            return steps

        # ── Default path: manual tool loop via AgentHandler ───────────
        handler = AgentHandler(
            llm_client=self.llm_client,
            debugger=self.debugger,
            process=self.process,
            strategy=AgentStrategy(strategy),
            max_steps=max_steps or agent_cfg.max_steps,
            timeout=timeout or agent_cfg.timeout,
        )
        return await handler.run(task)

    async def repl_agent(
        self,
        task: str,
        max_iterations: int = 30,
    ) -> REPLResult:
        """Run an RLM-style REPL agent with LLDB bridge access."""
        agent = REPLAgent(
            llm_client=self.llm_client,
            debugger=self.debugger,
            target=self.target,
            process=self.process,
            max_iterations=max_iterations,
            execution_callback=self._execution_callback,
        )
        return await agent.run(task)

    def wait_for_dashboard(self) -> None:
        """Block until the user presses Ctrl+C, keeping the dashboard alive.

        After Ctrl+C the dashboard server is shut down.  Safe to call
        even when no dashboard is active (returns immediately).
        """
        if self._web_display is not None:
            self._web_display.wait()
            self._web_display = None

    def end(self) -> None:
        """End the session and clean up."""
        if self._web_display is not None:
            self._web_display.stop()
            # Don't set to None — wait_for_dashboard() may be called after
        if self._visible_display is not None:
            self._visible_display.stop()
            self._visible_display = None
        if self._process is not None:
            try:
                self._process.kill()
            except Exception:
                pass
            self._process = None
        self._target = None
        self._act_handler = None
        self.debugger.destroy()
        logger.info("Session ended")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.end()


class Session:
    """Synchronous wrapper around AsyncSession for convenience."""

    def __init__(self, config: MorgulConfig, llm_event_callback=None, execution_callback=None):
        self._async_session = AsyncSession(
            config,
            llm_event_callback=llm_event_callback,
            execution_callback=execution_callback,
        )
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
        return self._loop

    def _run(self, coro):
        loop = self._get_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)

    def start(self, target_path: str, args: Optional[List[str]] = None) -> None:
        self._async_session.start(target_path, args)

    def attach(self, pid: int) -> None:
        self._async_session.attach(pid)

    def attach_by_name(self, name: str) -> None:
        self._async_session.attach_by_name(name)

    @property
    def process(self):
        return self._async_session.process

    @property
    def target(self):
        return self._async_session.target

    def act(self, instruction: str) -> ActResult:
        return self._run(self._async_session.act(instruction))

    def extract(self, instruction: str, response_model: Type[T]) -> T:
        return self._run(self._async_session.extract(instruction, response_model))

    def observe(self, instruction: Optional[str] = None) -> ObserveResult:
        return self._run(self._async_session.observe(instruction))

    def agent(
        self,
        task: str,
        strategy: str = "depth-first",
        max_steps: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> List[AgentStep]:
        return self._run(
            self._async_session.agent(task, strategy, max_steps, timeout)
        )

    def repl_agent(
        self,
        task: str,
        max_iterations: int = 30,
    ) -> REPLResult:
        return self._run(
            self._async_session.repl_agent(task, max_iterations)
        )

    def wait_for_dashboard(self) -> None:
        """Block until the user presses Ctrl+C, keeping the dashboard alive."""
        self._async_session.wait_for_dashboard()

    def end(self) -> None:
        self._async_session.end()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.end()
