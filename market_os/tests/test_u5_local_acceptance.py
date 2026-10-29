from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

import pytest

from market_os.api import make_handler
from market_os.portfolio_broker import B41Broker
from market_os.store import RunStore
from market_os.workflow import MarketWorkflow
from market_os.tests.test_portfolio_broker import buy, genesis, policy, approval


def _server(tmp_path: Path) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    source = tmp_path / "source" / genesis().portfolio_id
    B41Broker(source.parent, genesis(), policy()).submit_order(buy(), approval(buy()))
    root = tmp_path / "workflow"
    target = root / "b4-paper" / genesis().portfolio_id
    target.mkdir(parents=True)
    for path in source.iterdir():
        if path.is_file():
            (target / path.name).write_bytes(path.read_bytes())
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(root))))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def test_u5_loopback_acceptance_covers_health_dashboard_json_and_write_boundaries(tmp_path: Path) -> None:
    server, thread, base = _server(tmp_path)
    try:
        health = json.loads(urlopen(base + "/healthz", timeout=2).read())
        ready = json.loads(urlopen(base + "/readyz", timeout=2).read())
        assert health["status"] == "ok"
        assert ready["status"] == "ready"
        dashboard = urlopen(base + f"/v1/b4/portfolios/{genesis().portfolio_id}/dashboard", timeout=2)
        body = dashboard.read().decode("utf-8")
        assert dashboard.headers["Content-Type"] == "text/html; charset=utf-8"
        assert "synthetic-only · paper-only · read-only" in body
        assert "<form" not in body.lower()
        summary = json.loads(urlopen(base + f"/v1/b4/portfolios/{genesis().portfolio_id}/summary", timeout=2).read())
        assert summary["portfolio_id"] == genesis().portfolio_id
        with pytest.raises(HTTPError) as post:
            urlopen(Request(base + f"/v1/b4/portfolios/{genesis().portfolio_id}/dashboard", data=b"{}", method="POST"), timeout=2)
        assert post.value.code == 404
        with pytest.raises(HTTPError) as query:
            urlopen(base + f"/v1/b4/portfolios/{genesis().portfolio_id}/dashboard?x=1", timeout=2)
        assert query.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
