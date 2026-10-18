from __future__ import annotations

import json
import math
from pathlib import Path
import threading
from http.server import ThreadingHTTPServer
import urllib.parse
import urllib.request

from market_os.btc_b2 import (
    B2Config,
    B2Store,
    B2_FEATURE_VERSION,
    build_splits,
    evaluate_baselines,
    materialize_rows,
    run_b2,
)
from market_os.api import make_handler
from market_os.btc_history import HistoryStore
from market_os.cli import main
from market_os.store import RunStore
from market_os.workflow import MarketWorkflow

HISTORY_FIXTURE = Path(__file__).parent / "fixtures" / "btc_paper" / "history.json"


def _rows(count: int = 12) -> list[dict[str, object]]:
    base_ms = 1_767_225_600_000
    return [
        {
            "open_time_ms": base_ms + i * 60_000,
            "close_time_ms": base_ms + (i + 1) * 60_000,
            "open": 100.0 + i,
            "high": 102.0 + i,
            "low": 99.0 + i,
            "close": 100.0 + i,
            "volume": i + 1.0,
            "source_timestamp": f"2026-01-01T00:{i + 1:02d}:00+00:00",
            "received_at": f"2026-01-01T00:{i + 1:02d}:00+00:00",
            "availability_timestamp": f"2026-01-01T00:{i + 1:02d}:00+00:00",
            "canonical_fingerprint": f"{i + 1:064x}",
        }
        for i in range(count)
    ]


def _candles(tmp_path: Path) -> tuple[HistoryStore, str]:
    store = HistoryStore(tmp_path / "history")
    result = store.ingest_fixture(json.loads(HISTORY_FIXTURE.read_text(encoding="utf-8")))
    return store, result.dataset_revision


def test_materialize_b2_formulas_and_point_in_time_lineage() -> None:
    rows = _rows()
    result = materialize_rows(rows, B2Config("test", "2026-01-01T00:20:00+00:00"))
    eligible = [row for row in result["features"] if row["status"] == "eligible"]
    assert len(eligible) == 7
    row = eligible[0]
    assert row["feature_version"] == B2_FEATURE_VERSION
    assert row["values"]["log_return_1m"] == math.log(105 / 104)
    assert row["values"]["log_return_5m"] == math.log(105 / 100)
    assert row["values"]["range_pct"] == 3 / 105
    assert row["values"]["log_volume"] == math.log1p(6)
    assert row["decision_eligible"] is True
    assert row["availability_timestamp"] <= row["decision_eligible_at"]
    assert all("availability_timestamp" in ref for ref in row["input_refs"])
    assert all(ref["open_time_ms"] <= row["close_time_ms"] for ref in row["input_refs"])
    assert result["labels"][0]["target_refs"][0]["open_time_ms"] > row["close_time_ms"]
    assert "availability_timestamp" in result["labels"][0]["target_refs"][0]
    assert not any(
        ref["open_time_ms"] > feature["close_time_ms"]
        for feature in result["features"]
        for ref in feature["input_refs"]
    )
    assert any(ref["role"] == "current" for ref in row["input_refs"])


def test_materialize_b2_reports_warmup_gap_and_unavailable_without_lookahead() -> None:
    rows = _rows(12)
    del rows[3]
    rows[-1]["availability_timestamp"] = "2026-01-01T00:30:00+00:00"
    result = materialize_rows(rows, B2Config("test", "2026-01-01T00:25:00+00:00"))
    statuses = {row["status"] for row in result["features"]}
    assert "warm_up" in statuses
    assert "gap" in statuses
    assert "unavailable" in statuses
    assert all(
        ref["open_time_ms"] <= row["close_time_ms"]
        for row in result["features"]
        for ref in row["input_refs"]
    )


def test_materialize_b2_reports_stale_and_invalid_rows() -> None:
    rows = _rows(7)
    rows[0]["availability_timestamp"] = "2026-01-01T00:01:00+00:00"
    rows[0]["source_timestamp"] = "2026-01-01T00:01:00+00:00"
    rows[0]["received_at"] = "2026-01-01T00:01:00+00:00"
    rows[1]["close"] = float("nan")
    result = materialize_rows(rows, B2Config("test", "2026-01-01T01:00:00+00:00", max_staleness_seconds=60))
    assert "stale" in {row["status"] for row in result["features"]}
    assert "invalid" in {row["status"] for row in result["features"]}


