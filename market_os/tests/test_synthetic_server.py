from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from market_os.synthetic_server import make_synthetic_handler
from market_os.synthetic_session import load_synthetic_fixture, run_synthetic_fixture, write_synthetic_session_run
from market_os.synthetic_session_api import SyntheticSessionStore


FIXTURE = Path(__file__).parent / "fixtures" / "b38" / "synthetic_session.json"


def start_server(tmp_path: Path) -> tuple[ThreadingHTTPServer, threading.Thread, Path]:
    root = tmp_path / "synthetic"
    write_synthetic_session_run(run_synthetic_fixture(load_synthetic_fixture(FIXTURE)), root / "demo-session")
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_synthetic_handler(SyntheticSessionStore(root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, root


def test_loopback_server_serves_index_health_dashboard_and_json(tmp_path: Path) -> None:
    server, thread, _root = start_server(tmp_path)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        health = json.loads(urlopen(f"{base}/healthz", timeout=2).read())
        assert health["status"] == "ok"
        index = urlopen(base + "/", timeout=2).read().decode("utf-8")
        assert "/v1/synthetic/sessions/demo-session/dashboard" in index
        dashboard = urlopen(base + "/v1/synthetic/sessions/demo-session/dashboard", timeout=2).read().decode("utf-8")
        assert "synthetic-only · read-only" in dashboard
        accounting = json.loads(urlopen(base + "/v1/synthetic/sessions/demo-session/accounting", timeout=2).read())
        assert accounting["schema"] == "market-os.b3-6.synthetic-accounting-report@v1"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_server_rejects_query_parameters_and_writes(tmp_path: Path) -> None:
    server, thread, root = start_server(tmp_path)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with pytest.raises(HTTPError) as query_error:
            urlopen(base + "/v1/synthetic/sessions/demo-session/manifest?store_root=C:/outside", timeout=2)
        assert query_error.value.code == 400
        request = Request(base + "/v1/synthetic/sessions/demo-session/manifest", data=b"{}", method="POST")
        with pytest.raises(HTTPError) as post_error:
            urlopen(request, timeout=2)
        assert post_error.value.code == 405
        assert not (root / "demo-session" / "api-created.json").exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_server_factory_rejects_remote_bind(tmp_path: Path) -> None:
    from market_os.synthetic_server import serve_synthetic

    with pytest.raises(ValueError, match="loopback-only"):
        serve_synthetic(tmp_path, host="0.0.0.0")
