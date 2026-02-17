# Guide: Caching and Self-Healing

> **Experimental / Work in Progress:** The content-addressed caching system is functional but still under active development. Cache key strategies, storage formats, and invalidation behaviour may change in future releases.

## Content-Addressed Caching

Morgul caches analysis results keyed on function bytes, not addresses. This means:

- ASLR and relocation do not invalidate the cache.
- The same function in a different run produces a cache hit.
- Recompiling with changes to a function invalidates only that function's cache entry.

### Configuration

```toml
[cache]
enabled = true
directory = ".morgul/cache"
```

### How It Works

All three primitives — `act()`, `extract()`, and `observe()` — are cached. The cache key is a sha256 hash of the instruction text and the process context (function bytes, disassembly, registers). Because the key is derived from content rather than addresses, ASLR has no effect.

On a **cache miss**, the LLM is called and the result is stored. On a **cache hit**, the stored result is returned immediately — no LLM call, no tokens spent.

Cache hits are logged at `INFO` level:

```
morgul.core.translate.engine | Cache hit: a3f8c1e9b2d04f17
```

### Example

```python
# First call: LLM analyzes (slow, costs tokens)
result = morgul.extract("what does this function do?", response_model=FuncSummary)

# Second call, same function bytes: instant cache hit
result = morgul.extract("what does this function do?", response_model=FuncSummary)
```

The second call returns immediately with the cached result. No LLM invocation occurs.

The same applies to `act()` and `observe()`:

```python
# act() caching
r1 = morgul.act("set a breakpoint on main")  # cache miss → LLM call
r2 = morgul.act("set a breakpoint on main")  # cache hit → instant

# observe() caching
o1 = morgul.observe()  # cache miss → LLM call
o2 = morgul.observe()  # cache hit → instant
```

See `examples/caching_demo.py` for a runnable demonstration with timing output.

## Self-Healing

When generated code raises an exception, Morgul does not simply raise an error. Instead, it attempts to recover automatically.

### How It Works

1. Re-snapshots the process state after the failure.
2. Feeds the Python traceback back to the LLM so it understands what went wrong.
3. Asks the LLM for an alternative approach.
4. Retries the operation (up to `max_retries`).

### Configuration

```toml
[healing]
enabled = true
max_retries = 3
```

You can also set `self_heal = true` at the top level of `morgul.toml` as a shorthand.

### Example Scenario

You wrote `act("break on validate_license")` against v1.0 of a target binary. In v1.1, the function was renamed to `check_entitlement`. When Morgul tries to set the breakpoint and fails:

1. It detects that the symbol `validate_license` does not exist.
2. It re-snapshots the process state, including the available symbol table.
3. It sends the error context to the LLM, which uses fuzzy symbol matching to find `check_entitlement` as the likely equivalent.
4. It sets the breakpoint on the new symbol and continues.

Your script works across versions without modification.

## Disabling

To disable caching:

```toml
[cache]
enabled = false
```

To disable self-healing:

```toml
[healing]
enabled = false
```

Or at the top level:

```toml
self_heal = false
```
