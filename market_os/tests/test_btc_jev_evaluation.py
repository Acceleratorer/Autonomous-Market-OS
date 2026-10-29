from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading
from http.server import ThreadingHTTPServer
import urllib.parse
import urllib.request

import pytest

from market_os.api import make_handler
from market_os.btc_features import B2Config, B2Store, materialize_rows, run_b2
from market_os.btc_jev_evaluation import (
    B3Config,
    B3_ANSWER_SCHEMA,
    B3_DECISION_QUESTION,
    B3Store,
    ExperimentRequest,
    RecordedJevAdapter,
    evaluate_b3,
    parse_recorded_response,
    run_b3,
)
from market_os.btc_history import HistoryStore
from market_os.cli import main
from market_os.store import RunStore
from market_os.workflow import MarketWorkflow


HISTORY_FIXTURE = Path(__file__).parent / "fixtures" / "btc_paper" / "history.json"
JEV_FIXTURE = Path(__file__).parent / "fixtures" / "btc_b3" / "recorded_responses.json"


def _rows(count: int = 140) -> list[dict[str, object]]:
    base_ms = 1_767_225_600_000
    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for index in range(count):
        close = 100.0 + (index % 7) * 0.25 + index * 0.02
        available = base_time + timedelta(minutes=index + 1)
        timestamp = available.isoformat()
        rows.append({
            "open_time_ms": base_ms + index * 60_000,
            "close_time_ms": base_ms + (index + 1) * 60_000,
            "open": close - 0.1,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": index + 1.0,
            "source_timestamp": timestamp,
            "received_at": timestamp,
            "availability_timestamp": timestamp,
            "canonical_fingerprint": f"{index + 1:064x}",
        })
    return rows


def _materialized() -> dict[str, object]:
    return materialize_rows(_rows(), B2Config("b3-test", "2026-01-01T03:00:00+00:00", max_staleness_seconds=86_400), dataset_revision="btc-test-revision")


def _fixture_for(materialized: dict[str, object], kinds: dict[str, str] | None = None) -> RecordedJevAdapter:
    cases = []
    for index, feature in enumerate(item for item in materialized["features"] if item["status"] == "eligible"):
        kind = (kinds or {}).get(feature["input_fingerprint"], "valid")
        response = None if kind == "unavailable" else {
            "model": "jev-1.14.0",
            "answer": {
                "choice": "bullish",
                "probabilities": {"bullish": 0.7, "bearish": 0.2, "indeterminate": 0.1},
                "confidence": 0.6,
            },
        }
        cases.append({
            "case_id": f"case-{index}",
            "kind": kind,
            "input_feature_fingerprint": feature["input_fingerprint"],
            "response_delay_ms": 1000,
            "response": response,
        })
    return RecordedJevAdapter({
        "schema": "market-os.btc-b3-recorded-responses.v1",
        "fixture_id": "generated-b3-test",
        "cases": cases,
    })


def _continuous_synthetic_history_fixture(count: int = 100) -> dict[str, object]:
    start_ms = 1_767_225_600_000
    received_at = "2026-01-01T03:00:00+00:00"
    rows = []
    for index in range(count):
        close = 100 + index * 0.03 + (index % 7) * 0.11
        volume = index + 1
        open_time = start_ms + index * 60_000
        rows.append([
            open_time,
            f"{close - 0.1:.8f}",
            f"{close + 0.2:.8f}",
            f"{close - 0.2:.8f}",
            f"{close:.8f}",
            str(volume),
            open_time + 59_999,
            f"{close * volume:.8f}",
            10,
            f"{volume / 2:.8f}",
            f"{close * volume / 2:.8f}",
            "0",
        ])
    return {
        "schema": "market-os.btc-history-fixture.v1",
        "received_at": received_at,
        "requested_start_ms": start_ms,
        "requested_end_ms_exclusive": start_ms + count * 60_000,
        "as_of_ms": int(datetime.fromisoformat(received_at).timestamp() * 1000),
        "pages": [rows],
    }


