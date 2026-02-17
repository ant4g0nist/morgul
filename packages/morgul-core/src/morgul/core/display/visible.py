"""Split-pane TUI for visible debugger mode.

Left pane:  LLDB — shows code execution, output, and debugger operations
Right pane: Chat — shows LLM reasoning and AI responses

Uses Rich Layout + Live for a Stagehand-style full-screen split view.
"""

from __future__ import annotations

import re
import shutil
import time
from collections import deque

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from morgul.core.events import ExecutionEvent, ExecutionEventType
from morgul.llm.events import LLMEvent

# Max lines to keep in each pane's history.
_MAX_HISTORY = 500

# Strip ```python ... ``` markers from LLM content for the chat pane.
_CODE_BLOCK_RE = re.compile(r"```python\s*\n(.*?)```", re.DOTALL)


def _terminal_size() -> tuple[int, int]:
    try:
        sz = shutil.get_terminal_size()
        return sz.columns, sz.lines
    except Exception:
        return 120, 40


class _PaneBuffer:
    """Scrollable line buffer for one pane."""

    def __init__(self, max_lines: int = _MAX_HISTORY):
        self._lines: deque[Text | Syntax] = deque(maxlen=max_lines)

    def add(self, item: Text | Syntax) -> None:
        self._lines.append(item)

    def add_text(self, text: str, style: str = "") -> None:
        self._lines.append(Text(text, style=style))

    def add_blank(self) -> None:
        self._lines.append(Text(""))

    def render(self, height: int) -> Group:
        """Return the last *height* items for display (auto-scroll)."""
        items = list(self._lines)
        visible = items[-height:] if len(items) > height else items
        if not visible:
            visible = [Text("", style="dim")]
        return Group(*visible)


