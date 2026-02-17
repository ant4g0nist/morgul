"""Bridge-level types for the LLDB wrapper.

Provides enums and dataclasses that map LLDB concepts to clean Python types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional


class ProcessState(Enum):
    """Maps LLDB process states to a Python enum."""

    INVALID = auto()
    UNLOADED = auto()
    CONNECTED = auto()
    ATTACHING = auto()
    LAUNCHING = auto()
    STOPPED = auto()
    RUNNING = auto()
    STEPPING = auto()
    CRASHED = auto()
    DETACHED = auto()
    EXITED = auto()
    SUSPENDED = auto()


class StopReason(Enum):
    """Maps LLDB stop reasons to a Python enum."""

    INVALID = auto()
    NONE = auto()
    TRACE = auto()
    BREAKPOINT = auto()
    WATCHPOINT = auto()
    SIGNAL = auto()
    EXCEPTION = auto()
    EXEC = auto()
    PLAN_COMPLETE = auto()
    THREAD_EXITING = auto()
    INSTRUMENTATION = auto()


@dataclass(frozen=True)
class RegisterValue:
    """A single register name/value pair."""

    name: str
    value: int
    size: int


@dataclass(frozen=True)
class Variable:
    """A local variable, argument, or global captured from a frame.

    For struct/pointer types, ``children`` contains the expanded fields,
    giving the LLM visibility into nested data (like how LLDB's
    ``frame variable`` prints struct members).
    """

    name: str
    type_name: str
    value: str
    address: Optional[int] = None
    size: Optional[int] = None
    children: List[Variable] = field(default_factory=list)


@dataclass(frozen=True)
class MemoryRegion:
    """Describes a contiguous region of process memory."""

    start: int
    end: int
    readable: bool
    writable: bool
    executable: bool
    name: Optional[str] = None


@dataclass(frozen=True)
class ModuleInfo:
    """Metadata about a loaded shared library or executable."""

    name: str
    path: str
    uuid: str
    base_address: int


@dataclass(frozen=True)
class CommandResult:
    """The result of executing an LLDB CLI command."""

    output: str
    error: str
    succeeded: bool