def test_b3_contract_and_recorded_response_validation() -> None:
    answer = {
        "model": "jev-1.14.0",
        "answer": {
            "choice": "bullish",
            "probabilities": {"bullish": 0.7, "bearish": 0.2, "indeterminate": 0.1},
            "confidence": 0.6,
        },
    }
    assert parse_recorded_response(answer)["answer"]["choice"] == "bullish"
    with pytest.raises(ValueError, match="exactly model and answer"):
        parse_recorded_response({"model": "jev-1.14.0", "answer": answer["answer"], "extra": True})
    with pytest.raises(ValueError, match="sum to one"):
        parse_recorded_response({**answer, "answer": {**answer["answer"], "probabilities": {"bullish": 0.8, "bearish": 0.2, "indeterminate": 0.2}}})
    with pytest.raises(ValueError, match="inconsistent"):
        parse_recorded_response({**answer, "answer": {**answer["answer"], "choice": "bearish"}})
    materialized = _materialized()
    feature = next(item for item in materialized["features"] if item["status"] == "eligible")
    request = ExperimentRequest("btc-test-revision", materialized["feature_fingerprint"], feature["input_fingerprint"], feature["decision_eligible_at"])
    assert request.payload()["answer_schema"] == B3_ANSWER_SCHEMA
    assert request.payload()["decision_question"] == B3_DECISION_QUESTION
    with pytest.raises(ValueError, match="does not match"):
        ExperimentRequest("btc-test-revision", materialized["feature_fingerprint"], feature["input_fingerprint"], feature["decision_eligible_at"], request_fingerprint="0" * 64)
    with pytest.raises(ValueError, match="future candle"):
        bad_feature = {**feature, "input_refs": [*feature["input_refs"], {"open_time_ms": feature["close_time_ms"] + 60_000, "availability_timestamp": feature["decision_eligible_at"]}]}
        from market_os.btc_jev_evaluation import _request_for
        _request_for(bad_feature, B3Config("x", "btc-test-revision", materialized["feature_fingerprint"], "fixture"))


def test_b3_fixture_covers_unavailable_malformed_late_abstaining_inconsistent_and_hostile() -> None:
    adapter = RecordedJevAdapter.from_path(JEV_FIXTURE)
    assert {item["kind"] for item in adapter.inspect_cases()} == {"valid", "unavailable", "malformed", "late", "abstaining", "inconsistent", "hostile"}
    materialized = _materialized()
    decision_at = next(item["decision_eligible_at"] for item in materialized["features"] if item["status"] == "eligible")
    outcomes = []
    for case in adapter.inspect_cases():
        record = adapter.evaluate(ExperimentRequest("btc-test-revision", materialized["feature_fingerprint"], case["input_feature_fingerprint"], decision_at), deadline_ms=30_000)
        outcomes.append(record)
    assert {record.outcome for record in outcomes} == {"usable", "unavailable", "rejected", "late", "abstained"}
    valid = next(record for record in outcomes if record.outcome == "usable")
    assert valid.provider == "typesafe"
    assert valid.latency_ms is None
    assert valid.usage is None
    assert valid.cost_usd is None


def test_b3_evaluation_uses_same_inputs_and_calibration_range_only() -> None:
    materialized = _materialized()
    adapter = _fixture_for(materialized)
    config = B3Config("b3-positive", "btc-test-revision", materialized["feature_fingerprint"], adapter.fixture_id)
    result = evaluate_b3(materialized, adapter, config)
    assert result["splits"]["policy"]["boundaries_are_frozen_before_model_fit"] is True
    assert result["metrics"]["E1_numerical_only"]["coverage"]["candidate_n"] == result["metrics"]["E2_numerical_plus_jev"]["coverage"]["candidate_n"]
    assert result["matched_controls"]["same_inputs"] is True
    assert result["calibration"]["E1_numerical_only"]["range"] == "calibration"
    assert result["calibration"]["E2_numerical_plus_jev"]["range"] == "calibration"
    assert result == evaluate_b3(materialized, adapter, config)


