"""Stable reviewer projection for the deterministic quality benchmark."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .quality_benchmark import _report_fingerprint

QUALITY_REPORT_SCHEMA = "market-os.u7-g-quality-benchmark-report@v1"
QUALITY_BENCHMARK_SCHEMA = "market-os.quality-benchmark.v2"
_SHA256 = set("0123456789abcdef")


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= _SHA256


def _stable_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    """Remove machine-specific timing while preserving benchmark decisions."""
    return {
        key: value
        for key, value in metrics.items()
        if key != "latency_ms_p95"
    }


def _validate_benchmark(benchmark: dict[str, Any]) -> None:
    _require(isinstance(benchmark, dict), "benchmark report must be an object")
    _require(benchmark.get("api_version") == QUALITY_BENCHMARK_SCHEMA, "benchmark schema is not v2")
    for key in ("benchmark_fingerprint", "fixture_fingerprint"):
        _require(_is_sha256(benchmark.get(key)), f"{key} is not a SHA-256 fingerprint")
    _require(isinstance(benchmark.get("benchmark_id"), str) and benchmark["benchmark_id"].startswith("benchmark-"), "benchmark ID is invalid")
    _require(isinstance(benchmark.get("fixture_id"), str) and benchmark["fixture_id"], "fixture ID is missing")
    _require(_report_fingerprint(benchmark) == benchmark["benchmark_fingerprint"], "benchmark fingerprint mismatch")
    _require(benchmark.get("replay", {}).get("stable") is True, "benchmark replay is not stable")
    _require(benchmark.get("replay", {}).get("fingerprint") == benchmark["benchmark_fingerprint"], "benchmark replay fingerprint mismatch")
    safety = benchmark.get("safety", {})
    expected_safety = {
        "read_only": True,
        "trading_state_mutated": False,
        "live_orders_created": False,
        "external_provider_called": False,
    }
    _require(safety == expected_safety, "benchmark safety boundary is unsafe")
    evaluation = benchmark.get("evaluation", {})
    benchmark_success = evaluation.get("benchmark_success", {})
    gate_correctness = evaluation.get("gate_correctness", {})
    _require(benchmark_success.get("failed") == 0, "benchmark procedure failures remain")
    _require(gate_correctness.get("false_accepts") == [], "benchmark has false accepts")
    _require(gate_correctness.get("false_rejects") == [], "benchmark has false rejects")
    promotion = benchmark.get("promotion", {})
    _require(str(promotion.get("status", "")).startswith("Not ready"), "promotion status must remain not ready")
    _require(promotion.get("real_model_provider") is False, "real model provider was exercised")
    _require(promotion.get("human_approval") is False, "human approval must remain absent")
    cost = benchmark.get("metrics", {}).get("estimated_cost_reporting", {})
    _require(cost.get("status") == "not_available_for_deterministic_test_double", "deterministic cost must remain unavailable")
    cases = benchmark.get("cases")
    _require(isinstance(cases, list) and cases, "benchmark cases are missing")
    for case in cases:
        _require(isinstance(case.get("lineage"), list) and case["lineage"], f"case lineage is missing: {case.get('case_id')}")


def build_quality_report(benchmark: dict[str, Any]) -> dict[str, Any]:
    """Validate a v2 benchmark and return a deterministic U7-G projection."""
    _validate_benchmark(benchmark)
    evaluation = benchmark["evaluation"]
    stable = {
        "schema": QUALITY_REPORT_SCHEMA,
        "status": "passed",
        "benchmark": {
            "api_version": benchmark["api_version"],
            "benchmark_id": benchmark["benchmark_id"],
            "benchmark_fingerprint": benchmark["benchmark_fingerprint"],
            "fixture_id": benchmark["fixture_id"],
            "fixture_fingerprint": benchmark["fixture_fingerprint"],
            "case_count": len(benchmark["cases"]),
            "evaluation_count": evaluation["benchmark_success"]["passed"] + evaluation["benchmark_success"]["failed"],
        },
        "checks": {
            "benchmark_schema": True,
            "fingerprints_valid": True,
            "replay_stable": True,
            "benchmark_success": True,
            "gate_correctness": True,
            "lineage_complete": True,
            "safety_boundary": True,
            "cost_unavailable": True,
        },
        "evaluation": evaluation,
        "metrics": _stable_metrics(benchmark["metrics"]),
        "threshold_decisions": {
            key: value
            for key, value in benchmark["threshold_decisions"].items()
            if key != "latency_ms_p95"
        },
        "promotion": {
            "status": benchmark["promotion"]["status"],
            "real_model_provider": False,
            "human_approval": False,
            "estimated_cost": None,
            "reasons": benchmark["promotion"]["reasons"],
            "required_before_real_adapter": benchmark["promotion"]["required_before_real_adapter"],
        },
        "safety": benchmark["safety"],
        "deferred": ["real model provider", "credentials", "network providers", "live execution"],
    }
    stable["report_fingerprint"] = _digest(stable)
    return stable


def render_quality_markdown(report: dict[str, Any]) -> str:
    metric_rows = []
    for method, metrics in report["metrics"].items():
        values = metrics.get("values", {})
        for metric, value in values.items():
            metric_rows.append((method, metric, json.dumps(value, sort_keys=True)))
    check_rows = [(key, "PASS" if value else "FAIL") for key, value in report["checks"].items()]
    safety_rows = [(key, str(value)) for key, value in report["safety"].items()]
    return "\n".join([
        "# U7-G Deterministic Quality Benchmark Report",
        "",
        f"- Status: **{report['status'].upper()}**",
        f"- Benchmark: `{report['benchmark']['benchmark_id']}`",
        f"- Fixture: `{report['benchmark']['fixture_id']}`",
        f"- Cases: {report['benchmark']['case_count']} ({report['benchmark']['evaluation_count']} evaluations)",
        f"- Promotion: **{report['promotion']['status']}**",
        "",
        "## Checks",
        "",
        "| Check | Result |",
        "| --- | --- |",
        *[f"| {key} | {value} |" for key, value in check_rows],
        "",
        "## Stable metrics",
        "",
        "| Method | Metric | Value |",
        "| --- | --- | --- |",
        *[f"| {method} | {metric} | `{value}` |" for method, metric, value in metric_rows],
        "",
        "## Safety boundary",
        "",
        "| Boundary | Value |",
        "| --- | --- |",
        *[f"| {key} | {value} |" for key, value in safety_rows],
        "",
        "Latency is intentionally omitted from this stable projection because it is machine-specific. Deterministic test-double cost remains unavailable; promotion is not authorized.",
        "",
    ])


def render_quality_report(
    benchmark: dict[str, Any],
    *,
    markdown_path: str | Path | None = None,
    json_path: str | Path | None = None,
) -> dict[str, Any]:
    report = build_quality_report(benchmark)
    if markdown_path is not None:
        markdown = Path(markdown_path)
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text(render_quality_markdown(report), encoding="utf-8")
    if json_path is not None:
        output = Path(json_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


__all__ = ["QUALITY_REPORT_SCHEMA", "build_quality_report", "render_quality_markdown", "render_quality_report"]
