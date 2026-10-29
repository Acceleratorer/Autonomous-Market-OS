from __future__ import annotations

import hashlib
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from market_os.api import make_handler
from market_os.btc_features import B2Config, B2Store, run_b2
from market_os.btc_history import HistoryStore
from market_os.btc_jev_evaluation import B3Store, RecordedJevAdapter, run_b3
from market_os.btc_research_inspection import MAX_RESULT_ARTIFACT_BYTES
from market_os.store import RunStore
from market_os.workflow import MarketWorkflow


FIXTURES = Path(__file__).parent / "fixtures"
HISTORY_FIXTURE = FIXTURES / "btc_paper" / "history.json"
JEV_FIXTURE = FIXTURES / "btc_b3" / "recorded_responses.json"


def _seed_runs(root: Path) -> tuple[str, list[str], str]:
    history = HistoryStore(root / "btc-history")
    dataset = history.ingest_fixture(json.loads(HISTORY_FIXTURE.read_text(encoding="utf-8")))
    as_of = history.inspect_manifest(dataset.dataset_revision)["availability_timestamp_max"]
    b2_store = B2Store(root / "btc-b2")
    b2_runs = [
        run_b2(history, dataset.dataset_revision, b2_store, B2Config(f"inspection-{name}", as_of))["run_id"]
        for name in ("alpha", "beta")
    ]
    b3_run = run_b3(
        history,
        dataset.dataset_revision,
        RecordedJevAdapter.from_path(JEV_FIXTURE),
        B3Store(root / "btc-b3"),
    )["run_id"]
    return dataset.dataset_revision, b2_runs, b3_run


def _start_api(root: Path) -> tuple[ThreadingHTTPServer, Thread, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(root))))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def test_research_run_pages_and_details_are_bounded_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MARKET_OS_BTC_B2_STORE_ROOT", raising=False)
    monkeypatch.delenv("MARKET_OS_BTC_B3_STORE_ROOT", raising=False)
    workflow_root = tmp_path / "workflow"
    dataset_revision, b2_run_ids, b3_run_id = _seed_runs(workflow_root)
    before = {
        path: path.stat().st_mtime_ns
        for engine in ("b2", "b3")
        for path in (workflow_root / f"btc-{engine}").rglob("*")
        if path.is_file()
    }
    server, thread, base = _start_api(workflow_root)
    try:
        b2_url = f"{base}/v1/btc/research/b2/runs?limit=1"
        first = json.loads(urlopen(b2_url, timeout=2).read())
        assert first["api_version"] == "market-os.btc-research-inspection@v1"
        assert first["page"]["has_more"] is True
        assert len(first["runs"]) == 1
        assert not {"path", "artifacts", "features", "labels", "predictions"} & set(first["runs"][0])
        cursor = first["page"]["next_after_run_id"]
        assert first["runs"][0]["run_id"] == cursor

        second = json.loads(urlopen(f"{b2_url}&after_run_id={cursor}", timeout=2).read())
        assert second["page"]["has_more"] is False
        assert len(second["runs"]) == 1
        assert second["runs"][0]["run_id"] > cursor

        b2_detail = json.loads(urlopen(f"{base}/v1/btc/research/b2/runs/{b2_run_ids[0]}", timeout=2).read())
        assert b2_detail["run"]["dataset_revision"] == dataset_revision
        assert set(b2_detail["result"]) == {"naive_0_5", "empirical_rate", "conditional_rate"}
        assert all(score["status"] == "unavailable" for arms in b2_detail["result"].values() for score in arms.values())
        assert not {"features", "labels", "predictions", "splits", "path"} & set(b2_detail)

        b3_page = json.loads(urlopen(f"{base}/v1/btc/research/b3/runs?limit=1", timeout=2).read())
        assert [item["run_id"] for item in b3_page["runs"]] == [b3_run_id]
        b3_detail = json.loads(urlopen(f"{base}/v1/btc/research/b3/runs/{b3_run_id}", timeout=2).read())
        report = b3_detail["result"]
        assert report["source_boundary"]["dataset_revision"] == dataset_revision
        assert report["source_boundary"]["network_requests"] == 0
        assert report["source_boundary"]["provider_requests"] == 0
        assert report["matched_controls"]["same_inputs"] is True
        assert report["promotion"]["decision"] == "not-promoted"
        assert not {"responses", "predictions", "fixture_cases", "path"} & set(report)

        for query in ("store_root=outside", "limit=1&limit=2", "after_run_id=invalid", "unknown=1"):
            with pytest.raises(HTTPError) as rejected:
                urlopen(f"{base}/v1/btc/research/b2/runs?{query}", timeout=2)
            assert rejected.value.code == 400
        with pytest.raises(HTTPError) as rejected_detail_query:
            urlopen(f"{base}/v1/btc/research/b2/runs/{b2_run_ids[0]}?limit=1", timeout=2)
        assert rejected_detail_query.value.code == 400

        after = {path: path.stat().st_mtime_ns for path in before}
        assert after == before
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_research_routes_do_not_create_empty_stores_and_read_only_stores_cannot_persist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MARKET_OS_BTC_B2_STORE_ROOT", raising=False)
    monkeypatch.delenv("MARKET_OS_BTC_B3_STORE_ROOT", raising=False)
    workflow_root = tmp_path / "workflow"
    server, thread, base = _start_api(workflow_root)
    try:
        for engine in ("b2", "b3"):
            root = workflow_root / f"btc-{engine}"
            page = json.loads(urlopen(f"{base}/v1/btc/research/{engine}/runs", timeout=2).read())
            assert page["runs"] == []
            assert page["page"]["has_more"] is False
            assert not root.exists()
            legacy_root = tmp_path / f"legacy-{engine}"
            with pytest.raises(HTTPError) as missing:
                urlopen(f"{base}/v1/btc/{engine}/missing/metrics?store_root={legacy_root}", timeout=2)
            assert missing.value.code == 404
            assert not legacy_root.exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    for store_type in (B2Store, B3Store):
        root = tmp_path / f"readonly-{store_type.__name__}"
        store = store_type(root, read_only=True)
        assert not root.exists()
        with pytest.raises(ValueError, match="read-only"):
            store.persist({})
        assert not root.exists()


