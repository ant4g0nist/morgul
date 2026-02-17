"""Web-based dashboard display — HTTP server + SSE broadcaster.

Replaces the Rich TUI with a browser-based split-pane dashboard.
Runs an asyncio HTTP server in a daemon thread, serving a self-contained
HTML page and streaming events via Server-Sent Events (SSE).

Zero external dependencies — uses only Python stdlib.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import webbrowser
from collections import deque
from typing import Any, Dict, Optional, Set

from morgul.core.display.dashboard import DASHBOARD_HTML
from morgul.core.events import ExecutionEvent, ExecutionEventType

logger = logging.getLogger(__name__)


def _serialize_execution_event(event: ExecutionEvent) -> Dict[str, Any]:
    """Convert an ExecutionEvent (__slots__ object) to a JSON-safe dict."""
    d: Dict[str, Any] = {
        "type": "execution",
        "event_type": event.event_type.value,
        "code": event.code,
        "stdout": event.stdout,
        "stderr": event.stderr,
        "succeeded": event.succeeded,
        "duration": event.duration,
    }
    # Flatten metadata into the dict for easier JS consumption
    if event.metadata:
        for k, v in event.metadata.items():
            if k not in d:
                d[k] = v
    return d


def _serialize_llm_event(event: Any, is_start: bool) -> Dict[str, Any]:
    """Convert an LLMEvent (__slots__ object) to a JSON-safe dict."""
    d: Dict[str, Any] = {
        "type": "llm",
        "is_start": is_start,
        "method": event.method,
        "duration": event.duration,
        "model_type": event.model_type,
        "error": event.error,
    }
    if event.usage is not None:
        d["input_tokens"] = event.usage.input_tokens
        d["output_tokens"] = event.usage.output_tokens
    return d


class WebDisplay:
    """HTTP server + SSE broadcaster for the Morgul web dashboard.

    Runs in a background daemon thread with its own asyncio event loop.
    Serves the dashboard HTML at ``/`` and streams events via SSE at ``/events``.
    """

    def __init__(self, port: int = 8546):
        self._port = port
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server: Optional[asyncio.AbstractServer] = None
        self._clients: Set[asyncio.StreamWriter] = set()
        self._history: deque[str] = deque(maxlen=200)
        self._started = threading.Event()
        self._html_bytes = DASHBOARD_HTML.encode("utf-8")

    def start(self) -> None:
        """Start the HTTP server in a background daemon thread."""
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()
        # Wait for the server to be ready
        self._started.wait(timeout=5.0)
        url = f"http://127.0.0.1:{self._port}"
        logger.info("Morgul dashboard at %s", url)
        try:
            webbrowser.open(url)
        except Exception:
            logger.info("Open %s in your browser to view the dashboard", url)

    def stop(self) -> None:
        """End the session but keep the server alive for browsing history.

        Broadcasts ``session_end`` so the dashboard shows "session ended".
        The server keeps running — new/refreshed clients get the full
        event history replay.  Call ``shutdown()`` to kill the server.
        """
        self._broadcast_event({"type": "session_end"})

    def shutdown(self) -> None:
        """Shut down the HTTP server and background thread."""
        if self._loop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        self._server = None
        self._loop = None
        self._clients.clear()

    def wait(self) -> None:
        """Block until the user presses Ctrl+C, keeping the server alive."""
        import signal
        import sys
        url = f"http://127.0.0.1:{self._port}"
        sys.stderr.write(
            f"\n  Dashboard still running at {url}"
            f"\n  Press Ctrl+C to exit.\n\n"
        )
        sys.stderr.flush()
        try:
            # Block on the server thread — Ctrl+C raises KeyboardInterrupt
            while self._thread is not None and self._thread.is_alive():
                self._thread.join(timeout=1.0)
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def on_execution_event(self, event: ExecutionEvent) -> None:
        """Callback for execution events — same signature as VisibleDisplay."""
        data = _serialize_execution_event(event)
        self._broadcast_event(data)

    def on_llm_event(self, event: Any, is_start: bool) -> None:
        """Callback for LLM events — same signature as VisibleDisplay."""
        data = _serialize_llm_event(event, is_start)
        self._broadcast_event(data)

    # ── Internal ─────────────────────────────────────────────────────

    def _run_server(self) -> None:
        """Thread target: create an asyncio event loop and run the server."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._start_serving())
            self._started.set()
            self._loop.run_forever()
        except Exception:
            logger.exception("Dashboard server error")
        finally:
            # Clean up
            if self._server is not None:
                self._server.close()
                try:
                    self._loop.run_until_complete(self._server.wait_closed())
                except Exception:
                    pass
            # Close all SSE client writers
            for writer in list(self._clients):
                try:
                    writer.close()
                except Exception:
                    pass
            self._clients.clear()
            self._loop.close()

    async def _start_serving(self) -> None:
        """Create the asyncio TCP server."""
        self._server = await asyncio.start_server(
            self._handle_connection, "127.0.0.1", self._port
        )

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Route incoming HTTP requests to the appropriate handler."""
        try:
            # Read the request line and headers
            request_line = await asyncio.wait_for(
                reader.readline(), timeout=10.0
            )
            if not request_line:
                writer.close()
                return

            request_str = request_line.decode("utf-8", errors="replace")
            parts = request_str.strip().split()
            if len(parts) < 2:
                writer.close()
                return

            method, path = parts[0], parts[1]

            # Consume remaining headers
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=5.0)
                if line in (b"\r\n", b"\n", b""):
                    break

            if method != "GET":
                await self._send_response(writer, 405, "text/plain", b"Method Not Allowed")
                return

            if path == "/events":
                await self._serve_sse(reader, writer)
            else:
                await self._serve_dashboard(writer)

        except (asyncio.TimeoutError, ConnectionError, OSError):
            pass
        except Exception:
            logger.debug("Connection handler error", exc_info=True)
        finally:
            try:
                if not writer.is_closing():
                    writer.close()
            except Exception:
                pass

    async def _send_response(
        self,
        writer: asyncio.StreamWriter,
        status: int,
        content_type: str,
        body: bytes,
    ) -> None:
        """Send a simple HTTP response."""
        status_text = {200: "OK", 404: "Not Found", 405: "Method Not Allowed"}.get(
            status, "OK"
        )
        header = (
            f"HTTP/1.1 {status} {status_text}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        )
        writer.write(header.encode("utf-8"))
        writer.write(body)
        await writer.drain()
        writer.close()

    async def _serve_dashboard(self, writer: asyncio.StreamWriter) -> None:
        """Serve the dashboard HTML page."""
        await self._send_response(writer, 200, "text/html; charset=utf-8", self._html_bytes)

    async def _serve_sse(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Register an SSE client, replay history, then keep alive."""
        header = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/event-stream\r\n"
            "Cache-Control: no-cache\r\n"
            "Connection: keep-alive\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "\r\n"
        )
        writer.write(header.encode("utf-8"))
        await writer.drain()

        # Send an init event immediately so the browser fires onopen
        init_msg = json.dumps({"type": "init"})
        writer.write(f"data: {init_msg}\n\n".encode("utf-8"))
        await writer.drain()

        # Replay event history for catch-up
        for event_json in list(self._history):
            try:
                writer.write(f"data: {event_json}\n\n".encode("utf-8"))
                await writer.drain()
            except (ConnectionError, OSError):
                return

        self._clients.add(writer)
        try:
            # Keep connection open; send keepalive pings every 15s
            while True:
                try:
                    data = await asyncio.wait_for(reader.read(1024), timeout=15.0)
                    if not data:
                        break
                except asyncio.TimeoutError:
                    # Send SSE comment as keepalive
                    try:
                        writer.write(b": ping\n\n")
                        await writer.drain()
                    except (ConnectionError, OSError):
                        break
        except (ConnectionError, OSError, asyncio.CancelledError):
            pass
        finally:
            self._clients.discard(writer)

    def _broadcast_event(self, event_dict: Dict[str, Any]) -> None:
        """Serialize event to JSON and send to all SSE clients (thread-safe)."""
        event_json = json.dumps(event_dict, default=str)
        self._history.append(event_json)

        if self._loop is None or self._loop.is_closed():
            return

        self._loop.call_soon_threadsafe(
            asyncio.ensure_future,
            self._send_to_all(event_json),
        )

    async def _send_to_all(self, event_json: str) -> None:
        """Send an SSE message to all connected clients, pruning dead ones."""
        dead: list[asyncio.StreamWriter] = []
        message = f"data: {event_json}\n\n".encode("utf-8")
        for writer in list(self._clients):
            try:
                writer.write(message)
                await writer.drain()
            except (ConnectionError, OSError):
                dead.append(writer)
        for writer in dead:
            self._clients.discard(writer)
            try:
                writer.close()
            except Exception:
                pass
