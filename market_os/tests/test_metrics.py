from __future__ import annotations

import urllib.request
from http.server import ThreadingHTTPServer
from threading import Thread

from market_os.api import make_handler
from market_os.metrics import MetricsRegistry, classify_route
from market_os.store import RunStore
from market_os.workflow import MarketWorkflow


def test_metrics_use_bounded_route_labels() -> None:
    assert classify_route("/v3/b4/portfolios/paper-main/inspection") == "portfolio"
    assert classify_route("/v1/btc/history/datasets/btc-history-abc") == "btc"
    assert classify_route("/v1/b4/portfolios/paper-main?token=secret") == "portfolio"

    registry = MetricsRegistry()
    registry.record_request("GET", "/v3/b4/portfolios/paper-main/inspection", 200)
    registry.record_event("portfolio.authorization")
    rendered = registry.render().decode("utf-8")

    assert 'route="portfolio"' in rendered
    assert "paper-main" not in rendered
    assert "secret" not in rendered
    assert 'event="portfolio.authorization"' in rendered


def test_metrics_endpoint_exposes_only_prometheus_text(tmp_path) -> None:
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_handler(MarketWorkflow(RunStore(tmp_path / "state"))),
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/healthz",
            timeout=2,
        ) as response:
            response.read()
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/metrics",
            timeout=2,
        ) as response:
            body = response.read().decode("utf-8")
            assert response.headers["Content-Type"].startswith("text/plain")
        assert "market_os_http_requests_total" in body
        assert 'route="health"' in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
