"""Dependency-free HTTP adapter for the versioned workflow."""
from __future__ import annotations

import json
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .contracts import ContractError, error_response
from .workflow import MarketWorkflow


def make_handler(workflow: MarketWorkflow) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, payload: dict[str, Any]) -> None:
            raw = json.dumps(payload, sort_keys=True).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/tasks":
                self._send(404, {"error": "not found"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(size))
                task = workflow.create_task(body["objective"], body["symbols"], body["start"], body["end"], execution_mode=body.get("execution_mode", "paper"), idempotency_key=self.headers.get("Idempotency-Key"))
                result = workflow.run(task)
                self._send(200, result)
            except ContractError as exc:
                self._send(400, {"error": error_response(exc)})
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                self._send(400, {"error": {"code": "invalid_request", "message": str(exc), "api_version": "market-os.v1"}})
            except Exception as exc:  # pragma: no cover - defensive transport boundary
                self._send(500, {"error": str(exc)})

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/healthz":
                self._send(200, {"api_version": "market-os.v1", "service": "market-os", "status": "ok"})
                return
            if self.path == "/readyz":
                self._send(200, {"api_version": "market-os.v1", "service": "market-os", "status": "ready"})
                return
            prefix = "/v1/runs/"
            if not self.path.startswith(prefix):
                self._send(404, {"error": "not found"})
                return
            try:
                self._send(200, workflow.inspect_run(self.path[len(prefix):]))
            except KeyError:
                self._send(404, {"error": "run not found"})

        def log_message(self, *_args: Any) -> None:
            return

    return Handler


def serve(workflow: MarketWorkflow, host: str = "127.0.0.1", port: int = 8787) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(workflow))
    server.daemon_threads = True
    workflow.recover_inflight_runs()
    handled_signals = [signal.SIGTERM]
    if hasattr(signal, "SIGBREAK"):
        handled_signals.append(signal.SIGBREAK)
    previous_signals = {value: signal.getsignal(value) for value in handled_signals}

    def stop_server(_signum: int, _frame: object) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    for value in handled_signals:
        signal.signal(value, stop_server)
    try:
        server.serve_forever()
    finally:
        for value, previous in previous_signals.items():
            signal.signal(value, previous)
        server.server_close()