def test_b3_single_labeled_sample_is_explicitly_unavailable() -> None:
    materialized = _materialized()
    feature = next(item for item in materialized["features"] if item["status"] == "eligible")
    label = next(item for item in materialized["labels"] if item["feature_close_time_ms"] == feature["close_time_ms"])
    single_sample = {**materialized, "features": [feature], "labels": [label]}
    adapter = _fixture_for(single_sample)
    config = B3Config("single-sample", "btc-test-revision", materialized["feature_fingerprint"], adapter.fixture_id)

    result = evaluate_b3(single_sample, adapter, config)

    assert result["splits"]["boundaries"] == {}
    assert result["splits"]["counts"] == {"purged": 1}
    assert result["metrics"]["E1_numerical_only"]["coverage"]["status"] == "unavailable"
    assert result["metrics"]["E2_numerical_plus_jev"]["coverage"]["status"] == "unavailable"
    assert result["matched_controls"]["status"] == "unavailable"


def test_b3_abstentions_are_excluded_from_e2_but_not_hidden() -> None:
    materialized = _materialized()
    baseline_adapter = _fixture_for(materialized)
    baseline = evaluate_b3(materialized, baseline_adapter, B3Config("b3-probe", "btc-test-revision", materialized["feature_fingerprint"], baseline_adapter.fixture_id))
    test_times = {item["feature_close_time_ms"] for item in baseline["splits"]["rows"] if item["split"] == "test"}
    feature = next(item for item in materialized["features"] if item["status"] == "eligible" and item["close_time_ms"] in test_times)
    adapter = _fixture_for(materialized, {feature["input_fingerprint"]: "unavailable"})
    result = evaluate_b3(materialized, adapter, B3Config("b3-abstain", "btc-test-revision", materialized["feature_fingerprint"], adapter.fixture_id))
    assert result["failure_counts"]["unavailable"] == 1
    assert result["metrics"]["E1_numerical_only"]["coverage"]["abstention_n"] == 0
    assert result["metrics"]["E2_numerical_plus_jev"]["coverage"]["abstention_n"] >= 1
    assert any(item["outcome"] == "unavailable" for item in result["responses"])


def test_b3_store_replay_and_inspection_are_deterministic(tmp_path: Path) -> None:
    history = HistoryStore(tmp_path / "history")
    dataset = history.ingest_fixture(json.loads(HISTORY_FIXTURE.read_text(encoding="utf-8")))
    adapter = RecordedJevAdapter.from_path(JEV_FIXTURE)
    store = B3Store(tmp_path / "b3")
    first = run_b3(history, dataset.dataset_revision, adapter, store)
    second = run_b3(history, dataset.dataset_revision, adapter, store)
    assert first == second
    assert store.replay(first["run_id"])["provider_requests"] == 0
    assert store.inspect(first["run_id"], "fingerprints")["feature_fingerprint"] == first["feature_fingerprint"]
    assert store.inspect(first["run_id"], "abstentions")["resource"] == "abstentions"


