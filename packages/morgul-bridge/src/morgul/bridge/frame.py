"""Pythonic wrapper around LLDB's SBFrame."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    import lldb
except ImportError:
    lldb = None  # type: ignore[assignment]

from .types import RegisterValue, Variable


class Frame:
    """High-level wrapper around ``lldb.SBFrame``.

    Exposes registers, variables, expression evaluation, and disassembly
    through a clean Python interface.
    """

    def __init__(self, sb_frame: Any) -> None:
        self._sb = sb_frame

    # -- scalar properties -------------------------------------------------

    @property
    def pc(self) -> int:
        """Return the program counter."""
        return self._sb.GetPC()

    @property
    def sp(self) -> int:
        """Return the stack pointer."""
        return self._sb.GetSP()

    @property
    def fp(self) -> int:
        """Return the frame pointer."""
        return self._sb.GetFP()

    @property
    def index(self) -> int:
        """Return the frame index in the thread's frame list."""
        return self._sb.GetFrameID()

    @property
    def function_name(self) -> Optional[str]:
        """Return the name of the function this frame is in."""
        fn = self._sb.GetFunctionName()
        return fn if fn else None

    @property
    def module_name(self) -> Optional[str]:
        """Return the module (shared library) name for this frame."""
        mod = self._sb.GetModule()
        if mod and mod.IsValid():
            fs = mod.GetFileSpec()
            return fs.GetFilename() if fs.IsValid() else None
        return None

    @property
    def line_entry(self) -> Dict[str, Any]:
        """Return source location information.

        Returns
        -------
        dict
            Keys: ``file``, ``line``, ``col``.  Values are ``None``
            when debug information is unavailable.
        """
        le = self._sb.GetLineEntry()
        if le and le.IsValid():
            fs = le.GetFileSpec()
            return {
                "file": str(fs) if fs.IsValid() else None,
                "line": le.GetLine(),
                "col": le.GetColumn(),
            }
        return {"file": None, "line": None, "col": None}

    # -- registers ---------------------------------------------------------

    @property
    def registers(self) -> List[RegisterValue]:
        """Return all registers, flattened across register sets.

        Returns
        -------
        list[RegisterValue]
        """
        result: List[RegisterValue] = []
        reg_sets = self._sb.GetRegisters()
        for i in range(reg_sets.GetSize()):
            reg_set = reg_sets.GetValueAtIndex(i)
            for j in range(reg_set.GetNumChildren()):
                reg = reg_set.GetChildAtIndex(j)
                name = reg.GetName() or ""
                raw = reg.GetValueAsUnsigned(0)
                size = reg.GetByteSize()
                result.append(RegisterValue(name=name, value=raw, size=size))
        return result

    # -- variables ---------------------------------------------------------

    def variables(self, in_scope_only: bool = True) -> List[Variable]:
        """Return local variables visible in this frame.

        Parameters
        ----------
        in_scope_only:
            If ``True``, only return variables that are in scope.

        Returns
        -------
        list[Variable]
        """
        sb_vars = self._sb.GetVariables(
            True,   # arguments
            True,   # locals
            False,  # statics
            in_scope_only,
        )
        return [self._to_variable(sb_vars.GetValueAtIndex(i))
                for i in range(sb_vars.GetSize())]

    @property
    def arguments(self) -> List[Variable]:
        """Return function arguments for this frame."""
        sb_vars = self._sb.GetVariables(
            True,   # arguments
            False,  # locals
            False,  # statics
            True,   # in_scope_only
        )
        return [self._to_variable(sb_vars.GetValueAtIndex(i))
                for i in range(sb_vars.GetSize())]

    # -- expression evaluation ---------------------------------------------

    def evaluate_expression(self, expr: str) -> str:
        """Evaluate an expression in the context of this frame.

        Parameters
        ----------
        expr:
            The expression string (C, Objective-C, or Swift).

        Returns
        -------
        str
            The result value as a string, or an error message.
        """
        sb_val = self._sb.EvaluateExpression(expr)
        error = sb_val.GetError()
        if error.Fail():
            return f"error: {error}"
        return sb_val.GetValue() or sb_val.GetSummary() or ""

    # -- disassembly -------------------------------------------------------

    def disassemble(self, count: int = 20) -> str:
        """Disassemble instructions starting from the current PC.

        Parameters
        ----------
        count:
            Number of instructions to disassemble.

        Returns
        -------
        str
            Human-readable disassembly text.
        """
        target = self._sb.GetThread().GetProcess().GetTarget()
        sb_insns = target.ReadInstructions(
            self._sb.GetPCAddress(), count
        )
        lines: List[str] = []
        for i in range(sb_insns.GetSize()):
            insn = sb_insns.GetInstructionAtIndex(i)
            addr = insn.GetAddress().GetLoadAddress(target)
            mnemonic = insn.GetMnemonic(target)
            operands = insn.GetOperands(target)
            lines.append(f"  {addr:#x}: {mnemonic} {operands}")
        return "\n".join(lines)

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _to_variable(sb_val: Any, max_depth: int = 3, _depth: int = 0) -> Variable:
        """Convert an ``SBValue`` to a :class:`Variable`.

        Recursively expands struct/pointer children up to *max_depth*
        levels, so the LLM can see fields like ``ctx->palette_size``
        rather than just the raw pointer address.
        """
        addr_val = sb_val.GetLoadAddress()
        address = addr_val if addr_val != lldb.LLDB_INVALID_ADDRESS else None

        # For pointers, dereference to get the pointee's children.
        # This makes `ctx` (an ImageCtx*) show its struct fields.
        deref = sb_val
        type_class = sb_val.GetType().GetTypeClass()
        # lldb.eTypeClassPointer == 1 << 16 == 65536
        if type_class == 65536 and sb_val.GetNumChildren() == 1:
            pointee = sb_val.Dereference()
            if pointee.IsValid() and pointee.GetError().Success():
                deref = pointee

        children: list[Variable] = []
        if _depth < max_depth:
            num_children = deref.GetNumChildren()
            # Cap children to avoid blowing up on large arrays
            for i in range(min(num_children, 32)):
                child = deref.GetChildAtIndex(i)
                if child.IsValid():
                    children.append(
                        Frame._to_variable(child, max_depth=max_depth, _depth=_depth + 1)
                    )

        return Variable(
            name=sb_val.GetName() or "",
            type_name=sb_val.GetTypeName() or "",
            value=sb_val.GetValue() or sb_val.GetSummary() or "",
            address=address,
            size=sb_val.GetByteSize() or None,
            children=children,
        )
