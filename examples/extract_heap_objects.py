"""Extract complex heap structures into typed Pydantic models.

Demonstrates using extract() to pull structured data from memory — useful for
heap analysis, object introspection, and reverse engineering data formats.
"""

from typing import Optional

from pydantic import BaseModel

from morgul.core import Morgul


class HeapChunk(BaseModel):
    """A single heap chunk (malloc metadata)."""
    address: int
    size: int
    in_use: bool
    prev_size: int = 0


class HeapObject(BaseModel):
    """An application-level object living on the heap."""
    address: int
    type_name: Optional[str] = None
    size: int
    fields: dict[str, str] = {}  # field_name -> value as string


class HeapSummary(BaseModel):
    """Summary of the heap state around a pointer."""
    target_address: int
    chunks: list[HeapChunk]
    objects: list[HeapObject]
    total_allocated: int
    fragmentation_pct: float = 0.0
    notes: str = ""


with Morgul() as morgul:
    morgul.start("/tmp/morgul_test")

    # Run to a point where the heap is populated
    morgul.act("set a breakpoint on process_input and continue")
    morgul.act("step over until after the malloc calls return")

    # Extract the heap layout around the object of interest
    summary = morgul.extract(
        instruction=(
            "Examine the heap state. Look at the pointer in x0 (or rdi on x86). "
            "Walk the malloc metadata to find surrounding chunks. "
            "For each chunk, determine its size, whether it is in use, and "
            "try to identify the application-level object type if possible."
        ),
        response_model=HeapSummary,
    )

    print(f"Heap around 0x{summary.target_address:x}")
    print(f"Total allocated: {summary.total_allocated} bytes")
    print(f"Fragmentation: {summary.fragmentation_pct:.1f}%")
    print()

    print("Chunks:")
    for chunk in summary.chunks:
        status = "USED" if chunk.in_use else "FREE"
        print(f"  0x{chunk.address:x}  {chunk.size:>8} bytes  [{status}]")

    if summary.objects:
        print("\nIdentified objects:")
        for obj in summary.objects:
            type_str = obj.type_name or "unknown"
            print(f"  0x{obj.address:x}  {type_str}  ({obj.size} bytes)")
            for field, value in obj.fields.items():
                print(f"    .{field} = {value}")

    if summary.notes:
        print(f"\nNotes: {summary.notes}")