def test_b2_run_persists_replayable_artifacts_and_baselines(tmp_path: Path) -> None:
    history, dataset_revision = _candles(tmp_path)
    result = run_b2(history, dataset_revision, B2Store(tmp_path / "b2"))
    assert result["run_id"].startswith("btc-b2-")
    assert result["feature_fingerprint"]
    assert result["label_fingerprint"]
    assert set(result["baselines"]) == {"naive_0_5", "empirical_rate", "conditional_rate"}
    assert result == run_b2(history, dataset_revision, B2Store(tmp_path / "b2"))
    inspected = B2Store(tmp_path / "b2").inspect(result["run_id"], "metrics")
    assert inspected["run_id"] == result["run_id"]
    assert B2Store(tmp_path / "b2").replay(result["run_id"])["replayed"] is True


def test_b2_split_purges_overlapping_labels_and_embargoes_boundaries() -> None:
    samples = [
        {"feature_close_time_ms": i * 60_000, "target_end_ms": (i + 5) * 60_000, "direction": "up", "feature_values": {"log_return_1m": 0.01}}
        for i in range(100)
    ]
    result = build_splits(samples, B2Config("test"))
    assignments = {item["feature_close_time_ms"]: item for item in result["rows"]}
    train_boundary = result["boundaries"]["train_calibration_ms"]
    test_boundary = result["boundaries"]["calibration_test_ms"]
    assert all(item["target_end_ms"] < train_boundary for item in result["rows"] if item["split"] == "train")
    assert all(item["target_end_ms"] < test_boundary for item in result["rows"] if item["split"] == "calibration")
    assert all(
        item["split"] != "calibration"
        for item in result["rows"]
        if train_boundary <= item["feature_close_time_ms"] < train_boundary + 5 * 60_000
    )
    assert all(
        item["split"] != "test"
        for item in result["rows"]
        if test_boundary <= item["feature_close_time_ms"] < test_boundary + 5 * 60_000
    )
    assert assignments[test_boundary]["split"] == "purged"


def test_b2_calibration_is_separate_from_test_predictions() -> None:
    samples = [
        {"feature_close_time_ms": i * 60_000, "target_end_ms": (i + 5) * 60_000,
         "direction": "up" if i % 2 else "down", "feature_values": {"log_return_1m": 0.01 if i % 3 else -0.01}}
        for i in range(100)
    ]
    materialized = {
        "features": [
            {"status": "eligible", "close_time_ms": item["feature_close_time_ms"], "values": item["feature_values"]}
            for item in samples
        ],
        "labels": [
            {**item, "feature_close_time_ms": item["feature_close_time_ms"]}
            for item in samples
        ],
    }
    result = evaluate_baselines(materialized, B2Config("test"))
    assert result["calibration"]["empirical_rate"]["status"] == "measured"
    assert all(item["split"] == "test" for item in result["predictions"])
    calibration_rate = result["calibration"]["empirical_rate"]["calibration_rate"]
    assert calibration_rate not in {0.0, 1.0}
    assert result["metrics"]["empirical_rate"]["raw"]["status"] == "measured"
    assert result == evaluate_baselines(materialized, B2Config("test"))


def test_b2_cli_and_api_inspection_are_read_only(tmp_path: Path, capsys) -> None:
    history, dataset_revision = _candles(tmp_path)
    store_root = tmp_path / "b2"
    assert main([
        "btc-paper", "b2", "run", "--dataset-revision", dataset_revision,
        "--history-store-root", str(history.root), "--store-root", str(store_root),
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    run_id = result["run_id"]
    assert main(["btc-paper", "b2", "inspect", run_id, "--resource", "lineage", "--store-root", str(store_root)]) == 0
    assert json.loads(capsys.readouterr().out)["resource"] == "lineage"

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(tmp_path / "workflow"))))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = json.dumps({
            "dataset_revision": dataset_revision,
            "history_store_root": str(history.root),
            "store_root": str(tmp_path / "api-b2"),
            "experiment_id": "api-test",
        }).encode()
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/v1/btc/b2/runs",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        response = json.loads(urllib.request.urlopen(request, timeout=2).read())
        inspected = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/v1/btc/b2/{response['run_id']}/metrics"
            f"?store_root={urllib.parse.quote(str(tmp_path / 'api-b2'))}", timeout=2,
        ).read())
        assert inspected["resource"] == "metrics"
    finally:
        server.shutdown()
        thread.join(timeout=2)
