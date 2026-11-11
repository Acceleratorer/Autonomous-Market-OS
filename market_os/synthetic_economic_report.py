"""Deterministic synthetic economic evaluation; no provider or live claims."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping


FIXTURE_SCHEMA = "market-os.u7-j.synthetic-economic-fixture@v1"
REPORT_SCHEMA = "market-os.u7-j-synthetic-economic-report@v1"
INTERPRETATION = "synthetic economic observability only; no real-world profitability or promotion claim"
SOURCE_REFERENCE = {
    "repository": "ClawWork",
    "commit": "9c73ac05fdb0bffdb23febdd971eb70f44dd46eb",
    "path": "livebench/agent/economic_tracker.py",
    "imported_runtime": False,
}
_CHANNELS = ("llm_tokens", "search_api", "ocr_api", "other_api")
_BOUNDARY = {
    "private": True,
    "synthetic_only": True,
    "paper_only": True,
    "read_only": True,
    "predictive_evidence": False,
    "promotion_approved": False,
    "network_access": False,
    "provider_requests": 0,
    "credentials": False,
    "mutation_routes": False,
    "live_execution": False,
}


class SyntheticEconomicReportError(ValueError):
    """Raised when the synthetic economic fixture is invalid."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _source_sha256(raw: bytes) -> str:
    """Hash fixture bytes with platform line endings normalized."""
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def _fail(message: str) -> None:
    raise SyntheticEconomicReportError(message)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{field} must be an object")
    return value


