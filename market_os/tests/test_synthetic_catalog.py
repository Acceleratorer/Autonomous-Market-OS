from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from market_os.synthetic_catalog import CATALOG_SCHEMA, COMPARISON_SCHEMA, catalog_sessions, compare_sessions
from market_os.synthetic_session import load_synthetic_fixture, run_synthetic_fixture, write_synthetic_session_run
from market_os.synthetic_session_api import SyntheticSessionStore
from market_os.synthetic_server import make_synthetic_handler


FIXTURE = Path(__file__).parent / "fixtures" / "b38" / "synthetic_session.json"


def make_store(tmp_path: Path) -> SyntheticSessionStore:
    root = tmp_path / "synthetic"
    run = run_synthetic_fixture(load_synthetic_fixture(FIXTURE))
    write_synthetic_session_run(run, root / "alpha")
    write_synthetic_session_run(run, root / "beta")
    return SyntheticSessionStore(root)


def test_catalog_is_sorted_deterministic_and_fingerprint_backed(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    first = catalog_sessions(store)
    second = catalog_sessions(store)
    assert first == second
    assert first["schema"] == CATALOG_SCHEMA
    assert [item["session_id"] for item in first["sessions"]] == ["alpha", "beta"]
    assert first["sessions"][0]["manifest_fingerprint"]
    assert first["sessions"][0]["fill_count"] == 2


def test_comparison_is_explicit_right_minus_left(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    result = compare_sessions(store, "alpha", "beta")
    assert result["schema"] == COMPARISON_SCHEMA
    assert result["delta_direction"] == "right_minus_left"
    assert result["left"]["session_id"] == "alpha"
    assert result["right"]["session_id"] == "beta"
    assert result["delta"]["total_pnl_usdt"] == 0.0


def test_catalog_and_comparison_reject_unknown_duplicate_and_tampered_sessions(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(KeyError):
        compare_sessions(store, "missing", "alpha")
    with pytest.raises(ValueError, match="distinct"):
        compare_sessions(store, "alpha", "alpha")
    accounting = store.root / "alpha" / "accounting.json"
    payload = json.loads(accounting.read_text(encoding="utf-8"))
    payload["accounting"]["total_pnl_usdt"] = 123.0
    accounting.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint"):
        catalog_sessions(store)


def test_server_exposes_catalog_and_comparison_read_only(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_synthetic_handler(store))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        catalog = json.loads(urlopen(base + "/v1/synthetic/sessions", timeout=2).read())
        assert catalog["session_count"] == 2
        comparison = json.loads(urlopen(base + "/v1/synthetic/comparison/alpha/beta", timeout=2).read())
        assert comparison["delta_direction"] == "right_minus_left"
        catalog_html = urlopen(base + "/v1/synthetic/catalog", timeout=2).read().decode("utf-8")
        assert "Market OS synthetic catalog" in catalog_html
        assert "alpha" in catalog_html and "beta" in catalog_html
        assert "/v1/synthetic/comparison/alpha/beta/dashboard" in catalog_html
        comparison_html = urlopen(base + "/v1/synthetic/comparison/alpha/beta/dashboard", timeout=2).read().decode("utf-8")
        assert "Market OS synthetic comparison" in comparison_html
        assert "Right minus left" in comparison_html
        with pytest.raises(HTTPError) as duplicate:
            urlopen(base + "/v1/synthetic/comparison/alpha/alpha", timeout=2)
        assert duplicate.value.code == 409
        request = Request(base + "/v1/synthetic/sessions", data=b"{}", method="POST")
        with pytest.raises(HTTPError) as post:
            urlopen(request, timeout=2)
        assert post.value.code == 405
        with pytest.raises(HTTPError) as query:
            urlopen(base + "/v1/synthetic/catalog?session=alpha", timeout=2)
        assert query.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
