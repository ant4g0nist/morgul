"""morgul.bridge -- Pythonic wrapper around LLDB's SB API.

This package provides clean Python classes that hide LLDB's C++ naming
conventions behind an idiomatic interface.  LLDB must be available as a
Python module; if it is not, a clear ``RuntimeError`` is raised when
attempting to create a :class:`Debugger`.

Example::

    from morgul.bridge import Debugger

    with Debugger() as dbg:
        target = dbg.create_target("/path/to/binary")
        bp = target.breakpoint_create_by_name("main")
        process = target.launch()
        process.continue_()
"""

from __future__ import annotations

from .breakpoint import Breakpoint
from .commands import format_disassembly, run_command, run_commands
from .debugger import Debugger
from .frame import Frame
from .memory import (
    get_memory_regions,
    read_pointer,
    read_string,
    read_uint8,
    read_uint16,
    read_uint32,
    read_uint64,
    search_memory,
    write_uint8,
    write_uint16,
    write_uint32,
    write_uint64,
)
from .process import Process
from .target import Target
from .thread import Thread
from .types import (
    CommandResult,
    MemoryRegion,
    ModuleInfo,
    ProcessState,
    RegisterValue,
    StopReason,
    Variable,
)

__all__ = [
    # Core classes
    "Debugger",
    "Target",
    "Process",
    "Thread",
    "Frame",
    "Breakpoint",
    # Types
    "ProcessState",
    "StopReason",
    "RegisterValue",
    "Variable",
    "MemoryRegion",
    "ModuleInfo",
    "CommandResult",
    # Memory utilities
    "read_string",
    "read_pointer",
    "read_uint8",
    "read_uint16",
    "read_uint32",
    "read_uint64",
    "write_uint8",
    "write_uint16",
    "write_uint32",
    "write_uint64",
    "search_memory",
    "get_memory_regions",
    # Command helpers
    "run_command",
    "run_commands",
    "format_disassembly",
]
