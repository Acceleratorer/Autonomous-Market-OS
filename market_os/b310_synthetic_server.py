"""Loopback-only read-only server for B3.9 synthetic sessions."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import signal
import threading
import urllib.parse
from typing import Any

from .b39_synthetic_api import API_VERSION, SyntheticSessionStore


def make_synthetic_handler(store: SyntheticSessionStore) -> type[BaseHTTPRequestHandler]:
    if not isinstance(store, SyntheticSessionStore):
        raise ValueError("synthetic server requires a typed session store")

    class Handler(BaseHTTPRequestHandler):
        def _json(self, status: int, payload: dict[str, Any]) -> None:
            raw = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _html(self, status: int, body: str) -> None:
            raw = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self) -> None:  # noqa: N802
            self._json(405, {"error": "synthetic server is read-only", "api_version": API_VERSION})

        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.query:
                self._json(400, {"error": "query parameters are not accepted", "api_version": API_VERSION})
                return
            if parsed.path == "/healthz":
                self._json(200, {"api_version": API_VERSION, "service": "market-os-synthetic", "status": "ok"})
                return
            if parsed.path == "/":
                sessions = store.list_sessions()
                links = "".join(f'<li><a href="/v1/synthetic/sessions/{name}/dashboard">{name}</a></li>' for name in sessions)
                self._html(200, "<!doctype html><html><body><h1>Market OS synthetic sessions</h1><ul>" + links + "</ul></body></html>")
                return
            prefix = "/v1/synthetic/sessions/"
            if not parsed.path.startswith(prefix):
                self._json(404, {"error": "not found", "api_version": API_VERSION})
                return
            parts = parsed.path[len(prefix):].split("/")
            if len(parts) != 2:
                self._json(404, {"error": "synthetic session resource not found", "api_version": API_VERSION})
                return
            session_id, resource = parts
            try:
                if resource == "dashboard":
                    self._html(200, store.dashboard_html(session_id))
                else:
                    self._json(200, store.inspect(session_id, resource))
            except KeyError:
                self._json(404, {"error": "synthetic session or resource not found", "api_version": API_VERSION})
            except ValueError as exc:
                self._json(409, {"error": {"code": "synthetic_integrity_error", "message": str(exc), "api_version": API_VERSION}})

        def log_message(self, *_args: Any) -> None:
            return

    return Handler


def serve_synthetic(store_root: str | Path, host: str = "127.0.0.1", port: int = 8790) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("synthetic server is loopback-only")
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("port must be between 0 and 65535")
    store = SyntheticSessionStore(store_root)
    server = ThreadingHTTPServer((host, port), make_synthetic_handler(store))
    server.daemon_threads = True

    def stop_server(_signum: int, _frame: object) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    previous = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, stop_server)
    try:
        server.serve_forever()
    finally:
        signal.signal(signal.SIGTERM, previous)
        server.server_close()


__all__ = ["make_synthetic_handler", "serve_synthetic"]
