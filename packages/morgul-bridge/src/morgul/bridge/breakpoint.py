"""Pythonic wrapper around LLDB's SBBreakpoint."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

try:
    import lldb
except ImportError:
    lldb = None  # type: ignore[assignment]

# Module-level registry: maps Breakpoint object id → callback callable.
_BP_CALLBACKS: Dict[int, Callable[..., bool]] = {}


def _invoke_bp_callback(
    bp_id: int, frame: Any, bp_loc: Any, extra_args: Any, internal_dict: Any
) -> bool:
    """Dispatch function called by LLDB's script callback body."""
    cb = _BP_CALLBACKS.get(bp_id)
    if cb is None:
        return True  # stop by default if callback was GC'd
    return cb(frame, bp_loc, extra_args)


class Breakpoint:
    """High-level wrapper around ``lldb.SBBreakpoint``.

    Provides a clean interface for enabling, disabling, conditioning,
    and inspecting breakpoints.
    """

    def __init__(self, sb_breakpoint: Any) -> None:
        self._sb = sb_breakpoint

    # -- properties --------------------------------------------------------

    @property
    def id(self) -> int:
        """Return the breakpoint ID."""
        return self._sb.GetID()

    @property
    def enabled(self) -> bool:
        """Return whether the breakpoint is enabled."""
        return self._sb.IsEnabled()

    @property
    def hit_count(self) -> int:
        """Return how many times the breakpoint has been hit."""
        return self._sb.GetHitCount()

    @property
    def num_locations(self) -> int:
        """Return the number of resolved locations."""
        return self._sb.GetNumLocations()

    @property
    def condition(self) -> Optional[str]:
        """Return the breakpoint condition expression, if any."""
        cond = self._sb.GetCondition()
        return cond if cond else None

    @property
    def locations(self) -> List[Dict[str, Any]]:
        """Return information about each resolved breakpoint location.

        Returns
        -------
        list[dict]
            Each dict contains ``address`` (int) and ``module`` (str).
        """
        result: List[Dict[str, Any]] = []
        for i in range(self._sb.GetNumLocations()):
            loc = self._sb.GetLocationAtIndex(i)
            sb_addr = loc.GetAddress()
            address = sb_addr.GetLoadAddress(
                sb_addr.GetModule().GetTarget()
                if sb_addr.GetModule() and sb_addr.GetModule().IsValid()
                else None
            ) if sb_addr.IsValid() else 0
            mod = sb_addr.GetModule() if sb_addr.IsValid() else None
            mod_name = (
                mod.GetFileSpec().GetFilename()
                if mod and mod.IsValid()
                else None
            )
            result.append({"address": address, "module": mod_name})
        return result

    # -- mutators ----------------------------------------------------------

    def set_condition(self, condition: str) -> None:
        """Set a conditional expression on this breakpoint.

        The breakpoint will only stop when *condition* evaluates to true.

        Parameters
        ----------
        condition:
            A C-like expression string.
        """
        self._sb.SetCondition(condition)

    def set_callback(self, callback: Callable[..., bool]) -> None:
        """Attach a Python callback to this breakpoint.

        The callback receives ``(frame, bp_loc, extra_args)`` and should
        return ``True`` to stop or ``False`` to auto-continue.

        Parameters
        ----------
        callback:
            A callable with the LLDB breakpoint callback signature.
        """
        self._callback = callback  # prevent GC

        # Register in the module-level registry so the script body can find it.
        _BP_CALLBACKS[id(self)] = callback

        # Clear any previous script callback, then install the dispatch body.
        self._sb.SetScriptCallbackFunction("")
        self._sb.SetScriptCallbackBody(
            f"import sys; sys.modules['{__name__}']._invoke_bp_callback("
            f"{id(self)}, frame, bp_loc, extra_args, internal_dict)"
        )

    def enable(self) -> None:
        """Enable this breakpoint."""
        self._sb.SetEnabled(True)

    def disable(self) -> None:
        """Disable this breakpoint without deleting it."""
        self._sb.SetEnabled(False)

    def delete(self) -> None:
        """Remove this breakpoint from its target.

        After calling this method, the breakpoint object should not be reused.
        """
        _BP_CALLBACKS.pop(id(self), None)
        target = self._sb.GetTarget()
        if target and target.IsValid():
            target.BreakpointDelete(self._sb.GetID())
