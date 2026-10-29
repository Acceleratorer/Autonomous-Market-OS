from __future__ import annotations

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from market_os import cli
from market_os.api import make_handler
from market_os.quality_benchmark import (
    LEGACY_QUALITY_BENCHMARK_API_VERSION,
    QUALITY_BENCHMARK_API_VERSION,
    BenchmarkStore,
    _legacy_report_fingerprint,
    run_quality_benchmark,
)
from market_os.store import RunStore
from market_os.workflow import MarketWorkflow


FIXTURE = Path(__file__).parent / "fixtures" / "quality" / "benchmark.json"


def test_benchmark_runs_all_fixture_cases_with_independent_metrics(tmp_path: Path) -> None:
    report = run_quality_benchmark(tmp_path, FIXTURE)

    assert report["api_version"] == QUALITY_BENCHMARK_API_VERSION
    assert report["fixture_id"] == "m2.5-research-quality-corpus-v1"
    assert len(report["cases"]) == 36
    assert {case["method"] for case in report["cases"]} == {
        "deterministic-exact-quote",
        "deterministic-test-model",
    }
    assert report["promotion"]["status"] == "Not ready — specific failures remain"
    assert report["promotion"]["real_model_provider"] is False
    assert report["promotion"]["human_approval"] is False
    assert report["promotion"]["reasons"]
    assert "citation_precision" in report["metrics"]
    assert "latency_ms_p95" in report["metrics"]
    assert "estimated_cost_reporting" in report["metrics"]


def test_benchmark_fingerprint_replays_stably_and_persists_lineage(tmp_path: Path) -> None:
    first = run_quality_benchmark(tmp_path, FIXTURE)
    second = run_quality_benchmark(tmp_path, FIXTURE)

    assert first["benchmark_fingerprint"] == second["benchmark_fingerprint"]
    assert first["benchmark_id"] == second["benchmark_id"]
    assert first["replay"]["stable"] is True
    assert first["replay"]["fingerprint"] == first["benchmark_fingerprint"]
    assert first["artifact"]["lineage"] == [f"fixture:{first['fixture_fingerprint']}"]
    assert all(case["lineage"] for case in first["cases"])


@pytest.mark.parametrize(
    "resource",
    ["cases", "metrics", "failed-cases", "thresholds", "fingerprint"],
)
def test_benchmark_inspection_is_read_only(tmp_path: Path, resource: str) -> None:
    report = run_quality_benchmark(tmp_path, FIXTURE)
    store = BenchmarkStore(tmp_path)
    before = store.snapshot()

    inspected = store.inspect(report["benchmark_id"], resource)

    assert inspected
    assert store.snapshot() == before


def test_benchmark_case_inspection_filters_and_unknown_case_fails(tmp_path: Path) -> None:
    report = run_quality_benchmark(tmp_path, FIXTURE)
    store = BenchmarkStore(tmp_path)

    case = store.inspect(report["benchmark_id"], "cases", "fully-supported")

    assert len(case) == 2
    with pytest.raises(KeyError):
        store.inspect(report["benchmark_id"], "cases", "missing-case")


def test_benchmark_rejects_corrupt_persisted_report(tmp_path: Path) -> None:
    report = run_quality_benchmark(tmp_path, FIXTURE)
    artifact = report["artifact"]
    path = Path(artifact["path"])
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["benchmark_fingerprint"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="content hash mismatch"):
        BenchmarkStore(tmp_path).inspect(report["benchmark_id"], "fingerprint")


def test_cli_runs_and_inspects_benchmark(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main([
        "benchmark",
        "run",
        "--store-root",
        str(tmp_path),
        "--fixture",
        str(FIXTURE),
    ]) == 0
    report = json.loads(capsys.readouterr().out)

    assert cli.main([
        "benchmark",
        "inspect",
        report["benchmark_id"],
        "--store-root",
        str(tmp_path),
        "--resource",
        "metrics",
    ]) == 0
    assert "citation_precision" in json.loads(capsys.readouterr().out)

    assert cli.main([
        "benchmark",
        "inspect",
        report["benchmark_id"],
        "--store-root",
        str(tmp_path),
        "--resource",
        "evaluation",
    ]) == 0
    assert json.loads(capsys.readouterr().out)["benchmark_success"]["failed"] == 0


def test_api_runs_and_inspects_benchmark_without_trading_state(tmp_path: Path) -> None:
    workflow = MarketWorkflow(RunStore(tmp_path / "trading"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(workflow))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/v1/benchmarks",
            data=json.dumps({"fixture": str(FIXTURE)}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        report = json.loads(urllib.request.urlopen(request, timeout=10).read())
        inspected = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/v1/benchmarks/{report['benchmark_id']}/failed-cases",
            timeout=5,
        ).read())
        evaluation = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_port}/v1/benchmarks/{report['benchmark_id']}/evaluation",
            timeout=5,
        ).read())
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert report["promotion"]["status"] == "Not ready — specific failures remain"
    assert isinstance(inspected, list)
    assert evaluation["benchmark_success"]["failed"] == 0
    assert not (tmp_path / "trading" / "runs.jsonl").read_text(encoding="utf-8").strip()


