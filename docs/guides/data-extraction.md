# Guide: Structured Data Extraction

## Overview

Use `extract()` to pull typed, structured data from live process state. You define a Pydantic model describing the shape of the data you want, and Morgul reads the debugger state and returns a populated instance of that model.

## VTable Extraction Example

This complete example shows how to extract C++ vtable information from a running process.

```python
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
    morgul.start("./test_binary")
    morgul.act("set a breakpoint on main and continue")

    vtable = morgul.extract(
        instruction="Extract the vtable for the main polymorphic class. "
        "Look at the object pointer and read the vtable entries.",
        response_model=VTableInfo,
    )

    print(f"Class: {vtable.class_name}")
    print(f"VTable at: 0x{vtable.vtable_address:x}")
    for entry in vtable.entries:
        name = entry.function_name or "unknown"
        print(f"  [{entry.index}] {name} @ 0x{entry.address:x}")
```

## Designing Schemas

Good schema design makes a significant difference in extraction quality. Follow these guidelines:

- **Use `Optional` for uncertain fields.** Binary analysis is inherently uncertain. If a field might not be determinable (e.g., a function name for a stripped binary), give it a `None` default.

- **Keep schemas focused.** A schema that tries to capture everything about a function will produce worse results than one focused on a specific aspect (arguments, return value, side effects). Split large extractions into multiple targeted calls.

- **Use descriptive field names.** The LLM reads your field names as hints. `faulting_address` is better than `addr`. `is_heap_allocated` is better than `flag`.

- **Add field descriptions when the name alone is ambiguous.** Pydantic's `Field(description=...)` gives the LLM additional context about what a field should contain.

## Other Extraction Patterns

The same approach works for many kinds of binary data:

- **Function signatures**: Extract parameter types, return types, and calling conventions from disassembly.
- **Heap object layouts**: Map out the fields of a heap-allocated structure by reading memory at an object pointer.
- **String tables**: Extract arrays of strings from data sections or string pools.
- **Configuration structures**: Pull out config structs with their field values from a running process.

In each case, define a Pydantic model that matches the shape of the data, write an instruction that tells the LLM where to look and what to extract, and call `extract()`.
