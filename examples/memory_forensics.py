"""Memory forensics: search memory, read structures, and extract patterns.

Demonstrates using act() and extract() for low-level memory analysis — useful
for malware analysis, exploit development, and data recovery from live processes.
"""

from typing import Optional

from pydantic import BaseModel

from morgul.core import Morgul


class StringHit(BaseModel):
    """A string found in memory."""
    address: int
    value: str
    section: Optional[str] = None


class MemoryMap(BaseModel):
    """Summary of the process memory layout."""
    text_start: int
    text_end: int
    heap_start: Optional[int] = None
    heap_end: Optional[int] = None
    stack_start: Optional[int] = None
    stack_end: Optional[int] = None
    num_regions: int
    writable_regions: int
    executable_regions: int


class SuspiciousPattern(BaseModel):
    """A suspicious byte pattern found in memory."""
    address: int
    pattern_type: str  # "shellcode", "rop_gadget", "format_string", etc.
    description: str
    hex_bytes: str


with Morgul() as morgul:
    morgul.start("/tmp/morgul_test")
    morgul.act("set a breakpoint on main and continue")

    # --- 1. Map the memory layout ---
    print("=== Memory Layout ===")
    mem_map = morgul.extract(
        instruction=(
            "Examine the process memory regions. Identify the text, heap, and "
            "stack segments. Count the total regions, writable regions, and "
            "executable regions."
        ),
        response_model=MemoryMap,
    )
    print(f"  .text:  0x{mem_map.text_start:x} - 0x{mem_map.text_end:x}")
    if mem_map.heap_start:
        print(f"  heap:   0x{mem_map.heap_start:x} - 0x{mem_map.heap_end or 0:x}")
    if mem_map.stack_start:
        print(f"  stack:  0x{mem_map.stack_start:x} - 0x{mem_map.stack_end or 0:x}")
    print(f"  regions:    {mem_map.num_regions}")
    print(f"  writable:   {mem_map.writable_regions}")
    print(f"  executable: {mem_map.executable_regions}")

    # --- 2. Search for interesting strings ---
    print("\n=== String Search ===")
    morgul.act("search memory for any URL strings (http:// or https://)")
    strings = morgul.extract(
        instruction=(
            "Find strings in the process memory that look like URLs, file paths, "
            "or API keys. Report their addresses and values."
        ),
        response_model=list[StringHit],
    )
    for hit in strings:
        print(f"  0x{hit.address:x}: {hit.value!r}")

    # --- 3. Read specific memory ---
    print("\n=== Stack Inspection ===")
    result = morgul.act("dump the first 64 bytes of the current stack frame")
    print(f"  {result.output[:300]}")

    # --- 4. Look for suspicious patterns ---
    print("\n=== Suspicious Patterns ===")
    patterns = morgul.extract(
        instruction=(
            "Scan the writable+executable memory regions for suspicious byte "
            "patterns: NOP sleds, shellcode signatures, ROP gadgets, or "
            "format string sequences. Report what you find."
        ),
        response_model=list[SuspiciousPattern],
    )
    if patterns:
        for p in patterns:
            print(f"  0x{p.address:x} [{p.pattern_type}]")
            print(f"    {p.description}")
            print(f"    bytes: {p.hex_bytes[:60]}")
    else:
        print("  No suspicious patterns found.")
