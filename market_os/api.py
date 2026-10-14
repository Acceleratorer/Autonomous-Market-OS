"""Dependency-free HTTP adapter for the versioned workflow."""
from __future__ import annotations

import json
import threading
import signal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import ContractError, error_response
from .workflow import MarketWorkflow


def make_handler(
    workflow: MarketWorkflow,
    *,
    request_timeout: float = 5.0,
    service_log_path: str | Path | None = None,
) -> type[BaseHTTPRequestHandler]:
    log_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def setup(self) -> None:
            super().setup()
            self.request.settimeout(request_timeout)

        def _audit(self, status: int, *, run_id: str | None = None, error_type: str | None = None) -> None:
            if service_log_path is None:
                return
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "method": self.command,
                "path": self.path,
                "status": status,
                "run_id": run_id,
                "error_type": error_type,
            }
            destination = Path(service_log_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with log_lock, destination.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")

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
                self._audit(404)
                return
            status = 500
            run_id = None
            error_type = None
            try:
                size = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(size))
                selected = workflow
                if body.get("provider") or body.get("backtest_provider"):
                    from .provider_selection import selected_workflow

                    selected = selected_workflow(
                        workflow,
                        body.get("provider", "fixture"),
                        body.get("backtest_provider"),
                    )
                task = selected.create_task(body["objective"], body["symbols"], body["start"], body["end"], execution_mode=body.get("execution_mode", "paper"), idempotency_key=self.headers.get("Idempotency-Key"))
                result = selected.run(task)
                run_id = result.get("run", {}).get("run_id")
                status = 200
                self._send(200, result)
            except ContractError as exc:
                status = 400
                error_type = type(exc).__name__
                self._send(400, {"error": error_response(exc)})
            except (KeyError, TypeError, ValueError, json.JSONDecodeError, TimeoutError) as exc:
                status = 408 if isinstance(exc, TimeoutError) else 400
                error_type = type(exc).__name__
                self._send(status, {"error": {"code": "request_timeout" if status == 408 else "invalid_request", "message": str(exc), "api_version": "market-os.v1"}})
            except Exception as exc:  # pragma: no cover - defensive transport boundary
                error_type = type(exc).__name__
                self._send(500, {"error": str(exc)})
            finally:
                self._audit(status, run_id=run_id, error_type=error_type)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/healthz":
                self._send(200, {"api_version": "market-os.v1", "service": "market-os", "status": "ok"})
                self._audit(200)
                return
            if self.path == "/readyz":
                self._send(200, {"api_version": "market-os.v1", "service": "market-os", "status": "ready"})
                self._audit(200)
                return
            prefix = "/v1/runs/"
            if not self.path.startswith(prefix):
                self._send(404, {"error": "not found"})
                self._audit(404)
                return
            status = 200
            error_type = None
            try:
                self._send(200, workflow.inspect_run(self.path[len(prefix):]))
            except KeyError:
                status = 404
                error_type = "KeyError"
                self._send(404, {"error": "run not found"})
            finally:
                self._audit(status, error_type=error_type)

        def log_message(self, *_args: Any) -> None:
            return

    return Handler


def serve(
    workflow: MarketWorkflow,
    host: str = "127.0.0.1",
    port: int = 8787,
    *,
    request_timeout: float = 5.0,
    service_log_path: str | Path | None = None,
) -> None:
    if request_timeout <= 0:
        raise ValueError("request_timeout must be positive")
    server = ThreadingHTTPServer((host, port), make_handler(workflow, request_timeout=request_timeout, service_log_path=service_log_path))
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
