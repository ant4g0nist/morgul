"""Pythonic wrapper around LLDB's SBThread."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

try:
    import lldb
except ImportError:
    lldb = None  # type: ignore[assignment]

from .types import StopReason

if TYPE_CHECKING:
    from .frame import Frame

# Map LLDB integer stop-reason constants to our StopReason enum.
_STOP_REASON_MAP: Dict[int, StopReason] = {}


def _build_stop_reason_map() -> None:
    """Populate ``_STOP_REASON_MAP`` lazily once LLDB is available."""
    if _STOP_REASON_MAP or lldb is None:
        return
    _STOP_REASON_MAP.update(
        {
            lldb.eStopReasonInvalid: StopReason.INVALID,
            lldb.eStopReasonNone: StopReason.NONE,
            lldb.eStopReasonTrace: StopReason.TRACE,
            lldb.eStopReasonBreakpoint: StopReason.BREAKPOINT,
            lldb.eStopReasonWatchpoint: StopReason.WATCHPOINT,
            lldb.eStopReasonSignal: StopReason.SIGNAL,
            lldb.eStopReasonException: StopReason.EXCEPTION,
            lldb.eStopReasonExec: StopReason.EXEC,
            lldb.eStopReasonPlanComplete: StopReason.PLAN_COMPLETE,
            lldb.eStopReasonThreadExiting: StopReason.THREAD_EXITING,
            lldb.eStopReasonInstrumentation: StopReason.INSTRUMENTATION,
        }
    )


class Thread:
    """High-level wrapper around ``lldb.SBThread``.

    Provides stepping controls and frame inspection.
    """

    def __init__(self, sb_thread: Any) -> None:
        self._sb = sb_thread
        _build_stop_reason_map()

    # -- properties --------------------------------------------------------

    @property
    def id(self) -> int:
        """Return the thread ID."""
        return self._sb.GetThreadID()

    @property
    def name(self) -> Optional[str]:
        """Return the thread name, if any."""
        return self._sb.GetName()

    @property
    def stop_reason(self) -> StopReason:
        """Return the reason the thread is stopped."""
        raw = self._sb.GetStopReason()
        return _STOP_REASON_MAP.get(raw, StopReason.INVALID)

    @property
    def num_frames(self) -> int:
        """Return the number of stack frames."""
        return self._sb.GetNumFrames()

    @property
    def selected_frame(self) -> Frame:
        """Return the currently selected frame."""
        from .frame import Frame

        return Frame(self._sb.GetSelectedFrame())

    # -- stepping ----------------------------------------------------------

    def step_over(self) -> None:
        """Step over the current source line."""
        self._sb.StepOver()

    def step_into(self) -> None:
        """Step into the current source line."""
        self._sb.StepInto()

    def step_out(self) -> None:
        """Step out of the current function."""
        self._sb.StepOut()

    def step_instruction(self, over: bool = False) -> None:
        """Step a single machine instruction.

        Parameters
        ----------
        over:
            If ``True``, step *over* calls; otherwise step *into* them.
        """
        self._sb.StepInstruction(over)

    # -- frame access ------------------------------------------------------

    def get_frames(self, count: Optional[int] = None) -> List[Frame]:
        """Return stack frames for this thread.

        Parameters
        ----------
        count:
            Maximum number of frames to return.  ``None`` returns all.

        Returns
        -------
        list[Frame]
        """
        from .frame import Frame

        total = self._sb.GetNumFrames()
        if count is not None:
            total = min(total, count)
        return [Frame(self._sb.GetFrameAtIndex(i)) for i in range(total)]

    # -- utilities ---------------------------------------------------------

    def run_to_address(self, address: int) -> None:
        """Resume this thread until it reaches *address*.

        Parameters
        ----------
        address:
            The target instruction address.
        """
        sb_addr = lldb.SBAddress(address, self._sb.GetProcess().GetTarget())
        self._sb.RunToAddress(sb_addr.GetLoadAddress(
            self._sb.GetProcess().GetTarget()
        ))
