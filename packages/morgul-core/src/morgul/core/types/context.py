from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class RegisterInfo(BaseModel):
    """A single CPU register."""

    name: str
    value: int
    size: int = 8


class FrameInfo(BaseModel):
    """A single stack frame."""

    index: int
    function_name: Optional[str] = None
    module_name: Optional[str] = None
    pc: int
    file: Optional[str] = None
    line: Optional[int] = None


class StackTrace(BaseModel):
    """Stack trace for a thread."""

    frames: List[FrameInfo]
    thread_id: int
    thread_name: Optional[str] = None


class MemoryRegionInfo(BaseModel):
    """Description of a memory region."""

    start: int
    end: int
    readable: bool
    writable: bool
    executable: bool
    name: Optional[str] = None


class ModuleDetail(BaseModel):
    """A loaded module / shared library."""

    name: str
    path: str
    uuid: Optional[str] = None
    base_address: int


class ProcessSnapshot(BaseModel):
    """Complete snapshot of process state at a point in time."""

    registers: List[RegisterInfo]
    stack_trace: Optional[StackTrace] = None
    memory_regions: List[MemoryRegionInfo] = []
    modules: List[ModuleDetail] = []
    disassembly: str = ""
    variables: List[Dict[str, Any]] = []
    process_state: str = ""
    stop_reason: str = ""
    pc: Optional[int] = None
    target_triple: str = ""
