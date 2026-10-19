"""Dependency-free HTTP adapter for the versioned workflow."""
from __future__ import annotations

import json
import threading
import signal
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from dataclasses import asdict

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
            if self.path == "/v1/btc/history/ingest":
                status = 500
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    body = json.loads(self.rfile.read(size))
                    from .btc_history import HistoryStore

                    result = HistoryStore(body["store_root"]).ingest_fixture(body["fixture"])
                    status = 200
                    self._send(200, asdict(result))
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    status = 400
                    self._send(400, {"error": {"code": "invalid_request", "message": str(exc), "api_version": "market-os.btc-history.v1"}})
                except Exception as exc:  # pragma: no cover
                    self._send(500, {"error": str(exc)})
                finally:
                    self._audit(status)
                return
            if self.path == "/v1/btc/b2/runs":
                status = 500
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    body = json.loads(self.rfile.read(size))
                    from .btc_b2 import B2Config, B2Store, run_b2
                    from .btc_history import HistoryStore

                    result = run_b2(
                        HistoryStore(body["history_store_root"]),
                        body["dataset_revision"],
                        B2Store(body.get("store_root", str(workflow.store.root / "btc-b2"))),
                        B2Config(body.get("experiment_id", "btc-b2-offline"), body.get("as_of")),
                    )
                    status = 200
                    self._send(200, result)
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    status = 400
                    self._send(400, {"error": {"code": "invalid_request", "message": str(exc), "api_version": "market-os.btc-b2.v1"}})
                except Exception as exc:  # pragma: no cover - defensive transport boundary
                    self._send(500, {"error": str(exc)})
                finally:
                    self._audit(status)
                return
            if self.path == "/v1/btc/b3/runs":
                status = 500
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    body = json.loads(self.rfile.read(size))
                    from .btc_b3 import B3Store, RecordedJevAdapter, run_b3
                    from .btc_history import HistoryStore

                    result = run_b3(
                        HistoryStore(body["history_store_root"]),
                        body["dataset_revision"],
                        RecordedJevAdapter.from_path(body["fixture"]),
                        B3Store(body.get("store_root", str(workflow.store.root / "btc-b3"))),
                        experiment_id=body.get("experiment_id", "btc-b3-jev-offline"),
                    )
                    status = 200
                    self._send(200, result)
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    status = 400
                    self._send(400, {"error": {"code": "invalid_request", "message": str(exc), "api_version": "market-os.btc-b3.v1"}})
                except Exception as exc:  # pragma: no cover - defensive transport boundary
                    self._send(500, {"error": str(exc)})
                finally:
                    self._audit(status)
                return
            if self.path == "/v1/benchmarks":
                status = 500
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    body = json.loads(self.rfile.read(size))
                    from .quality_benchmark import run_quality_benchmark

                    result = run_quality_benchmark(workflow.store.root, body.get("fixture"))
                    status = 200
                    self._send(200, result)
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    status = 400
                    self._send(400, {"error": {"code": "invalid_request", "message": str(exc), "api_version": "market-os.v1"}})
                except Exception as exc:  # pragma: no cover - defensive transport boundary
                    self._send(500, {"error": str(exc)})
                finally:
                    self._audit(status)
                return
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
                if body.get("provider") or body.get("backtest_provider") or body.get("summary_provider"):
                    from .provider_selection import selected_workflow

                    if body.get("summary_provider") is None:
                        selected = selected_workflow(
                            workflow,
                            body.get("provider", "fixture"),
                            body.get("backtest_provider"),
                        )
                    else:
                        selected = selected_workflow(
                            workflow,
                            body.get("provider", "fixture"),
                            body.get("backtest_provider"),
                            body.get("summary_provider"),
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
            if urllib.parse.urlsplit(self.path).path == "/v1/btc/history/readiness":
                status = 200
                error_type = None
                try:
                    parsed = urllib.parse.urlsplit(self.path)
                    query = urllib.parse.parse_qs(parsed.query)
                    from .btc_history import plan_historical_readiness

                    result = plan_historical_readiness(int(query["cutoff-ms"][0]))
                    self._send(200, result)
                except (KeyError, TypeError, ValueError) as exc:
                    status = 400
                    error_type = type(exc).__name__
                    self._send(400, {"error": {"code": "invalid_request", "message": str(exc), "api_version": "market-os.btc-history-readiness.v1"}})
                finally:
                    self._audit(status, error_type=error_type)
                return
            btc_prefix = "/v1/btc/history/"
            if self.path.startswith(btc_prefix):
                status = 200
                error_type = None
                try:
                    parsed = urllib.parse.urlsplit(self.path)
                    parts = parsed.path[len(btc_prefix):].split("/")
                    if len(parts) != 2:
                        raise KeyError("BTC dataset resource")
                    from .btc_history import HistoryStore

                    query = urllib.parse.parse_qs(parsed.query)
                    store = HistoryStore(query.get("store_root", [str(workflow.store.root / "btc-history")])[0])
                    dataset_id, resource = parts
                    if resource == "manifest":
                        result = store.inspect_manifest(dataset_id)
                    elif resource == "candles":
                        start_ms = int(query["start-ms"][0]) if "start-ms" in query else None
                        end_ms = int(query["end-ms"][0]) if "end-ms" in query else None
                        result = store.inspect_candles(dataset_id, start_time_ms=start_ms, end_time_ms=end_ms)
                    elif resource == "outcomes":
                        result = store.inspect_outcomes(dataset_id)
                    elif resource == "provenance":
                        result = store.inspect_provenance(dataset_id)
                    elif resource == "gaps":
                        result = store.inspect_gaps(dataset_id)
                    elif resource == "replay":
                        result = store.replay(dataset_id)
                    else:
                        raise KeyError("BTC dataset resource")
                    self._send(200, result)
                except KeyError:
                    status = 404
                    error_type = "KeyError"
                    self._send(404, {"error": "BTC dataset or resource not found"})
                except ValueError as exc:
                    status = 409
                    error_type = type(exc).__name__
                    self._send(409, {"error": {"code": "btc_history_integrity_error", "message": str(exc), "api_version": "market-os.btc-history.v1"}})
                finally:
                    self._audit(status, error_type=error_type)
                return
            btc_b2_prefix = "/v1/btc/b2/"
            if self.path.startswith(btc_b2_prefix):
                status = 200
                error_type = None
                try:
                    parsed = urllib.parse.urlsplit(self.path)
                    parts = parsed.path[len(btc_b2_prefix):].split("/")
                    if len(parts) != 2:
                        raise KeyError("B2 run resource")
                    from .btc_b2 import B2Store

                    query = urllib.parse.parse_qs(parsed.query)
                    store = B2Store(query.get("store_root", [str(workflow.store.root / "btc-b2")])[0])
                    result = store.inspect(parts[0], parts[1])
                    self._send(200, result)
                except KeyError:
                    status = 404
                    error_type = "KeyError"
                    self._send(404, {"error": "B2 run not found"})
                except ValueError as exc:
                    status = 409
                    error_type = type(exc).__name__
                    self._send(409, {"error": {"code": "btc_b2_integrity_error", "message": str(exc), "api_version": "market-os.btc-b2.v1"}})
                finally:
                    self._audit(status, error_type=error_type)
                return
            btc_b3_prefix = "/v1/btc/b3/"
            if self.path.startswith(btc_b3_prefix):
                status = 200
                error_type = None
                try:
                    parsed = urllib.parse.urlsplit(self.path)
                    parts = parsed.path[len(btc_b3_prefix):].split("/")
                    if len(parts) != 2:
                        raise KeyError("B3 run resource")
                    from .btc_b3 import B3Store

                    query = urllib.parse.parse_qs(parsed.query)
                    store = B3Store(query.get("store_root", [str(workflow.store.root / "btc-b3")])[0])
                    result = store.inspect(parts[0], parts[1])
                    self._send(200, result)
                except KeyError:
                    status = 404
                    error_type = "KeyError"
                    self._send(404, {"error": "B3 run not found"})
                except ValueError as exc:
                    status = 409
                    error_type = type(exc).__name__
                    self._send(409, {"error": {"code": "btc_b3_integrity_error", "message": str(exc), "api_version": "market-os.btc-b3.v1"}})
                finally:
                    self._audit(status, error_type=error_type)
                return
            connectivity_prefix = "/v1/btc/connectivity/"
            if self.path.startswith(connectivity_prefix):
                status = 200
                error_type = None
                try:
                    parsed = urllib.parse.urlsplit(self.path)
                    parts = parsed.path[len(connectivity_prefix):].split("/")
                    if len(parts) != 2:
                        raise KeyError("connectivity resource")
                    from .btc_connectivity import ConnectivityStore

                    query = urllib.parse.parse_qs(parsed.query)
                    store = ConnectivityStore(query.get("store_root", [str(workflow.store.root / "btc-connectivity")])[0])
                    result = store.inspect(parts[0], parts[1])
                    self._send(200, result)
                except KeyError:
                    status = 404
                    error_type = "KeyError"
                    self._send(404, {"error": "connectivity probe or resource not found"})
                except ValueError as exc:
                    status = 409
                    error_type = type(exc).__name__
                    self._send(409, {"error": {"code": "btc_connectivity_integrity_error", "message": str(exc), "api_version": "market-os.u3-api-connectivity.v1"}})
                finally:
                    self._audit(status, error_type=error_type)
                return
            benchmark_prefix = "/v1/benchmarks/"
            if self.path.startswith(benchmark_prefix):
                status = 200
                error_type = None
                try:
                    parts = self.path[len(benchmark_prefix):].split("/")
                    if len(parts) not in {2, 3}:
                        raise KeyError("benchmark resource")
                    from .quality_benchmark import BenchmarkStore

                    result = BenchmarkStore(workflow.store.root).inspect(parts[0], parts[1], parts[2] if len(parts) == 3 else None)
                    self._send(200, result)
                except KeyError:
                    status = 404
                    error_type = "KeyError"
                    self._send(404, {"error": "benchmark not found"})
                except ValueError as exc:
                    status = 409
                    error_type = type(exc).__name__
                    self._send(409, {"error": {"code": "benchmark_integrity_error", "message": str(exc), "api_version": "market-os.v1"}})
                finally:
                    self._audit(status, error_type=error_type)
                return
            prefix = "/v1/runs/"
            if not self.path.startswith(prefix):
                self._send(404, {"error": "not found"})
                self._audit(404)
                return
            status = 200
            error_type = None
            try:
                suffix = self.path[len(prefix):]
                parts = suffix.split("/")
                if len(parts) == 1:
                    result = workflow.inspect_run(parts[0])
                elif len(parts) in {3, 4} and parts[1] == "research":
                    resource = parts[2]
                    item_id = parts[3] if len(parts) == 4 else None
                    if resource not in {"documents", "passages", "claims", "unsupported-claims", "passage-claims", "citations", "model-summary", "inferences", "lineage"}:
                        self._send(404, {"error": "research resource not found"})
                        self._audit(404)
                        return
                    result = workflow.inspect_resource(parts[0], resource, item_id)
                else:
                    self._send(404, {"error": "run resource not found"})
                    self._audit(404)
                    return
                self._send(200, result)
            except KeyError:
                status = 404
                error_type = "KeyError"
                self._send(404, {"error": "run or research item not found"})
            except ValueError as exc:
                status = 409
                error_type = type(exc).__name__
                self._send(409, {"error": {"code": "research_integrity_error", "message": str(exc), "api_version": "market-os.v1"}})
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
