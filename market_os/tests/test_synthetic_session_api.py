from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

import pytest

from market_os.api import make_handler
from market_os.synthetic_session_api import SyntheticSessionStore
from market_os.synthetic_session import load_synthetic_fixture, run_synthetic_fixture, write_synthetic_session_run
from market_os.store import RunStore
from market_os.workflow import MarketWorkflow


FIXTURE = Path(__file__).parent / "fixtures" / "b38" / "synthetic_session.json"


def session_root(tmp_path: Path) -> Path:
    output = tmp_path / "synthetic"
    write_synthetic_session_run(run_synthetic_fixture(load_synthetic_fixture(FIXTURE)), output / "demo-session")
    return output


def test_store_inspects_valid_session_resources_and_dashboard(tmp_path: Path) -> None:
    root = session_root(tmp_path)
    store = SyntheticSessionStore(root)
    manifest = store.inspect("demo-session", "manifest")
    accounting = store.inspect("demo-session", "accounting")
    replay = store.inspect("demo-session", "replay")
    dashboard = store.dashboard_html("demo-session")
    assert manifest["schema"] == "market-os.b3-8.synthetic-session-manifest@v1"
    assert accounting["schema"] == "market-os.b3-6.synthetic-accounting-report@v1"
    assert replay["schema"] == "market-os.b3-5.synthetic-strategy-session@v1"
    assert "synthetic-only · read-only" in dashboard
    assert "Replay timeline" in dashboard
    assert "Fill" in dashboard


def test_store_rejects_path_traversal_unknown_resource_and_tamper(tmp_path: Path) -> None:
    root = session_root(tmp_path)
    store = SyntheticSessionStore(root)
    with pytest.raises(KeyError):
        store.inspect("../demo-session", "manifest")
    with pytest.raises(KeyError):
        store.inspect("demo-session", "unknown")
    accounting_path = root / "demo-session" / "accounting.json"
    payload = json.loads(accounting_path.read_text(encoding="utf-8"))
    payload["accounting"]["total_pnl_usdt"] = 999.0
    accounting_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint"):
        store.inspect("demo-session", "accounting")


def test_http_api_is_read_only_and_serves_json_and_html(tmp_path: Path) -> None:
    root = session_root(tmp_path)
    handler = make_handler(MarketWorkflow(RunStore(tmp_path / "workflow")))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server_thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}/v1/synthetic/sessions/demo-session"
        manifest_url = f"{base}/manifest?store_root={root.as_posix()}"
        manifest = json.loads(urlopen(manifest_url, timeout=2).read())
        assert manifest["schema"] == "market-os.b3-8.synthetic-session-manifest@v1"
        accounting = json.loads(urlopen(f"{base}/accounting?store_root={root.as_posix()}", timeout=2).read())
        assert accounting["accounting"]["fill_count"] == 2
        dashboard_response = urlopen(f"{base}/dashboard?store_root={root.as_posix()}", timeout=2)
        dashboard = dashboard_response.read().decode("utf-8")
        assert dashboard_response.headers["Content-Type"].startswith("text/html")
        assert "Replay timeline" in dashboard
        assert not (root / "demo-session" / "api-created.json").exists()
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