class VisibleDisplay:
    """Full-screen split-pane TUI: LLDB on the left, Chat on the right.

    Both panes auto-scroll to the bottom. Code is syntax-highlighted in the
    LLDB pane; LLM reasoning is shown in the Chat pane.
    """

    def __init__(self):
        self._console = Console(stderr=True)
        self._lldb = _PaneBuffer()
        self._chat = _PaneBuffer()
        self._live: Live | None = None
        self._step_count = 0
        self._start_time = time.monotonic()
        self._llm_label: str | None = None

    def start(self) -> None:
        """Start the full-screen live TUI."""
        self._start_time = time.monotonic()
        self._lldb.add_text("session started", style="bold green")
        self._lldb.add_blank()
        self._chat.add_text("waiting for AI...", style="dim")
        self._live = Live(
            self._render(),
            console=self._console,
            refresh_per_second=4,
            screen=True,  # full-screen: takes over the terminal
        )
        self._live.start()

    def stop(self) -> None:
        """Stop the live TUI and restore the terminal."""
        if self._live is not None:
            elapsed = time.monotonic() - self._start_time
            self._lldb.add_blank()
            self._lldb.add_text(
                f"session ended ({self._step_count} steps, {elapsed:.1f}s)",
                style="bold green",
            )
            self._refresh()
            # Small pause so the user sees the final state
            import time as _t
            _t.sleep(0.5)
            self._live.stop()
            self._live = None

    def __enter__(self) -> VisibleDisplay:
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()

    def _render(self) -> Layout:
        """Build the full-screen split-pane layout."""
        cols, rows = _terminal_size()
        # Panel borders + title/subtitle take ~4 lines
        pane_h = max(rows - 2, 10)
        inner_h = max(pane_h - 4, 6)  # content lines inside panel

        elapsed = time.monotonic() - self._start_time
        lldb_subtitle = f"step {self._step_count} | {elapsed:.0f}s"
        if self._llm_label:
            lldb_subtitle += " | thinking..."

        left = Panel(
            self._lldb.render(inner_h),
            title="[bold green]LLDB[/bold green]",
            subtitle=f"[dim]{lldb_subtitle}[/dim]",
            border_style="green",
            padding=(0, 1),
            height=pane_h,
        )

        right = Panel(
            self._chat.render(inner_h),
            title="[bold blue]Chat[/bold blue]",
            subtitle="[dim]AI reasoning[/dim]",
            border_style="blue",
            padding=(0, 1),
            height=pane_h,
        )

        layout = Layout()
        layout.split_row(
            Layout(left, name="lldb", ratio=1),
            Layout(right, name="chat", ratio=1),
        )
        return layout

    def _refresh(self) -> None:
        if self._live is not None:
            self._live.update(self._render())

    def on_execution_event(self, event: ExecutionEvent) -> None:
        """Handle execution events — code/output to LLDB pane, reasoning to Chat."""
        if event.event_type == ExecutionEventType.CODE_START:
            self._step_count += 1
            self._lldb.add_blank()
            self._lldb.add_text(
                f">>> step {self._step_count}",
                style="bold cyan",
            )
            if event.code:
                code = event.code.rstrip()
                lines = code.splitlines()
                if len(lines) > 15:
                    head = "\n".join(lines[:10])
                    tail = "\n".join(lines[-4:])
                    skipped = len(lines) - 14
                    code = f"{head}\n# ... ({skipped} more lines)\n{tail}"
                self._lldb.add(
                    Syntax(code, "python", theme="monokai", line_numbers=False)
                )

        elif event.event_type == ExecutionEventType.CODE_END:
            if event.succeeded:
                self._lldb.add_text(
                    f"ok ({event.duration:.2f}s)", style="green"
                )
            else:
                self._lldb.add_text(
                    f"FAIL ({event.duration:.2f}s)", style="bold red"
                )
            if event.stdout.strip():
                for line in event.stdout.strip().splitlines()[:15]:
                    self._lldb.add_text(line, style="green")
                remaining = len(event.stdout.strip().splitlines()) - 15
                if remaining > 0:
                    self._lldb.add_text(
                        f"... ({remaining} more lines)", style="dim"
                    )
            if event.stderr.strip():
                for line in event.stderr.strip().splitlines()[:8]:
                    self._lldb.add_text(line, style="red")

        elif event.event_type == ExecutionEventType.HEAL_START:
            attempt = event.metadata.get("attempt", "?")
            max_retries = event.metadata.get("max_retries", "?")
            self._lldb.add_blank()
            self._lldb.add_text(
                f"heal {attempt}/{max_retries}", style="bold yellow"
            )

        elif event.event_type == ExecutionEventType.HEAL_END:
            if event.succeeded:
                self._lldb.add_text("healed", style="bold green")
            else:
                self._lldb.add_text("heal failed", style="bold red")
                if event.stderr.strip():
                    for line in event.stderr.strip().splitlines()[:4]:
                        self._lldb.add_text(line, style="red")

        elif event.event_type == ExecutionEventType.REPL_STEP:
            step = event.metadata.get("step", "?")
            max_iter = event.metadata.get("max_iterations", "?")
            self._lldb.add_blank()
            self._lldb.add_text(
                f"─── repl {step}/{max_iter} ───",
                style="bold magenta",
            )
            self._chat.add_blank()
            self._chat.add_text(
                f"─── step {step}/{max_iter} ───",
                style="bold magenta",
            )

        elif event.event_type == ExecutionEventType.LLM_RESPONSE:
            content = event.metadata.get("content", "")
            if content:
                # Extract reasoning (non-code text) for the Chat pane.
                # Keep a short summary of code blocks instead of stripping entirely.
                parts = _CODE_BLOCK_RE.split(content)
                for i, part in enumerate(parts):
                    text = part.strip()
                    if not text:
                        continue
                    if i % 2 == 0:
                        # Reasoning text
                        for line in text.splitlines():
                            self._chat.add_text(line, style="")
                    else:
                        # This is a captured code block body — show a brief summary
                        code_lines = text.strip().splitlines()
                        if code_lines:
                            preview = code_lines[0][:60]
                            if len(code_lines) > 1:
                                preview += f"  ({len(code_lines)} lines)"
                            self._chat.add_text(
                                f"  >> {preview}", style="dim cyan"
                            )

        self._refresh()

    def on_llm_event(self, event: LLMEvent, is_start: bool) -> None:
        """Handle LLM events — show in chat pane."""
        if is_start:
            label = event.model_type or event.method
            self._llm_label = label
            self._chat.add_text(f"thinking ({label})...", style="dim italic")
        else:
            self._llm_label = None
            if event.error:
                self._chat.add_text(f"error: {event.error}", style="bold red")
            else:
                tokens = ""
                if event.usage:
                    tokens = f" | {event.usage.input_tokens}+{event.usage.output_tokens} tok"
                self._chat.add_text(
                    f"{event.duration:.1f}s{tokens}",
                    style="dim",
                )
        self._refresh()