def test_research_result_integrity_and_b3_lineage_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MARKET_OS_BTC_B2_STORE_ROOT", raising=False)
    monkeypatch.delenv("MARKET_OS_BTC_B3_STORE_ROOT", raising=False)
    workflow_root = tmp_path / "workflow"
    _, _, b3_run_id = _seed_runs(workflow_root)
    run_dir = workflow_root / "btc-b3" / "runs" / b3_run_id
    report_path = run_dir / "report.json"
    manifest_path = run_dir / "manifest.json"
    original_report = json.loads(report_path.read_text(encoding="utf-8"))
    original_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    server, thread, base = _start_api(workflow_root)
    url = f"{base}/v1/btc/research/b3/runs/{b3_run_id}"
    try:
        report_path.write_bytes(report_path.read_bytes() + b" ")
        with pytest.raises(HTTPError) as tampered:
            urlopen(url, timeout=2)
        assert tampered.value.code == 409
        error = json.loads(tampered.value.read())["error"]
        assert error["code"] == "btc_research_integrity_error"
        assert "workflow" not in error["message"]

        for field, replacement in (("same_inputs", False), ("fixture_fingerprint", "0" * 64)):
            manifest = json.loads(json.dumps(original_manifest))
            report = json.loads(json.dumps(original_report))
            if field == "same_inputs":
                report["matched_controls"][field] = replacement
            else:
                report["source_boundary"][field] = replacement
            raw = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            report_path.write_bytes(raw)
            artifact = next(item for item in manifest["artifacts"] if item["kind"] == "report")
            artifact["size_bytes"] = len(raw)
            artifact["sha256"] = hashlib.sha256(raw).hexdigest()
            manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
            with pytest.raises(HTTPError) as inconsistent:
                urlopen(url, timeout=2)
            assert inconsistent.value.code == 409

        manifest_path.write_text(json.dumps(original_manifest, sort_keys=True), encoding="utf-8")
        report_path.write_bytes(b"x" * (MAX_RESULT_ARTIFACT_BYTES + 1))
        with pytest.raises(HTTPError) as oversized:
            urlopen(url, timeout=2)
        assert oversized.value.code == 409

        report_manifest = json.loads(json.dumps(original_manifest))
        artifact = next(item for item in report_manifest["artifacts"] if item["kind"] == "report")
        deeply_nested = b"[" * 2000 + b"0" + b"]" * 2000
        report_path.write_bytes(deeply_nested)
        artifact["size_bytes"] = len(deeply_nested)
        artifact["sha256"] = hashlib.sha256(deeply_nested).hexdigest()
        manifest_path.write_text(json.dumps(report_manifest, sort_keys=True), encoding="utf-8")
        with pytest.raises(HTTPError) as malformed:
            urlopen(url, timeout=2)
        assert malformed.value.code == 409
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
