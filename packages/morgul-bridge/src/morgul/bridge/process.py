"""Pythonic wrapper around LLDB's SBProcess."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

try:
    import lldb
except ImportError:
    lldb = None  # type: ignore[assignment]

from .types import ProcessState

if TYPE_CHECKING:
    from .target import Target
    from .thread import Thread

# Map LLDB integer state constants to our ProcessState enum.
_STATE_MAP: Dict[int, ProcessState] = {}


def _build_state_map() -> None:
    """Populate ``_STATE_MAP`` lazily once LLDB is available."""
    if _STATE_MAP or lldb is None:
        return
    _STATE_MAP.update(
        {
            lldb.eStateInvalid: ProcessState.INVALID,
            lldb.eStateUnloaded: ProcessState.UNLOADED,
            lldb.eStateConnected: ProcessState.CONNECTED,
            lldb.eStateAttaching: ProcessState.ATTACHING,
            lldb.eStateLaunching: ProcessState.LAUNCHING,
            lldb.eStateStopped: ProcessState.STOPPED,
            lldb.eStateRunning: ProcessState.RUNNING,
            lldb.eStateStepping: ProcessState.STEPPING,
            lldb.eStateCrashed: ProcessState.CRASHED,
            lldb.eStateDetached: ProcessState.DETACHED,
            lldb.eStateExited: ProcessState.EXITED,
            lldb.eStateSuspended: ProcessState.SUSPENDED,
        }
    )


class Process:
    """High-level wrapper around ``lldb.SBProcess``.

    Provides methods for controlling execution and reading/writing memory.
    """

    def __init__(self, sb_process: Any, target: Target) -> None:
        self._sb = sb_process
        self._target = target
        _build_state_map()

    # -- properties --------------------------------------------------------

    @property
    def state(self) -> ProcessState:
        """Return the current process state as a :class:`ProcessState`."""
        raw = self._sb.GetState()
        return _STATE_MAP.get(raw, ProcessState.INVALID)

    @property
    def pid(self) -> int:
        """Return the process ID."""
        return self._sb.GetProcessID()

    @property
    def exit_status(self) -> int:
        """Return the exit status (only valid after the process has exited)."""
        return self._sb.GetExitStatus()

    @property
    def exit_description(self) -> str:
        """Return a textual description of the exit reason."""
        return self._sb.GetExitDescription() or ""

    @property
    def threads(self) -> List[Thread]:
        """Return all threads in the process."""
        from .thread import Thread

        return [
            Thread(self._sb.GetThreadAtIndex(i))
            for i in range(self._sb.GetNumThreads())
        ]

    @property
    def selected_thread(self) -> Thread:
        """Return the currently selected thread."""
        from .thread import Thread

        return Thread(self._sb.GetSelectedThread())

    @property
    def num_threads(self) -> int:
        """Return the number of threads."""
        return self._sb.GetNumThreads()

    # -- execution control -------------------------------------------------

    def continue_(self) -> None:
        """Resume execution of the process."""
        error = self._sb.Continue()
        if error and not error.Success():
            raise RuntimeError(f"Failed to continue: {error}")

    def stop(self) -> None:
        """Halt the process."""
        error = self._sb.Stop()
        if error and not error.Success():
            raise RuntimeError(f"Failed to stop: {error}")

    def kill(self) -> None:
        """Kill the process."""
        error = self._sb.Kill()
        if error and not error.Success():
            raise RuntimeError(f"Failed to kill process: {error}")

    def detach(self) -> None:
        """Detach from the process."""
        error = self._sb.Detach()
        if error and not error.Success():
            raise RuntimeError(f"Failed to detach: {error}")

    # -- memory ------------------------------------------------------------

    def read_memory(self, address: int, size: int) -> bytes:
        """Read *size* bytes from the process address space.

        Parameters
        ----------
        address:
            Start address to read from.
        size:
            Number of bytes to read.

        Returns
        -------
        bytes
        """
        error = lldb.SBError()
        data = self._sb.ReadMemory(address, size, error)
        if error.Fail():
            raise RuntimeError(
                f"Failed to read {size} bytes at {address:#x}: {error}"
            )
        return bytes(data)

    def write_memory(self, address: int, data: bytes) -> int:
        """Write *data* into the process address space.

        Parameters
        ----------
        address:
            Start address to write to.
        data:
            The bytes to write.

        Returns
        -------
        int
            The number of bytes actually written.
        """
        error = lldb.SBError()
        written = self._sb.WriteMemory(address, data, error)
        if error.Fail():
            raise RuntimeError(
                f"Failed to write {len(data)} bytes at {address:#x}: {error}"
            )
        return written
