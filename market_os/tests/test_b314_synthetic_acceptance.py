from __future__ import annotations

import html
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from market_os.b310_synthetic_server import make_synthetic_handler
from market_os.b38_synthetic_session import load_synthetic_fixture, run_synthetic_fixture, write_synthetic_session_run
from market_os.b39_synthetic_api import SyntheticSessionStore


FIXTURE = Path(__file__).parent / "fixtures" / "b38" / "synthetic_session.json"
REPO_ROOT = Path(__file__).parents[2]


def _make_store(tmp_path: Path) -> Path:
    root = tmp_path / "synthetic"
    run = run_synthetic_fixture(load_synthetic_fixture(FIXTURE))
    write_synthetic_session_run(run, root / "alpha")
    write_synthetic_session_run(run, root / "beta")
    return root


def _snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    return {
        str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "market_os.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture()
def server(tmp_path: Path):
    root = _make_store(tmp_path)
    store = SyntheticSessionStore(root)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_synthetic_handler(store))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}", root, store
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def _get_json(base: str, path: str) -> dict[str, object]:
    return json.loads(urlopen(base + path, timeout=2).read())


def test_b314_cli_http_and_html_surfaces_share_validated_artifacts(server) -> None:
    base, root, _store = server
    before = _snapshot(root)

    cli_catalog = _cli("synthetic", "catalog", "--store-root", str(root))
    cli_compare = _cli(
        "synthetic", "compare", "--store-root", str(root), "--left", "alpha", "--right", "beta"
    )
    assert cli_catalog.returncode == 0, cli_catalog.stderr
    assert cli_compare.returncode == 0, cli_compare.stderr

    http_catalog = _get_json(base, "/v1/synthetic/sessions")
    http_compare = _get_json(base, "/v1/synthetic/comparison/alpha/beta")
    assert json.loads(cli_catalog.stdout) == http_catalog
    assert json.loads(cli_compare.stdout) == http_compare
    assert http_compare["left"]["manifest_fingerprint"] == http_catalog["sessions"][0]["manifest_fingerprint"]
    assert http_compare["delta_direction"] == "right_minus_left"

    index = urlopen(base + "/", timeout=2).read().decode("utf-8")
    catalog_html = urlopen(base + "/v1/synthetic/catalog", timeout=2).read().decode("utf-8")
    comparison_html = urlopen(base + "/v1/synthetic/comparison/alpha/beta/dashboard", timeout=2).read().decode("utf-8")
    session_html = urlopen(base + "/v1/synthetic/sessions/alpha/dashboard", timeout=2).read().decode("utf-8")
    assert "/v1/synthetic/sessions" in index
    assert "/v1/synthetic/sessions/alpha/dashboard" in catalog_html
    assert "/v1/synthetic/comparison/alpha/beta/dashboard" in catalog_html
    assert "Right minus left" in comparison_html
    assert "synthetic-only · read-only" in session_html
    assert http_catalog["sessions"][0]["accounting_fingerprint"] in session_html
    assert str(http_compare["delta"]["total_pnl_usdt"]) in comparison_html
    assert _snapshot(root) == before


def test_b314_inspection_does_not_replay_sessions(server, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    base, root, _store = server

    def unexpected_replay(*_args, **_kwargs):
        raise AssertionError("inspection must not replay a session")

    from market_os import b35_strategy_replay, cli

    monkeypatch.setattr(b35_strategy_replay, "run_strategy_replay", unexpected_replay)
    before = _snapshot(root)

    assert cli.main(["synthetic", "catalog", "--store-root", str(root)]) == 0
    cli_catalog = json.loads(capsys.readouterr().out)
    assert len(cli_catalog["sessions"]) == 2
    assert _get_json(base, "/v1/synthetic/sessions")["session_count"] == 2
    assert _get_json(base, "/v1/synthetic/comparison/alpha/beta")["delta_direction"] == "right_minus_left"
    assert _snapshot(root) == before


def test_b314_all_read_surfaces_fail_closed_after_tamper(server) -> None:
    base, root, _store = server
    accounting = root / "alpha" / "accounting.json"
    payload = json.loads(accounting.read_text(encoding="utf-8"))
    payload["accounting"]["total_pnl_usdt"] = 999.0
    accounting.write_text(json.dumps(payload), encoding="utf-8")

    cli = _cli("synthetic", "catalog", "--store-root", str(root))
    assert cli.returncode != 0
    assert "fingerprint" in cli.stderr.lower()
    for path in (
        "/v1/synthetic/sessions",
        "/v1/synthetic/catalog",
        "/v1/synthetic/comparison/alpha/beta",
        "/v1/synthetic/comparison/alpha/beta/dashboard",
    ):
        with pytest.raises(HTTPError) as error:
            urlopen(base + path, timeout=2)
        assert error.value.code == 409


def test_b314_read_only_query_and_path_boundaries(server) -> None:
    base, root, _store = server
    before = _snapshot(root)
    for path in (
        "/v1/synthetic/sessions/../alpha/manifest",
        "/v1/synthetic/sessions/%2E%2E/alpha/manifest",
        "/v1/synthetic/comparison/alpha/alpha",
    ):
        with pytest.raises(HTTPError) as error:
            urlopen(base + path, timeout=2)
        assert error.value.code in {404, 409}

    with pytest.raises(HTTPError) as query_error:
        urlopen(base + "/v1/synthetic/catalog?store-root=outside", timeout=2)
    assert query_error.value.code == 400

    request = Request(base + "/v1/synthetic/sessions", data=b"{}", method="POST")
    with pytest.raises(HTTPError) as post_error:
        urlopen(request, timeout=2)
    assert post_error.value.code == 405
    assert _snapshot(root) == before


def test_b314_root_html_escapes_untrusted_session_labels(server) -> None:
    base, root, store = server
    original = store.list_sessions
    before = _snapshot(root)
    store.list_sessions = lambda: ("<script>alert(1)</script>",)  # type: ignore[method-assign]
    try:
        body = urlopen(base + "/", timeout=2).read().decode("utf-8")
    finally:
        store.list_sessions = original  # type: ignore[method-assign]
    assert html.escape("<script>alert(1)</script>", quote=True) in body
    assert "<script>alert(1)</script>" not in body
    assert _snapshot(root) == before