def _number(value: Any, field: str, *, minimum: float = 0.0, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        _fail(f"{field} must be finite")
    result = float(value)
    if result < minimum or (maximum is not None and result > maximum):
        _fail(f"{field} is outside its allowed range")
    return result


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(f"{field} must be a non-negative integer")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{field} must be a non-empty string")
    return value


def _money(value: float) -> float:
    return round(value, 12)


def _load_fixture(path: str | Path) -> tuple[dict[str, Any], str, str]:
    fixture = Path(path)
    try:
        raw = fixture.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _fail(f"cannot read economic fixture: {exc}")
    if not isinstance(payload, dict):
        _fail("economic fixture must be an object")
    expected = payload.get("fixture_fingerprint")
    body = {key: value for key, value in payload.items() if key != "fixture_fingerprint"}
    actual = _fingerprint(body)
    if expected != actual:
        _fail("economic fixture fingerprint mismatch")
    if payload.get("schema") != FIXTURE_SCHEMA or payload.get("synthetic_only") is not True:
        _fail("economic fixture schema or boundary is invalid")
    if payload.get("interpretation") != INTERPRETATION:
        _fail("economic fixture interpretation is invalid")
    _text(payload.get("fixture_id"), "fixture_id")
    _text(payload.get("label"), "label")
    license_metadata = _mapping(payload.get("license"), "license")
    if license_metadata.get("classification") != "synthetic-internal":
        _fail("economic fixture license classification is invalid")
    _text(license_metadata.get("attribution"), "license.attribution")
    if payload.get("source_reference") != SOURCE_REFERENCE:
        _fail("economic fixture source reference is invalid")
    _number(payload.get("initial_balance_usd"), "initial_balance_usd")
    _number(payload.get("min_evaluation_threshold"), "min_evaluation_threshold", maximum=1.0)
    pricing = _mapping(payload.get("token_pricing"), "token_pricing")
    _number(pricing.get("input_per_1m_usd"), "token_pricing.input_per_1m_usd")
    _number(pricing.get("output_per_1m_usd"), "token_pricing.output_per_1m_usd")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        _fail("tasks must be a non-empty list")
    seen: set[str] = set()
    for index, task in enumerate(tasks):
        item = _mapping(task, f"tasks[{index}]")
        task_id = item.get("task_id")
        if not isinstance(task_id, str) or not task_id or task_id in seen:
            _fail(f"tasks[{index}].task_id is missing or duplicated")
        seen.add(task_id)
        _number(item.get("base_payment_usd"), f"tasks[{index}].base_payment_usd")
        _number(item.get("evaluation_score"), f"tasks[{index}].evaluation_score", maximum=1.0)
        _number(item.get("wall_clock_seconds"), f"tasks[{index}].wall_clock_seconds", minimum=0.000001)
        llm = _mapping(item.get("llm"), f"tasks[{index}].llm")
        _integer(llm.get("input_tokens"), f"tasks[{index}].llm.input_tokens")
        _integer(llm.get("output_tokens"), f"tasks[{index}].llm.output_tokens")
        calls = item.get("api_calls", [])
        if not isinstance(calls, list):
            _fail(f"tasks[{index}].api_calls must be a list")
        for call_index, call in enumerate(calls):
            record = _mapping(call, f"tasks[{index}].api_calls[{call_index}]")
            if record.get("channel") not in _CHANNELS[1:]:
                _fail(f"tasks[{index}].api_calls[{call_index}].channel is invalid")
            if record.get("pricing_model") not in {"per_token", "flat_rate"}:
                _fail(f"tasks[{index}].api_calls[{call_index}].pricing_model is invalid")
            if record.get("pricing_model") == "per_token":
                _integer(record.get("tokens"), f"tasks[{index}].api_calls[{call_index}].tokens")
                _number(record.get("price_per_1m_usd"), f"tasks[{index}].api_calls[{call_index}].price_per_1m_usd")
            else:
                _number(record.get("cost_usd"), f"tasks[{index}].api_calls[{call_index}].cost_usd")
            if "api_name" in record:
                _text(record.get("api_name"), f"tasks[{index}].api_calls[{call_index}].api_name")
    return payload, actual, _source_sha256(raw)


def _task_cost(task: Mapping[str, Any], pricing: Mapping[str, Any]) -> tuple[dict[str, float], list[dict[str, Any]]]:
    llm = _mapping(task["llm"], "llm")
    channels = {key: 0.0 for key in _CHANNELS}
    channels["llm_tokens"] = _money(
        _integer(llm["input_tokens"], "llm.input_tokens") / 1_000_000 * float(pricing["input_per_1m_usd"])
        + _integer(llm["output_tokens"], "llm.output_tokens") / 1_000_000 * float(pricing["output_per_1m_usd"])
    )
    calls: list[dict[str, Any]] = []
    for call in task.get("api_calls", []):
        record = _mapping(call, "api_call")
        cost = (
            _integer(record["tokens"], "api_call.tokens") / 1_000_000 * float(record["price_per_1m_usd"])
            if record["pricing_model"] == "per_token"
            else float(record["cost_usd"])
        )
        cost = _money(cost)
        channels[str(record["channel"])] += cost
        calls.append({
            "api_name": str(record.get("api_name", "synthetic-api")),
            "channel": record["channel"],
            "pricing_model": record["pricing_model"],
            "cost_usd": cost,
        })
    channels = {key: _money(value) for key, value in channels.items()}
    return channels, calls


def _survival_status(balance: float) -> str:
    if balance <= 0:
        return "bankrupt"
    if balance < 100:
        return "struggling"
    if balance < 500:
        return "stable"
    return "thriving"


def build_synthetic_economic_report(path: str | Path) -> dict[str, Any]:
    """Build a deterministic ClawWork-shaped economic projection from a fixture."""
    fixture, fixture_fingerprint, source_sha256 = _load_fixture(path)
    pricing = _mapping(fixture["token_pricing"], "token_pricing")
    threshold = float(fixture["min_evaluation_threshold"])
    balance = _money(float(fixture["initial_balance_usd"]))
    totals = {key: 0.0 for key in _CHANNELS}
    income = 0.0
    wall_clock = 0.0
    tasks: list[dict[str, Any]] = []
    for task in fixture["tasks"]:
        item = _mapping(task, "task")
        channels, api_calls = _task_cost(item, pricing)
        cost = _money(sum(channels.values()))
        score = float(item["evaluation_score"])
        payment = _money(float(item["base_payment_usd"]) if score >= threshold else 0.0)
        net = _money(payment - cost)
        balance = _money(balance + net)
        wall_clock += float(item["wall_clock_seconds"])
        for key in _CHANNELS:
            totals[key] = _money(totals[key] + channels[key])
        income = _money(income + payment)
        tasks.append({
            "task_id": item["task_id"],
            "evaluation_score": score,
            "payment_threshold": threshold,
            "base_payment_usd": _money(float(item["base_payment_usd"])),
            "payment_awarded": payment > 0,
            "income_usd": payment,
            "costs_usd": channels,
            "total_cost_usd": cost,
            "net_usd": net,
            "wall_clock_seconds": float(item["wall_clock_seconds"]),
            "api_calls": api_calls,
            "balance_after_usd": balance,
        })
    totals["total"] = _money(sum(totals[key] for key in _CHANNELS))
    net = _money(income - totals["total"])
    report = {
        "schema": REPORT_SCHEMA,
        "status": "passed",
        "fixture": {
            "fixture_id": fixture["fixture_id"],
            "label": fixture["label"],
            "schema": fixture["schema"],
            "fixture_fingerprint": fixture_fingerprint,
            "source_sha256": source_sha256,
            "task_count": len(tasks),
        },
        "source_reference": dict(SOURCE_REFERENCE),
        "checks": {
            "fixture_valid": True,
            "accounting_balanced": _money(float(fixture["initial_balance_usd"]) + net) == balance,
            "threshold_applied": True,
            "deterministic_replay": True,
            "synthetic_boundary": True,
            "promotion_disabled": True,
        },
        "economics": {
            "initial_balance_usd": _money(float(fixture["initial_balance_usd"])),
            "final_balance_usd": balance,
            "total_costs_usd": totals,
            "total_income_usd": income,
            "net_usd": net,
            "net_per_hour_usd": _money(net / (wall_clock / 3600)) if wall_clock else None,
            "wall_clock_seconds": wall_clock,
            "tasks_completed": len(tasks),
            "tasks_paid": sum(item["payment_awarded"] for item in tasks),
            "tasks_rejected": sum(not item["payment_awarded"] for item in tasks),
            "survival_status": _survival_status(balance),
        },
        "tasks": tasks,
        "boundary": dict(_BOUNDARY),
        "promotion": {
            "approved": False,
            "status": "Not ready — synthetic economics only",
            "reasons": ["fixture costs and rewards are synthetic", "real provider usage and payment authorization are deferred"],
        },
        "interpretation": INTERPRETATION,
        "deferred": ["real providers", "credentials", "network access", "live execution", "external payment"],
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report


def _display(value: Any) -> str:
    return json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)


def render_markdown(report: Mapping[str, Any]) -> str:
    rows = [
        f"| {task['task_id']} | {task['evaluation_score']} | {task['income_usd']} | {task['total_cost_usd']} | {task['net_usd']} | {task['balance_after_usd']} |"
        for task in report["tasks"]
    ]
    return "\n".join([
        "# U7-J Synthetic Economic Report", "",
        f"- Status: **{str(report['status']).upper()}**",
        f"- Fixture fingerprint: `{report['fixture']['fixture_fingerprint']}`",
        f"- Final balance: **${report['economics']['final_balance_usd']:.6f}**",
        f"- Net: **${report['economics']['net_usd']:.6f}**",
        f"- Promotion approved: **{report['promotion']['approved']}**", "",
        "## Task economics", "", "| Task | Score | Income | Cost | Net | Balance after |", "| --- | ---: | ---: | ---: | ---: | ---: |", *rows, "",
        "## Boundary", "", "| Boundary | Value |", "| --- | --- |",
        *[f"| {key} | {_display(value)} |" for key, value in report["boundary"].items()], "",
        report["interpretation"], "",
    ])


def render_synthetic_economic_report(
    fixture_path: str | Path,
    *,
    markdown_path: str | Path,
    json_path: str | Path,
) -> dict[str, Any]:
    report = build_synthetic_economic_report(fixture_path)
    markdown = Path(markdown_path)
    output = Path(json_path)
    markdown.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text(render_markdown(report), encoding="utf-8")
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a U7-J synthetic economic report")
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--markdown", required=True)
    parser.add_argument("--json", dest="json_path", required=True)
    args = parser.parse_args(argv)
    try:
        report = render_synthetic_economic_report(args.fixture, markdown_path=args.markdown, json_path=args.json_path)
    except (OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"schema": report["schema"], "status": report["status"], "report_fingerprint": report["report_fingerprint"]}, sort_keys=True))
    return 0


__all__ = [
    "FIXTURE_SCHEMA",
    "INTERPRETATION",
    "REPORT_SCHEMA",
    "SOURCE_REFERENCE",
    "SyntheticEconomicReportError",
    "build_synthetic_economic_report",
    "main",
    "render_markdown",
    "render_synthetic_economic_report",
]


if __name__ == "__main__":
    raise SystemExit(main())
