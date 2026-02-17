"""PythonExecutor — shared execution engine for Python code against the bridge API."""

from __future__ import annotations

import contextlib
import io
import logging
import re
import time
import traceback
from typing import TYPE_CHECKING, Optional

from morgul.core.events import (
    ExecutionEvent,
    ExecutionEventCallback,
    ExecutionEventType,
)

if TYPE_CHECKING:
    from morgul.bridge.debugger import Debugger
    from morgul.bridge.process import Process
    from morgul.bridge.target import Target

logger = logging.getLogger(__name__)

# Maximum characters of stdout to feed back.
MAX_OUTPUT_CHARS = 20_000


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... (truncated, {len(text)} chars total)"


class PythonExecutor:
    """Executes Python code in a persistent namespace with bridge objects.

    Used by both ``ActHandler`` (single code blocks from translate) and
    ``REPLAgent`` (multi-turn code execution).  Variables persist across
    ``execute()`` calls within the same executor instance.
    """

    def __init__(
        self,
        debugger: Debugger,
        target: Target,
        process: Process,
        execution_callback: Optional[ExecutionEventCallback] = None,
    ):
        self.debugger = debugger
        self.target = target
        self.process = process
        self._execution_callback = execution_callback
        self.namespace = self._build_namespace()

    def _build_namespace(self) -> dict:
        """Build the persistent execution namespace with bridge objects."""
        import binascii
        import collections
        import json
        import math
        import struct

        from morgul.bridge.memory import (
            read_pointer,
            read_string,
            read_uint8,
            read_uint16,
            read_uint32,
            read_uint64,
            search_memory,
        )

        ns: dict = {
            # Bridge objects (live debugger state)
            "debugger": self.debugger,
            "target": self.target,
            "process": self.process,
            "thread": (
                self.process.selected_thread
                if self.process is not None
                else None
            ),
            "frame": (
                self.process.selected_thread.selected_frame
                if self.process is not None
                and self.process.selected_thread is not None
                else None
            ),
            # Memory utilities (pre-bound with process)
            "read_string": read_string,
            "read_pointer": read_pointer,
            "read_uint8": read_uint8,
            "read_uint16": read_uint16,
            "read_uint32": read_uint32,
            "read_uint64": read_uint64,
            "search_memory": search_memory,
            # Safe builtins
            "struct": struct,
            "binascii": binascii,
            "json": json,
            "re": re,
            "collections": collections,
            "math": math,
            # Python builtins needed for code execution
            "print": print,
            "range": range,
            "len": len,
            "int": int,
            "str": str,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "bytes": bytes,
            "bytearray": bytearray,
            "hex": hex,
            "oct": oct,
            "bin": bin,
            "abs": abs,
            "min": min,
            "max": max,
            "sum": sum,
            "sorted": sorted,
            "reversed": reversed,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "isinstance": isinstance,
            "type": type,
            "hasattr": hasattr,
            "getattr": getattr,
            "setattr": setattr,
            "repr": repr,
            "chr": chr,
            "ord": ord,
            "format": format,
            "round": round,
            "pow": pow,
            "divmod": divmod,
            "hash": hash,
            "id": id,
            "dir": dir,
            "vars": vars,
            "any": any,
            "all": all,
            "next": next,
            "iter": iter,
            "slice": slice,
            "Exception": Exception,
            "ValueError": ValueError,
            "TypeError": TypeError,
            "KeyError": KeyError,
            "IndexError": IndexError,
            "AttributeError": AttributeError,
            "RuntimeError": RuntimeError,
            "StopIteration": StopIteration,
            "True": True,
            "False": False,
            "None": None,
            "__builtins__": {},
        }
        return ns

    def _emit(self, event: ExecutionEvent) -> None:
        """Emit an execution event if a callback is registered."""
        if self._execution_callback is not None:
            self._execution_callback(event)

    def execute(self, code: str) -> tuple[str, str, bool]:
        """Execute *code* in the persistent namespace, capturing stdout/stderr.

        Returns ``(stdout, stderr, succeeded)``.
        """
        self._emit(ExecutionEvent(
            event_type=ExecutionEventType.CODE_START,
            code=code,
        ))

        t0 = time.monotonic()
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        succeeded = True

        try:
            with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
                exec(code, self.namespace)  # noqa: S102
        except Exception:
            succeeded = False
            stderr_buf.write(traceback.format_exc())

        self.refresh()

        stdout = _truncate(stdout_buf.getvalue())
        stderr = _truncate(stderr_buf.getvalue())

        self._emit(ExecutionEvent(
            event_type=ExecutionEventType.CODE_END,
            code=code,
            stdout=stdout,
            stderr=stderr,
            succeeded=succeeded,
            duration=time.monotonic() - t0,
        ))

        return stdout, stderr, succeeded

    def refresh(self) -> None:
        """Update thread/frame refs to reflect current debugger state."""
        try:
            thread = self.process.selected_thread
            self.namespace["thread"] = thread
            if thread is not None:
                self.namespace["frame"] = thread.selected_frame
            else:
                self.namespace["frame"] = None
        except Exception:
            pass
