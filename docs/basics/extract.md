# extract() - Structured Data Extraction

The `extract()` primitive pulls structured, typed data from the live process state. You define a Pydantic schema describing the shape of data you want, and Morgul returns a populated instance.

## Signature

```python
morgul.extract(instruction: str, response_model: Type[T]) -> T
```

Returns an instance of your Pydantic model `T`, populated with data extracted from the live process.

## Defining a Schema

Use standard Pydantic models to define the structure of the data you want:

```python
from pydantic import BaseModel

class VulnContext(BaseModel):
    function_name: str
    buffer_size: int
    max_input_size: int
    bounds_checked: bool
```

The schema serves two purposes: it tells the LLM what information to look for, and it enforces type safety on the returned data.

## Using extract

```python
vuln = morgul.extract(
    "analyze the current function for buffer overflow potential",
    response_model=VulnContext,
)
print(f"{vuln.function_name}: buffer={vuln.buffer_size}, checked={vuln.bounds_checked}")
```

The `instruction` parameter guides the LLM on what process state to examine. The `response_model` defines the output shape. Together they give you precise, typed results.

## VTable Extraction Example

Here is a more involved example that extracts vtable information from a C++ binary:

```python
class VTableEntry(BaseModel):
    index: int
    function_name: str | None = None
    address: int

class VTableInfo(BaseModel):
    class_name: str
    vtable_address: int
    entries: list[VTableEntry]
    num_entries: int

vtable = morgul.extract(
    "extract the vtable for the main polymorphic class",
    response_model=VTableInfo,
)
for entry in vtable.entries:
    print(f"  [{entry.index}] {entry.function_name} @ 0x{entry.address:x}")
```

This demonstrates nested models, optional fields, and working with complex binary structures through natural language.

## Tips

- **Keep schemas focused.** Extract one concept at a time rather than trying to capture everything in a single model. A focused schema leads to more accurate results.
- **Use `Optional` fields** for data that may not be available. Not every process state will have every piece of information you ask for.
- **The instruction guides what state the LLM examines; the schema defines the output shape.** A good instruction narrows the LLM's attention to the relevant part of the process, while the schema ensures you get back exactly the structure you need.
- **Validate after extraction.** Even though Pydantic enforces types, you may want to add domain-specific validation (e.g., checking that an address falls within a valid range).

## When to Use extract vs act

The distinction is straightforward:

- **extract** -- read and analyze data from the process. Does not change process state.
- **act** -- perform actions that change state (set breakpoints, step, continue, write memory).

If you need to both act and then extract data from the result, call `act()` first, then call `extract()` to analyze the new state.

## See Also

- [act() - Execute Debugging Actions](act.md)
- [Data Extraction Guide](../guides/data-extraction.md)
