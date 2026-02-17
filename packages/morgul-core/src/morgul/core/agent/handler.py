"""Agent handler — autonomous debugging loop."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, AsyncIterator

from morgul.core.agent.strategies import AgentStrategy, get_strategy_description
from morgul.core.agent.tools import AGENT_TOOLS
from morgul.core.context.builder import ContextBuilder
from morgul.core.translate.prompts import AGENT_SYSTEM_PROMPT
from morgul.core.types.llm import AgentStep

if TYPE_CHECKING:
    from morgul.bridge import Debugger
    from morgul.bridge.process import Process
    from morgul.llm import LLMClient
    from morgul.llm.types import ChatMessage

logger = logging.getLogger(__name__)


class AgentHandler:
    """Autonomous debugging agent that iterates through observe→act→extract→reason cycles.

    Supports three strategies:
    - depth-first: Follow the most promising lead deeply
    - breadth-first: Survey the landscape before diving deep
    - hypothesis-driven: Form and test hypotheses
    """

    def __init__(
        self,
        llm_client: LLMClient,
        debugger: Debugger,
        process: Process,
        strategy: AgentStrategy = AgentStrategy.DEPTH_FIRST,
        max_steps: int = 50,
        timeout: float = 300.0,
    ):
        self.llm = llm_client
        self.debugger = debugger
        self.process = process
        self.strategy = strategy
        self.max_steps = max_steps
        self.timeout = timeout
        self.context_builder = ContextBuilder()
        self.steps: list[AgentStep] = []

    async def run(self, task: str) -> list[AgentStep]:
        """Run the agent loop until completion or limits are reached."""
        steps: list[AgentStep] = []
        async for step in self.run_stream(task):
            steps.append(step)
        return steps

    async def run_stream(self, task: str) -> AsyncIterator[AgentStep]:
        """Run the agent loop, yielding steps as they complete."""
        from morgul.llm.types import ChatMessage

        system_prompt = AGENT_SYSTEM_PROMPT.format(
            strategy=self.strategy.value,
            strategy_description=get_strategy_description(self.strategy),
            task=task,
            max_steps=self.max_steps,
        )

        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=system_prompt),
        ]

        # Add initial observation
        snapshot = self.context_builder.build(self.process)
        context_text = self.context_builder.format_for_prompt(snapshot)
        messages.append(
            ChatMessage(
                role="user",
                content=f"Current process state:\n{context_text}\n\nBegin working on the task.",
            )
        )

        start_time = time.monotonic()

        for step_num in range(1, self.max_steps + 1):
            elapsed = time.monotonic() - start_time
            if elapsed > self.timeout:
                logger.warning("Agent timeout after %.1f seconds", elapsed)
                break

            # Get LLM response with tools
            response = await self.llm.chat(
                messages=messages,
                tools=AGENT_TOOLS,
            )

            # Process tool calls
            if response.tool_calls:
                # Execute all tool calls and collect results
                tool_results: list[tuple[str, str, str]] = []  # (id, name, result)
                done = False
                for tool_call in response.tool_calls:
                    result = await self._execute_tool(tool_call.name, tool_call.arguments)
                    tool_results.append((tool_call.id, tool_call.name, result))

                    step = AgentStep(
                        step_number=step_num,
                        action=f"{tool_call.name}({tool_call.arguments})",
                        observation=result,
                        reasoning=response.content or "",
                    )
                    self.steps.append(step)
                    yield step

                    if tool_call.name == "done":
                        done = True

                if done:
                    return

                # Append ONE assistant message with all tool_calls
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=response.content or "",
                        tool_calls=response.tool_calls,
                    )
                )

                # Append one tool result message for EACH tool_call_id
                for tc_id, _tc_name, tc_result in tool_results:
                    messages.append(
                        ChatMessage(
                            role="tool",
                            content=tc_result,
                            tool_call_id=tc_id,
                        )
                    )

                # Update context after all actions
                snapshot = self.context_builder.build(self.process)
                context_text = self.context_builder.format_for_prompt(snapshot)
                messages.append(
                    ChatMessage(
                        role="user",
                        content=f"Updated process state:\n{context_text}",
                    )
                )
            else:
                # No tool calls — LLM just responded with text
                step = AgentStep(
                    step_number=step_num,
                    action="think",
                    observation=response.content or "",
                    reasoning=response.content or "",
                )
                self.steps.append(step)
                yield step

                messages.append(
                    ChatMessage(role="assistant", content=response.content or "")
                )
                messages.append(
                    ChatMessage(
                        role="user",
                        content="Continue with the task. Use tools to make progress.",
                    )
                )

    async def _execute_tool(self, name: str, args: dict) -> str:
        """Execute an agent tool and return the result as a string."""
        try:
            if name == "act":
                result = self.debugger.execute_command(args.get("instruction", ""))
                return result.output if result.succeeded else f"Error: {result.error}"

            elif name == "set_breakpoint":
                location = args["location"]
                if location.startswith("0x"):
                    addr = int(location, 16)
                    bp = self.process._target.breakpoint_create_by_address(addr)
                else:
                    bp = self.process._target.breakpoint_create_by_name(location)
                return f"Breakpoint {bp.id} set at {location}"

            elif name == "read_memory":
                addr = int(args["address"], 16)
                size = args.get("size", 64)
                data = self.process.read_memory(addr, size)
                hex_str = data.hex()
                formatted = " ".join(hex_str[i : i + 2] for i in range(0, len(hex_str), 2))
                return f"Memory at {args['address']} ({size} bytes):\n{formatted}"

            elif name == "step":
                mode = args.get("mode", "over")
                thread = self.process.selected_thread
                if thread is None:
                    return "Error: no selected thread"
                if mode == "over":
                    thread.step_over()
                elif mode == "into":
                    thread.step_into()
                elif mode == "out":
                    thread.step_out()
                elif mode == "instruction":
                    thread.step_instruction()
                return f"Stepped {mode}"

            elif name == "continue_execution":
                self.process.continue_()
                return f"Process continued, state: {self.process.state}"

            elif name == "evaluate":
                frame = self.process.selected_thread.selected_frame
                result = frame.evaluate_expression(args["expression"])
                return f"Result: {result}"

            elif name == "done":
                return args.get("result", "Task completed")

            else:
                return f"Unknown tool: {name}"

        except Exception as e:
            return f"Error executing {name}: {e}"
