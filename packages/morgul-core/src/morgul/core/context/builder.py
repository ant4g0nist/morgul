"""Context builder — prunes process state for LLM consumption."""

from __future__ import annotations

from morgul.core.context.snapshot import capture_snapshot
from morgul.core.types.context import ProcessSnapshot


class ContextBuilder:
    """Builds and prunes process context for LLM prompts.

    Manages token budget awareness by prioritizing the most relevant
    context: current function disassembly, registers, stack trace,
    and nearby variables.
    """

    def __init__(self, max_tokens: int = 4096):
        self.max_tokens = max_tokens

    def build(
        self,
        process,
        frame=None,
        include_memory_regions: bool = False,
        disassembly_count: int = 20,
    ) -> ProcessSnapshot:
        """Build a pruned process context snapshot."""
        snapshot = capture_snapshot(
            process,
            frame=frame,
            include_memory_regions=include_memory_regions,
            disassembly_count=disassembly_count,
        )
        return self._prune(snapshot)

    def _prune(self, snapshot: ProcessSnapshot) -> ProcessSnapshot:
        """Prune snapshot to fit within token budget.

        Priority order:
        1. Process state + stop reason + PC
        2. Registers (general purpose first)
        3. Current frame disassembly
        4. Stack trace (top N frames)
        5. Variables
        6. Modules (first N)
        7. Memory regions
        """
        estimated_tokens = self._estimate_tokens(snapshot)
        if estimated_tokens <= self.max_tokens:
            return snapshot

        # Progressively prune less important context
        pruned = snapshot.model_copy()

        # Trim memory regions first
        if pruned.memory_regions:
            pruned.memory_regions = []
            if self._estimate_tokens(pruned) <= self.max_tokens:
                return pruned

        # Trim modules to top 10
        if len(pruned.modules) > 10:
            pruned.modules = pruned.modules[:10]
            if self._estimate_tokens(pruned) <= self.max_tokens:
                return pruned

        # Trim stack trace to top 10 frames
        if pruned.stack_trace and len(pruned.stack_trace.frames) > 10:
            pruned.stack_trace.frames = pruned.stack_trace.frames[:10]
            if self._estimate_tokens(pruned) <= self.max_tokens:
                return pruned

        # Trim disassembly to first 500 chars
        if len(pruned.disassembly) > 500:
            pruned.disassembly = pruned.disassembly[:500] + "\n... (truncated)"
            if self._estimate_tokens(pruned) <= self.max_tokens:
                return pruned

        # Trim variables to top 10
        if len(pruned.variables) > 10:
            pruned.variables = pruned.variables[:10]

        return pruned

    def _estimate_tokens(self, snapshot: ProcessSnapshot) -> int:
        """Rough token estimate: ~4 chars per token."""
        text = snapshot.model_dump_json()
        return len(text) // 4

    def _platform_hints(self, target_triple: str) -> str:
        """Return platform-specific LLDB tips based on target triple."""
        hints: list[str] = []
        triple = target_triple.lower()

        if "arm64" in triple or "aarch64" in triple:
            hints.append(
                "arm64 calling convention: $x0-$x7 = arguments, $x0 = return value, "
                "$lr = return address, $fp = frame pointer."
            )
        elif "x86_64" in triple or "x86-64" in triple:
            hints.append(
                "x86_64 calling convention: $rdi, $rsi, $rdx, $rcx, $r8, $r9 = arguments, "
                "$rax = return value, $rbp = frame pointer."
            )
        elif "x86" in triple or "i386" in triple:
            hints.append(
                "x86 (32-bit) calling convention: arguments on stack, "
                "$eax = return value, $ebp = frame pointer."
            )

        return "\n".join(hints)

    def format_for_prompt(self, snapshot: ProcessSnapshot) -> str:
        """Format snapshot as a human-readable string for LLM prompts."""
        parts: list[str] = []

        if snapshot.target_triple:
            parts.append(f"Target: {snapshot.target_triple}")
            platform_hints = self._platform_hints(snapshot.target_triple)
            if platform_hints:
                parts.append(f"\n--- Platform Hints ---\n{platform_hints}")
        parts.append(f"Process State: {snapshot.process_state}")
        parts.append(f"Stop Reason: {snapshot.stop_reason}")
        if snapshot.pc is not None:
            parts.append(f"PC: 0x{snapshot.pc:x}")

        if snapshot.registers:
            parts.append("\n--- Registers ---")
            for reg in snapshot.registers:
                parts.append(f"  {reg.name} = 0x{reg.value:x}")

        if snapshot.stack_trace:
            parts.append(f"\n--- Stack Trace (thread {snapshot.stack_trace.thread_id}) ---")
            for f in snapshot.stack_trace.frames:
                loc = f.function_name or f"0x{f.pc:x}"
                mod = f" [{f.module_name}]" if f.module_name else ""
                src = f" at {f.file}:{f.line}" if f.file and f.line else ""
                parts.append(f"  #{f.index}: {loc}{mod}{src}")

        if snapshot.disassembly:
            parts.append("\n--- Disassembly ---")
            parts.append(snapshot.disassembly)

        if snapshot.variables:
            parts.append("\n--- Variables ---")
            self._format_variables(snapshot.variables, parts, indent=2)

        if snapshot.modules:
            parts.append(f"\n--- Modules ({len(snapshot.modules)}) ---")
            for m in snapshot.modules[:10]:
                parts.append(f"  {m.name} @ 0x{m.base_address:x}")

        return "\n".join(parts)

    def _format_variables(self, variables: list, parts: list, indent: int = 2) -> None:
        """Recursively format variables with struct field expansion."""
        prefix = " " * indent
        for v in variables:
            name = v.get("name", "?")
            type_name = v.get("type", "?")
            value = v.get("value", "?")
            parts.append(f"{prefix}{name}: {type_name} = {value}")
            children = v.get("children", [])
            if children:
                self._format_variables(children, parts, indent=indent + 4)
