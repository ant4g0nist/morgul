"""Command execution helpers for the LLDB bridge.

Provides convenience functions for running LLDB CLI commands and
formatting output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from .types import CommandResult

if TYPE_CHECKING:
    from .debugger import Debugger
    from .frame import Frame


def run_command(debugger: Debugger, command: str) -> CommandResult:
    """Execute a single LLDB CLI command.

    Parameters
    ----------
    debugger:
        The :class:`Debugger` instance to run the command on.
    command:
        The LLDB command string.

    Returns
    -------
    CommandResult
    """
    return debugger.execute_command(command)


def run_commands(
    debugger: Debugger, commands: List[str]
) -> List[CommandResult]:
    """Execute multiple LLDB CLI commands sequentially.

    Parameters
    ----------
    debugger:
        The :class:`Debugger` instance to run the commands on.
    commands:
        A list of LLDB command strings.

    Returns
    -------
    list[CommandResult]
    """
    return [debugger.execute_command(cmd) for cmd in commands]


def format_disassembly(frame: Frame, count: int = 20) -> str:
    """Disassemble instructions from the current PC and format them.

    This is a convenience wrapper around :meth:`Frame.disassemble` that
    adds a header with the function name and PC address.

    Parameters
    ----------
    frame:
        The frame to disassemble from.
    count:
        Number of instructions to disassemble.

    Returns
    -------
    str
        Formatted disassembly text with a descriptive header.
    """
    header_parts: List[str] = []
    fn_name = frame.function_name
    if fn_name:
        header_parts.append(fn_name)
    header_parts.append(f"@ {frame.pc:#x}")

    header = " ".join(header_parts)
    body = frame.disassemble(count)
    return f"{header}:\n{body}"