def test_benchmark_does_not_claim_real_model_quality(tmp_path: Path) -> None:
    report = run_quality_benchmark(tmp_path, FIXTURE)

    assert report["methods"]["deterministic-test-model"]["is_test_double"] is True
    assert report["promotion"]["real_model_provider"] is False
    assert "real model" in " ".join(report["promotion"]["reasons"]).lower()


def test_quality_report_separates_gate_correctness_from_candidate_quality(tmp_path: Path) -> None:
    report = run_quality_benchmark(tmp_path, FIXTURE)

    assert report["evaluation"]["benchmark_success"]["passed"] == 36
    assert report["evaluation"]["benchmark_success"]["failed"] == 0
    assert report["evaluation"]["gate_correctness"]["false_accepts"] == []
    assert report["evaluation"]["gate_correctness"]["false_rejects"] == []

    similar = next(
        case
        for case in report["cases"]
        if case["method"] == "deterministic-test-model"
        and case["case_id"] == "similar-nonidentical-quote"
    )
    assert similar["benchmark_success"] is True
    assert similar["passed"] is True
    assert similar["gate_correctness"] == 1.0
    assert similar["candidate_quality"]["status"] == "failed"
    assert similar["quote_exactness"] == 0.0
    assert similar["malformed_output_rejection"] == 1.0

    corrupt_baseline = next(
        case
        for case in report["cases"]
        if case["method"] == "deterministic-exact-quote"
        and case["case_id"] == "corrupt-content-hash"
    )
    assert corrupt_baseline["benchmark_success"] is True
    assert corrupt_baseline["evidence_coverage"] is None
    assert corrupt_baseline["evidence_coverage_accuracy"] is None
    assert corrupt_baseline["latency_ms"] is None
    assert corrupt_baseline["usage"]["input_units"] is None

    quality = report["evaluation"]["candidate_quality"]["deterministic-test-model"]
    assert quality["failed"] >= 1
    assert quality["failed_case_ids"]
    assert "similar-nonidentical-quote" in quality["failed_case_ids"]


def test_quality_metrics_report_invalid_citations_and_empty_denominators(tmp_path: Path) -> None:
    report = run_quality_benchmark(tmp_path, FIXTURE)

    invalid = next(
        case
        for case in report["cases"]
        if case["method"] == "deterministic-test-model"
        and case["case_id"] == "invalid-citation-id"
    )
    missing = next(
        case
        for case in report["cases"]
        if case["method"] == "deterministic-test-model"
        and case["case_id"] == "missing-citations"
    )
    assert invalid["citation_precision"] == 0.0
    assert invalid["citation_recall"] is None
    assert missing["citation_precision"] is None
    assert missing["citation_recall"] is None

    precision = report["metrics"]["citation_precision"]
    assert precision["applicable_count"]["deterministic-test-model"] > 0
    assert precision["not_applicable_count"]["deterministic-test-model"] > 0

    failure = next(
        case
        for case in report["cases"]
        if case["method"] == "deterministic-test-model"
        and case["case_id"] == "model-failure"
    )
    assert failure["usage"]["input_units"] is None
    assert failure["usage"]["output_units"] is None
    assert failure["usage_known"] is False
    assert report["metrics"]["estimated_cost_reporting"]["values"]["deterministic-test-model"] is None


def test_benchmark_inspection_exposes_corrected_evaluation(tmp_path: Path) -> None:
    report = run_quality_benchmark(tmp_path, FIXTURE)
    store = BenchmarkStore(tmp_path)
    before = store.snapshot()

    evaluation = store.inspect(report["benchmark_id"], "evaluation")
    failures = store.inspect(report["benchmark_id"], "candidate-quality-failures")

    assert evaluation["benchmark_success"]["failed"] == 0
    assert any(item["case_id"] == "similar-nonidentical-quote" for item in failures)
    assert store.snapshot() == before


def test_v1_benchmark_artifacts_remain_readable(tmp_path: Path) -> None:
    report = run_quality_benchmark(tmp_path, FIXTURE)
    artifact_path = Path(report["artifact"]["path"])
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["api_version"] = LEGACY_QUALITY_BENCHMARK_API_VERSION
    payload.pop("evaluation")
    for case in payload["cases"]:
        for key in ("benchmark_success", "candidate_quality"):
            case.pop(key, None)
    payload["cases"][1]["passed"] = False
    payload["benchmark_fingerprint"] = _legacy_report_fingerprint(payload)
    artifact_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    index_path = tmp_path / "benchmarks" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index[report["artifact"]["artifact_id"]]["sha256"] = __import__("hashlib").sha256(artifact_path.read_bytes()).hexdigest()
    index_path.write_text(json.dumps(index, sort_keys=True), encoding="utf-8")

    inspected = BenchmarkStore(tmp_path).inspect(report["benchmark_id"], "failed-cases")

    assert isinstance(inspected, list)
