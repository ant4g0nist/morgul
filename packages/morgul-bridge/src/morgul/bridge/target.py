"""Pythonic wrapper around LLDB's SBTarget."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    import lldb
except ImportError:
    lldb = None  # type: ignore[assignment]

from .types import ModuleInfo


class Target:
    """High-level wrapper around ``lldb.SBTarget``.

    Provides methods for launching processes, setting breakpoints,
    inspecting modules, and reading memory through the target.
    """

    def __init__(self, sb_target: Any) -> None:
        self._sb = sb_target

    # -- properties --------------------------------------------------------

    @property
    def path(self) -> str:
        """Return the file path of the target executable."""
        exe = self._sb.GetExecutable()
        if exe and exe.IsValid():
            return str(exe)
        return ""

    @property
    def triple(self) -> str:
        """Return the target triple (e.g. ``x86_64-apple-macosx``)."""
        return self._sb.GetTriple() or ""

    @property
    def byte_order(self) -> str:
        """Return the byte order as a human-readable string."""
        order = self._sb.GetByteOrder()
        if order == lldb.eByteOrderLittle:
            return "little"
        elif order == lldb.eByteOrderBig:
            return "big"
        return "unknown"

    @property
    def modules(self) -> List[ModuleInfo]:
        """Return metadata for every loaded module."""
        result: List[ModuleInfo] = []
        for i in range(self._sb.GetNumModules()):
            mod = self._sb.GetModuleAtIndex(i)
            if not mod.IsValid():
                continue
            file_spec = mod.GetFileSpec()
            # Base address: first section's load address or file address
            base = 0
            num_sections = mod.GetNumSections()
            if num_sections > 0:
                section = mod.GetSectionAtIndex(0)
                addr = section.GetLoadAddress(self._sb)
                if addr != lldb.LLDB_INVALID_ADDRESS:
                    base = addr
                else:
                    base = section.GetFileAddress()
            result.append(
                ModuleInfo(
                    name=file_spec.GetFilename() or "",
                    path=str(file_spec) if file_spec.IsValid() else "",
                    uuid=mod.GetUUIDString() or "",
                    base_address=base,
                )
            )
        return result

    @property
    def breakpoints(self) -> list:
        """Return all breakpoints currently set on this target."""
        from .breakpoint import Breakpoint

        result: List[Breakpoint] = []
        for i in range(self._sb.GetNumBreakpoints()):
            sb_bp = self._sb.GetBreakpointAtIndex(i)
            if sb_bp.IsValid():
                result.append(Breakpoint(sb_bp))
        return result

    # -- public API --------------------------------------------------------

    def launch(
        self,
        args: Optional[List[str]] = None,
        env: Optional[List[str]] = None,
        stdin: Optional[str] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        working_dir: Optional[str] = None,
    ):
        """Launch the target and return a :class:`Process` wrapper.

        Parameters
        ----------
        args:
            Command-line arguments for the inferior.
        env:
            Environment variables in ``KEY=VALUE`` form.
        stdin / stdout / stderr:
            Optional file paths for I/O redirection.
        working_dir:
            Working directory for the launched process.

        Returns
        -------
        Process
            A wrapper around the launched ``SBProcess``.
        """
        from .process import Process

        error = lldb.SBError()
        sb_process = self._sb.Launch(
            lldb.SBListener(),
            args,
            env,
            stdin,
            stdout,
            stderr,
            None,  # executable path (use target's)
            0,     # launch flags
            True,  # stop at entry
            error,
        )
        if error.Fail():
            raise RuntimeError(f"Failed to launch target: {error}")
        return Process(sb_process, self)

    def breakpoint_create_by_name(
        self, name: str, module: Optional[str] = None
    ):
        """Create a breakpoint on a symbol name.

        Parameters
        ----------
        name:
            The function / symbol name.
        module:
            Optional module name to restrict the search.

        Returns
        -------
        Breakpoint
        """
        from .breakpoint import Breakpoint

        if module:
            sb_bp = self._sb.BreakpointCreateByName(name, module)
        else:
            sb_bp = self._sb.BreakpointCreateByName(name)
        if not sb_bp or not sb_bp.IsValid():
            raise RuntimeError(f"Failed to create breakpoint for '{name}'")
        return Breakpoint(sb_bp)

    def breakpoint_create_by_address(self, address: int):
        """Create a breakpoint at an absolute address.

        Returns
        -------
        Breakpoint
        """
        from .breakpoint import Breakpoint

        sb_bp = self._sb.BreakpointCreateByAddress(address)
        if not sb_bp or not sb_bp.IsValid():
            raise RuntimeError(
                f"Failed to create breakpoint at address {address:#x}"
            )
        return Breakpoint(sb_bp)

    def breakpoint_create_by_regex(self, pattern: str):
        """Create breakpoints on all symbols matching *pattern*.

        Returns
        -------
        Breakpoint
        """
        from .breakpoint import Breakpoint

        sb_bp = self._sb.BreakpointCreateByRegex(pattern)
        if not sb_bp or not sb_bp.IsValid():
            raise RuntimeError(
                f"Failed to create breakpoint for regex '{pattern}'"
            )
        return Breakpoint(sb_bp)

    def find_functions(
        self, name: str, match_type: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Search for functions by name.

        Parameters
        ----------
        name:
            The function name or pattern.
        match_type:
            An ``lldb.eFunctionNameType*`` constant.  Defaults to
            ``eFunctionNameTypeAuto``.

        Returns
        -------
        list[dict]
            Each dict has keys ``name``, ``address``, and ``module``.
        """
        if match_type is None:
            match_type = lldb.eFunctionNameTypeAuto
        sc_list = self._sb.FindFunctions(name, match_type)
        results: List[Dict[str, Any]] = []
        for i in range(sc_list.GetSize()):
            sc = sc_list.GetContextAtIndex(i)
            func = sc.GetFunction()
            sym = sc.GetSymbol()
            fn_name = func.GetName() if func.IsValid() else (
                sym.GetName() if sym.IsValid() else ""
            )
            addr = (
                sym.GetStartAddress().GetLoadAddress(self._sb)
                if sym.IsValid()
                else 0
            )
            mod = sc.GetModule()
            mod_name = (
                mod.GetFileSpec().GetFilename() if mod.IsValid() else ""
            )
            results.append(
                {"name": fn_name, "address": addr, "module": mod_name}
            )
        return results

    def find_symbols(self, name: str) -> List[Dict[str, Any]]:
        """Search for symbols by name.

        Returns
        -------
        list[dict]
            Each dict has keys ``name``, ``address``, and ``module``.
        """
        sc_list = self._sb.FindSymbols(name)
        results: List[Dict[str, Any]] = []
        for i in range(sc_list.GetSize()):
            sc = sc_list.GetContextAtIndex(i)
            sym = sc.GetSymbol()
            addr = (
                sym.GetStartAddress().GetLoadAddress(self._sb)
                if sym.IsValid()
                else 0
            )
            mod = sc.GetModule()
            mod_name = (
                mod.GetFileSpec().GetFilename() if mod.IsValid() else ""
            )
            results.append(
                {
                    "name": sym.GetName() if sym.IsValid() else "",
                    "address": addr,
                    "module": mod_name,
                }
            )
        return results

    def read_memory(self, address: int, size: int) -> bytes:
        """Read *size* bytes from the target's process memory.

        This is a convenience that delegates to the process associated with
        this target.
        """
        sb_process = self._sb.GetProcess()
        if not sb_process or not sb_process.IsValid():
            raise RuntimeError("No process is associated with this target")
        error = lldb.SBError()
        data = sb_process.ReadMemory(address, size, error)
        if error.Fail():
            raise RuntimeError(
                f"Failed to read {size} bytes at {address:#x}: {error}"
            )
        return bytes(data)

    def resolve_address(self, addr: int) -> Dict[str, Any]:
        """Resolve an address to symbol and module information.

        Returns
        -------
        dict
            Keys: ``address``, ``symbol``, ``module``, ``offset``.
        """
        sb_addr = self._sb.ResolveLoadAddress(addr)
        symbol = sb_addr.GetSymbol() if sb_addr.IsValid() else None
        module = sb_addr.GetModule() if sb_addr.IsValid() else None
        return {
            "address": addr,
            "symbol": symbol.GetName() if symbol and symbol.IsValid() else None,
            "module": (
                module.GetFileSpec().GetFilename()
                if module and module.IsValid()
                else None
            ),
            "offset": (
                addr - symbol.GetStartAddress().GetLoadAddress(self._sb)
                if symbol and symbol.IsValid()
                else 0
            ),
        }
