"""Example: extract structured vtable information from a C++ binary."""

from pydantic import BaseModel

from morgul.core import Morgul


class VTableEntry(BaseModel):
    index: int
    function_name: str | None = None
    address: int


class VTableInfo(BaseModel):
    class_name: str
    vtable_address: int
    entries: list[VTableEntry]
    num_entries: int


with Morgul() as morgul:
    morgul.start("/tmp/morgul_test")  # Replace with your C++ binary for vtable extraction

    # Set breakpoint and run to it
    morgul.act("set a breakpoint on main and continue")

    # Extract structured vtable information
    vtable = morgul.extract(
        instruction="Extract the vtable for the main polymorphic class. "
        "Look at the object pointer and read the vtable entries.",
        response_model=VTableInfo,
    )

    print(f"Class: {vtable.class_name}")
    print(f"VTable at: 0x{vtable.vtable_address:x}")
    print(f"Entries ({vtable.num_entries}):")
    for entry in vtable.entries:
        name = entry.function_name or "unknown"
        print(f"  [{entry.index}] {name} @ 0x{entry.address:x}")