def test_continuous_synthetic_positive_evaluation_persists_replays_and_inspects(tmp_path: Path, capsys) -> None:
    history = HistoryStore(tmp_path / "history")
    dataset = history.ingest_fixture(_continuous_synthetic_history_fixture())
    workflow = MarketWorkflow(RunStore(tmp_path / "workflow"))
    b2_store = B2Store(workflow.store.root / "btc-b2")
    b3_store = B3Store(workflow.store.root / "btc-b3")
    materialized = materialize_rows(
        history.inspect_candles(dataset.dataset_revision),
        B2Config("positive-b3", "2026-01-01T03:00:00+00:00"),
        dataset_revision=dataset.dataset_revision,
    )
    adapter = _fixture_for(materialized)

    b2 = run_b2(history, dataset.dataset_revision, b2_store)
    b3 = run_b3(history, dataset.dataset_revision, adapter, b3_store, experiment_id="positive-b3")

    assert b2["sample_count"] > 50
    assert b2["metrics"]["naive_0_5"]["raw"]["status"] == "measured"
    assert b2["calibration"]["empirical_rate"]["status"] == "measured"
    assert b2_store.replay(b2["run_id"])["replayed"] is True
    assert b3["sample_count"] == b2["sample_count"]
    assert b3["metrics"]["E1_numerical_only"]["coverage"]["status"] == "measured"
    assert b3["metrics"]["E2_numerical_plus_jev"]["coverage"]["status"] == "measured"
    assert b3["matched_controls"]["status"] == "measured"
    assert b3["promotion_decision"] == "not-promoted"
    assert b3_store.replay(b3["run_id"])["provider_requests"] == 0

    assert main(["btc-paper", "b2", "inspect", b2["run_id"], "--resource", "metrics", "--store-root", str(b2_store.root)]) == 0
    assert json.loads(capsys.readouterr().out)["value"]["naive_0_5"]["raw"]["status"] == "measured"
    assert main(["btc-paper", "b3", "inspect", b3["run_id"], "--resource", "metrics", "--store-root", str(b3_store.root)]) == 0
    assert json.loads(capsys.readouterr().out)["value"]["E1_numerical_only"]["coverage"]["status"] == "measured"

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workflow))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        b2_api = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/v1/btc/b2/{b2['run_id']}/metrics", timeout=3,
        ).read())
        b3_api = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/v1/btc/b3/{b3['run_id']}/metrics", timeout=3,
        ).read())
        assert b2_api["value"]["naive_0_5"]["raw"]["status"] == "measured"
        assert b3_api["value"]["E1_numerical_only"]["coverage"]["status"] == "measured"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_b3_cli_and_api_inspection_are_read_only(tmp_path: Path, capsys) -> None:
    history_root = tmp_path / "history"
    assert main(["btc-paper", "ingest", "--fixture", str(HISTORY_FIXTURE), "--store-root", str(history_root)]) == 0
    dataset_revision = json.loads(capsys.readouterr().out)["dataset_revision"]
    b3_root = tmp_path / "b3"
    assert main(["btc-paper", "b3", "run", "--dataset-revision", dataset_revision, "--history-store-root", str(history_root), "--fixture", str(JEV_FIXTURE), "--store-root", str(b3_root)]) == 0
    run_id = json.loads(capsys.readouterr().out)["run_id"]
    assert main(["btc-paper", "b3", "inspect", run_id, "--resource", "report", "--store-root", str(b3_root)]) == 0
    assert json.loads(capsys.readouterr().out)["resource"] == "report"
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(tmp_path / "workflow"))))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = json.dumps({"history_store_root": str(history_root), "dataset_revision": dataset_revision, "fixture": str(JEV_FIXTURE), "store_root": str(tmp_path / "api-b3")}).encode()
        request = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/v1/btc/b3/runs", data=body, headers={"Content-Type": "application/json"}, method="POST")
        response = json.loads(urllib.request.urlopen(request, timeout=2).read())
        inspected = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/v1/btc/b3/{response['run_id']}/replay?store_root={urllib.parse.quote(str(tmp_path / 'api-b3'))}", timeout=2).read())
        assert inspected["replayed"] is True
        assert inspected["provider_requests"] == 0
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_b3_normal_path_has_no_real_provider_transport() -> None:
    adapter = RecordedJevAdapter.from_path(JEV_FIXTURE)
    assert not hasattr(adapter, "request")
    assert not hasattr(adapter, "fetch")
    assert not hasattr(adapter, "client")


def test_b3_evaluation_does_not_use_socket_or_url_transport(monkeypatch) -> None:
    import socket
    import urllib.request

    def fail_socket(*_args, **_kwargs):
        raise AssertionError("offline B3 attempted a socket")

    def fail_urlopen(*_args, **_kwargs):
        raise AssertionError("offline B3 attempted URL transport")

    monkeypatch.setattr(socket, "socket", fail_socket)
    monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)
    materialized = _materialized()
    adapter = _fixture_for(materialized)
    result = evaluate_b3(materialized, adapter, B3Config("offline-only", "btc-test-revision", materialized["feature_fingerprint"], adapter.fixture_id))
    assert result["sample_count"] > 0
