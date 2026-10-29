"""Loopback-only read-only server for B3.9 synthetic sessions."""
from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import signal
import threading
import urllib.parse
from typing import Any

from .synthetic_session_api import API_VERSION, SyntheticSessionStore
from .synthetic_catalog import catalog_sessions, compare_sessions


def make_synthetic_handler(store: SyntheticSessionStore) -> type[BaseHTTPRequestHandler]:
    if not isinstance(store, SyntheticSessionStore):
        raise ValueError("synthetic server requires a typed session store")

    class Handler(BaseHTTPRequestHandler):
        @staticmethod
        def _cell(value: Any) -> str:
            return html.escape(str(value), quote=True)

        def _catalog_html(self) -> str:
            catalog = catalog_sessions(store)
            session_ids = [str(item["session_id"]) for item in catalog["sessions"]]
            rows = "".join(
                "<tr>"
                + "".join(f"<td>{self._cell(item.get(key))}</td>" for key in ("session_id", "observation_count", "fill_count", "total_pnl_usdt"))
                + f'<td><a href="/v1/synthetic/sessions/{self._cell(item["session_id"])}/dashboard">session</a></td>'
                + "</tr>"
                for item in catalog["sessions"]
            )
            comparisons = "".join(
                f'<li><a href="/v1/synthetic/comparison/{html.escape(left, quote=True)}/{html.escape(right, quote=True)}/dashboard">'
                f'{self._cell(left)} vs {self._cell(right)}</a></li>'
                for index, left in enumerate(session_ids)
                for right in session_ids[index + 1:]
            )
            return (
                "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>Market OS synthetic catalog</title>"
                "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"></head><body>"
                "<main><h1>Market OS synthetic catalog</h1><p>synthetic-only · read-only</p>"
                f"<p>Sessions: {self._cell(catalog['session_count'])}</p>"
                "<table><thead><tr><th>Session</th><th>Observations</th><th>Fills</th><th>Total PnL (USDT)</th><th>View</th></tr></thead>"
                f"<tbody>{rows}</tbody></table><h2>Comparisons</h2><ul>{comparisons}</ul></main></body></html>"
            )

        def _comparison_html(self, left_id: str, right_id: str) -> str:
            comparison = compare_sessions(store, left_id, right_id)
            rows = "".join(
                f"<tr><th>{self._cell(field)}</th><td>{self._cell(comparison['left'][field])}</td>"
                f"<td>{self._cell(comparison['right'][field])}</td><td>{self._cell(comparison['delta'][field])}</td></tr>"
                for field in comparison["delta"]
            )
            return (
                "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>Market OS synthetic comparison</title>"
                "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"></head><body>"
                "<main><h1>Market OS synthetic comparison</h1><p>synthetic-only · read-only</p>"
                f"<p>Comparison direction: {self._cell(comparison['delta_direction'])}</p>"
                f"<p>Left: {self._cell(left_id)} · Right: {self._cell(right_id)}</p>"
                "<table><thead><tr><th>Metric</th><th>Left</th><th>Right</th><th>Right minus left</th></tr></thead>"
                f"<tbody>{rows}</tbody></table></main></body></html>"
            )

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
                links = "".join(f'<li><a href="/v1/synthetic/sessions/{html.escape(name, quote=True)}/dashboard">{html.escape(name)}</a></li>' for name in sessions)
                self._html(200, "<!doctype html><html><body><h1>Market OS synthetic sessions</h1><p><a href=\"/v1/synthetic/sessions\">catalog JSON</a></p><ul>" + links + "</ul></body></html>")
                return
            if parsed.path == "/v1/synthetic/catalog":
                try:
                    self._html(200, self._catalog_html())
                except KeyError:
                    self._json(404, {"error": "synthetic session not found", "api_version": API_VERSION})
                except ValueError as exc:
                    self._json(409, {"error": {"code": "synthetic_integrity_error", "message": str(exc), "api_version": API_VERSION}})
                return
            if parsed.path == "/v1/synthetic/sessions":
                try:
                    self._json(200, catalog_sessions(store))
                except KeyError:
                    self._json(404, {"error": "synthetic session not found", "api_version": API_VERSION})
                except ValueError as exc:
                    self._json(409, {"error": {"code": "synthetic_integrity_error", "message": str(exc), "api_version": API_VERSION}})
                return
            comparison_prefix = "/v1/synthetic/comparison/"
            if parsed.path.startswith(comparison_prefix):
                parts = parsed.path[len(comparison_prefix):].split("/")
                if len(parts) == 3 and parts[2] == "dashboard" and all(parts):
                    try:
                        self._html(200, self._comparison_html(parts[0], parts[1]))
                    except KeyError:
                        self._json(404, {"error": "synthetic session not found", "api_version": API_VERSION})
                    except ValueError as exc:
                        self._json(409, {"error": {"code": "synthetic_integrity_error", "message": str(exc), "api_version": API_VERSION}})
                    return
                if len(parts) != 2 or not all(parts):
                    self._json(404, {"error": "synthetic comparison not found", "api_version": API_VERSION})
                    return
                try:
                    self._json(200, compare_sessions(store, parts[0], parts[1]))
                except KeyError:
                    self._json(404, {"error": "synthetic session not found", "api_version": API_VERSION})
                except ValueError as exc:
                    self._json(409, {"error": {"code": "synthetic_integrity_error", "message": str(exc), "api_version": API_VERSION}})
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
