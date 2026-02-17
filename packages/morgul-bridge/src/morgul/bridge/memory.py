"""Memory utility functions for reading and writing process memory.

All functions accept a :class:`~morgul.bridge.process.Process` instance
as their first argument.
"""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING, List

try:
    import lldb
except ImportError:
    lldb = None  # type: ignore[assignment]

from .types import MemoryRegion

if TYPE_CHECKING:
    from .process import Process


# ---------------------------------------------------------------------------
# String reading
# ---------------------------------------------------------------------------

def read_string(process: Process, address: int, max_length: int = 256) -> str:
    """Read a NUL-terminated C string from *address*.

    Parameters
    ----------
    process:
        The process to read from.
    address:
        Start address of the string.
    max_length:
        Maximum number of bytes to read before giving up.

    Returns
    -------
    str
        The decoded string (stops at the first NUL byte).
    """
    data = process.read_memory(address, max_length)
    nul = data.find(b"\x00")
    if nul != -1:
        data = data[:nul]
    return data.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Pointer reading
# ---------------------------------------------------------------------------

def read_pointer(process: Process, address: int) -> int:
    """Read a pointer-sized integer from *address*.

    The pointer size is determined by the target architecture (4 or 8 bytes).
    """
    # Determine pointer size from the target's address byte size
    sb_target = process._sb.GetTarget()
    ptr_size = sb_target.GetAddressByteSize() if sb_target else 8
    data = process.read_memory(address, ptr_size)
    fmt = "<Q" if ptr_size == 8 else "<I"
    return struct.unpack(fmt, data)[0]


# ---------------------------------------------------------------------------
# Fixed-width integer reads
# ---------------------------------------------------------------------------

def read_uint8(process: Process, address: int) -> int:
    """Read an unsigned 8-bit integer."""
    return struct.unpack("B", process.read_memory(address, 1))[0]


def read_uint16(process: Process, address: int) -> int:
    """Read an unsigned 16-bit little-endian integer."""
    return struct.unpack("<H", process.read_memory(address, 2))[0]


def read_uint32(process: Process, address: int) -> int:
    """Read an unsigned 32-bit little-endian integer."""
    return struct.unpack("<I", process.read_memory(address, 4))[0]


def read_uint64(process: Process, address: int) -> int:
    """Read an unsigned 64-bit little-endian integer."""
    return struct.unpack("<Q", process.read_memory(address, 8))[0]


# ---------------------------------------------------------------------------
# Fixed-width integer writes
# ---------------------------------------------------------------------------

def write_uint8(process: Process, address: int, value: int) -> None:
    """Write an unsigned 8-bit integer."""
    process.write_memory(address, struct.pack("B", value))


def write_uint16(process: Process, address: int, value: int) -> None:
    """Write an unsigned 16-bit little-endian integer."""
    process.write_memory(address, struct.pack("<H", value))


def write_uint32(process: Process, address: int, value: int) -> None:
    """Write an unsigned 32-bit little-endian integer."""
    process.write_memory(address, struct.pack("<I", value))


def write_uint64(process: Process, address: int, value: int) -> None:
    """Write an unsigned 64-bit little-endian integer."""
    process.write_memory(address, struct.pack("<Q", value))


# ---------------------------------------------------------------------------
# Memory search
# ---------------------------------------------------------------------------

def search_memory(
    process: Process, start: int, size: int, pattern: bytes
) -> List[int]:
    """Search for *pattern* in a region of process memory.

    Parameters
    ----------
    process:
        The process to search in.
    start:
        Start address of the search region.
    size:
        Number of bytes to search.
    pattern:
        The byte pattern to look for.

    Returns
    -------
    list[int]
        Addresses where the pattern was found.
    """
    data = process.read_memory(start, size)
    matches: List[int] = []
    offset = 0
    while True:
        idx = data.find(pattern, offset)
        if idx == -1:
            break
        matches.append(start + idx)
        offset = idx + 1
    return matches


# ---------------------------------------------------------------------------
# Memory regions
# ---------------------------------------------------------------------------

def get_memory_regions(process: Process) -> List[MemoryRegion]:
    """Enumerate all memory regions mapped in the process.

    Returns
    -------
    list[MemoryRegion]
    """
    regions: List[MemoryRegion] = []
    region_list = process._sb.GetMemoryRegions()
    region_info = lldb.SBMemoryRegionInfo()
    for i in range(region_list.GetSize()):
        region_list.GetMemoryRegionAtIndex(i, region_info)
        regions.append(
            MemoryRegion(
                start=region_info.GetRegionBase(),
                end=region_info.GetRegionEnd(),
                readable=region_info.IsReadable(),
                writable=region_info.IsWritable(),
                executable=region_info.IsExecutable(),
                name=region_info.GetName() or None,
            )
        )
    return regions
