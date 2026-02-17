"""Demo: content-addressed caching skips duplicate LLM calls.

Prerequisites:
  ./examples/build_test_binary.sh   # builds /tmp/morgul_test

Run with:
    PYTHONPATH="$(lldb -P)" uv run python examples/caching_demo.py

First run of each instruction hits the LLM (cache miss).
Repeating the same instruction at the same state returns instantly (cache hit).
"""

import logging
import shutil
import sys
import time

from morgul.core import Morgul
from morgul.core.types.config import load_config
from morgul.llm.events import LLMEvent

# Show cache-hit log messages
logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")


def _on_llm(event: LLMEvent, is_start: bool) -> None:
    if is_start:
        label = event.model_type or event.method
        sys.stderr.write(f"  [llm: {label}...]\r")
        sys.stderr.flush()
    elif not event.error:
        tokens = ""
        if event.usage:
            tokens = f" {event.usage.input_tokens}+{event.usage.output_tokens}tok"
        sys.stderr.write(f"  [llm: {event.duration:.1f}s{tokens}]    \n")
        sys.stderr.flush()


config = load_config()

with Morgul(config=config, llm_event_callback=_on_llm) as morgul:
    morgul.start("/tmp/morgul_test")

    # ── act(): first call = cache miss (LLM) ───────────────────────
    t0 = time.perf_counter()
    r1 = morgul.act("set a breakpoint on main")
    elapsed_miss = time.perf_counter() - t0
    print(f"\n[1] act (miss): {r1.success}  elapsed={elapsed_miss:.2f}s")

    # ── act(): same instruction, same state = cache hit ─────────────
    t0 = time.perf_counter()
    r2 = morgul.act("set a breakpoint on main")
    elapsed_hit = time.perf_counter() - t0
    print(f"[2] act (hit):  {r2.success}  elapsed={elapsed_hit:.4f}s")

    # ── observe(): first call = cache miss ──────────────────────────
    t0 = time.perf_counter()
    o1 = morgul.observe()
    elapsed_miss_obs = time.perf_counter() - t0
    print(f"\n[3] observe (miss): {len(o1.actions)} actions  elapsed={elapsed_miss_obs:.2f}s")

    # ── observe(): same state = cache hit ───────────────────────────
    t0 = time.perf_counter()
    o2 = morgul.observe()
    elapsed_hit_obs = time.perf_counter() - t0
    print(f"[4] observe (hit):  {len(o2.actions)} actions  elapsed={elapsed_hit_obs:.4f}s")

    # ── Show cache directory ────────────────────────────────────────
    cache_dir = config.cache.directory
    print(f"\nCache directory: {cache_dir}/")

    # ── Clear cache and re-run (should be a miss again) ─────────────
    shutil.rmtree(cache_dir, ignore_errors=True)
    print("Cache cleared.")

    t0 = time.perf_counter()
    r3 = morgul.act("set a breakpoint on main")
    elapsed_cleared = time.perf_counter() - t0
    print(f"[5] act (miss after clear): {r3.success}  elapsed={elapsed_cleared:.2f}s")
