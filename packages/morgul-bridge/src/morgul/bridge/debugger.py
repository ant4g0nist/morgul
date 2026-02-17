"""Pythonic wrapper around LLDB's SBDebugger."""

from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

try:
    import lldb
except ImportError:
    lldb = None  # type: ignore[assignment]

from .types import CommandResult

if TYPE_CHECKING:
    from .process import Process
    from .target import Target


def _require_lldb() -> None:
    """Raise a clear error when LLDB is not available."""
    if lldb is None:
        raise RuntimeError(
            "The 'lldb' Python module is not available. "
            "Ensure LLDB is installed and its Python bindings are on your PYTHONPATH. "
            "On macOS this is typically provided by Xcode or the Command Line Tools."
        )


class Debugger:
    """High-level wrapper around ``lldb.SBDebugger``.

    Usage::

        with Debugger() as dbg:
            target = dbg.create_target("/path/to/binary")
    """

    def __init__(self) -> None:
        _require_lldb()
        lldb.SBDebugger.Initialize()
        self._sb = lldb.SBDebugger.Create()
        self._sb.SetAsync(False)
        # Suppress interactive prompts (e.g. "kill it and restart?")
        self.execute_command("settings set auto-confirm true")

    # -- context manager ---------------------------------------------------

    def __enter__(self) -> Debugger:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self.destroy()

    # -- properties --------------------------------------------------------

    @property
    def async_mode(self) -> bool:
        """Return whether the debugger operates asynchronously."""
        return self._sb.GetAsync()

    @async_mode.setter
    def async_mode(self, value: bool) -> None:
        self._sb.SetAsync(value)

    # -- public API --------------------------------------------------------

    def create_target(self, path: str) -> Target:
        """Create a target from an executable path.

        Parameters
        ----------
        path:
            Filesystem path to the binary.

        Returns
        -------
        Target
            A wrapper around the newly-created ``SBTarget``.

        Raises
        ------
        RuntimeError
            If LLDB fails to create the target.
        """
        from .target import Target

        sb_target = self._sb.CreateTarget(path)
        if not sb_target or not sb_target.IsValid():
            raise RuntimeError(f"Failed to create target for '{path}'")
        return Target(sb_target)

    def attach(self, pid: int) -> Tuple[Target, Process]:
        """Attach to a running process by PID.

        Returns
        -------
        tuple[Target, Process]
            The target and process wrappers for the attached process.
        """
        from .process import Process
        from .target import Target

        error = lldb.SBError()
        sb_target = self._sb.CreateTarget("")
        if not sb_target or not sb_target.IsValid():
            raise RuntimeError("Failed to create empty target for attach")

        sb_process = sb_target.AttachToProcessWithID(
            self._sb.GetListener(), pid, error
        )
        if error.Fail():
            raise RuntimeError(f"Failed to attach to PID {pid}: {error}")

        target = Target(sb_target)
        process = Process(sb_process, target)
        return target, process

    def attach_by_name(self, name: str) -> Tuple[Target, Process]:
        """Attach to a running process by name.

        Parameters
        ----------
        name:
            The process name to attach to.

        Returns
        -------
        tuple[Target, Process]
            The target and process wrappers for the attached process.
        """
        from .process import Process
        from .target import Target

        error = lldb.SBError()
        sb_target = self._sb.CreateTarget("")
        if not sb_target or not sb_target.IsValid():
            raise RuntimeError("Failed to create empty target for attach")

        sb_process = sb_target.AttachToProcessWithName(
            self._sb.GetListener(), name, False, error
        )
        if error.Fail():
            raise RuntimeError(f"Failed to attach to process '{name}': {error}")

        target = Target(sb_target)
        process = Process(sb_process, target)
        return target, process

    def execute_command(self, command: str) -> CommandResult:
        """Execute an LLDB CLI command and return the result.

        Parameters
        ----------
        command:
            The LLDB command string (e.g. ``"bt"``).

        Returns
        -------
        CommandResult
            Captured output, error text, and success flag.
        """
        ret = lldb.SBCommandReturnObject()
        interpreter = self._sb.GetCommandInterpreter()
        interpreter.HandleCommand(command, ret)
        return CommandResult(
            output=ret.GetOutput() or "",
            error=ret.GetError() or "",
            succeeded=ret.Succeeded(),
        )

    def destroy(self) -> None:
        """Destroy the underlying debugger instance and release resources."""
        if self._sb is not None:
            lldb.SBDebugger.Destroy(self._sb)
            self._sb = None  # type: ignore[assignment]
