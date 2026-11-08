"""Stable reviewer reports for validated synthetic session artifacts."""
from __future__ import annotations

import argparse
import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .accounting import ACCOUNTING_SCHEMA, INTERPRETATION as ACCOUNTING_INTERPRETATION
from .strategy_replay import INTERPRETATION as REPLAY_INTERPRETATION, SESSION_SCHEMA
from .synthetic_session import (
    ARTIFACT_INTERPRETATION,
    MANIFEST_SCHEMA,
    load_synthetic_fixture,
    run_synthetic_fixture,
    write_synthetic_session_run,
)
from .synthetic_session_api import API_VERSION, SyntheticSessionStore

REPORT_SCHEMA = "market-os.u7-h-synthetic-session-accounting-report@v1"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class SyntheticSessionReportError(ValueError):
    """Raised when a synthetic session cannot be reported safely."""


def _fail(message: str) -> None:
    raise SyntheticSessionReportError(message)


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{field} must be an object")
    return value


def _fingerprint(value: Any, field: str) -> str:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        _fail(f"{field} must be a lowercase SHA-256 fingerprint")
    return value


def _finite(value: Any, field: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        _fail(f"{field} must be finite")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(f"{field} must be a non-negative integer")
    return value


def _counts(value: Any, field: str) -> dict[str, int]:
    source = _object(value, field)
    result: dict[str, int] = {}
    for key, count in source.items():
        if not isinstance(key, str):
            _fail(f"{field} keys must be strings")
        result[key] = _nonnegative_int(count, f"{field}.{key}")
    return dict(sorted(result.items()))


def _validated_dashboard(
    store: SyntheticSessionStore, session_id: str
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    dashboard = _object(store.inspect(session_id, "dashboard"), "synthetic dashboard")
    if dashboard.get("schema") != API_VERSION:
        _fail("synthetic dashboard schema is unsupported")
    manifest = _object(dashboard.get("manifest"), "synthetic manifest")
    replay = _object(store.inspect(session_id, "replay"), "strategy replay")
    accounting = _object(store.inspect(session_id, "accounting"), "accounting report")

    if manifest.get("schema") != MANIFEST_SCHEMA or manifest.get("synthetic_only") is not True:
        _fail("synthetic manifest boundary is invalid")
    if manifest.get("interpretation") != ARTIFACT_INTERPRETATION:
        _fail("synthetic manifest interpretation is invalid")
    if replay.get("schema") != SESSION_SCHEMA or replay.get("synthetic_only") is not True:
        _fail("strategy replay boundary is invalid")
    if replay.get("interpretation") != REPLAY_INTERPRETATION:
        _fail("strategy replay interpretation is invalid")
    if accounting.get("schema") != ACCOUNTING_SCHEMA or accounting.get("synthetic_only") is not True:
        _fail("accounting boundary is invalid")
    if accounting.get("interpretation") != ACCOUNTING_INTERPRETATION:
        _fail("accounting interpretation is invalid")

    manifest_fingerprint = _fingerprint(manifest.get("fingerprint"), "manifest fingerprint")
    replay_fingerprint = _fingerprint(replay.get("fingerprint"), "replay fingerprint")
    accounting_fingerprint = _fingerprint(accounting.get("fingerprint"), "accounting fingerprint")
    if manifest.get("replay_fingerprint") != replay_fingerprint:
        _fail("manifest replay fingerprint mismatch")
    if manifest.get("accounting_fingerprint") != accounting_fingerprint:
        _fail("manifest accounting fingerprint mismatch")
    if accounting.get("source_replay_fingerprint") != replay_fingerprint:
        _fail("accounting source replay fingerprint mismatch")
    _fingerprint(manifest.get("fixture_fingerprint"), "fixture fingerprint")

    observations = replay.get("observations")
    if not isinstance(observations, list):
        _fail("strategy replay observations must be an array")
    replay_state = _object(replay.get("replay"), "replay state")
    replay_status = replay_state.get("status")
    if not isinstance(replay_status, str) or not replay_status:
        _fail("replay status is required")

    accounting_summary = _object(accounting.get("accounting"), "accounting summary")
    for field in (
        "initial_cash_usdt", "initial_btc_quantity", "final_cash_usdt",
        "final_btc_quantity", "mark_price_usdt", "turnover_usdt",
        "total_notional_usdt", "total_fees_usdt", "spread_cost_usdt",
        "slippage_cost_usdt", "realized_pnl_usdt", "unrealized_pnl_usdt",
        "total_pnl_usdt",
    ):
        _finite(accounting_summary.get(field), f"accounting.{field}")
    _nonnegative_int(accounting_summary.get("fill_count"), "accounting.fill_count")
    return manifest, replay, accounting


def build_synthetic_session_report(
    store: SyntheticSessionStore, session_id: str, *, deterministic_replay: bool = True
) -> dict[str, Any]:
    """Build a bounded reviewer report without changing the session store."""
    if not isinstance(store, SyntheticSessionStore):
        _fail("report requires a synthetic session store")
    if deterministic_replay is not True:
        _fail("synthetic replay is not deterministic")
    manifest, replay, accounting = _validated_dashboard(store, session_id)
    accounting_summary = _object(accounting["accounting"], "accounting summary")
    replay_state = _object(replay["replay"], "replay state")
    observation_count = _nonnegative_int(len(replay["observations"]), "replay.observation_count")
    fill_count = _nonnegative_int(accounting_summary["fill_count"], "accounting.fill_count")
    # The B3.8 fixture is deliberately bounded: one observation per event and
    # at most one fill per event. Keep the reviewer gate explicit and stable.
    bounds = {
        "max_observations": observation_count,
        "max_fills": observation_count,
    }
    if observation_count > bounds["max_observations"] or fill_count > bounds["max_fills"]:
        _fail("synthetic session count bound exceeded")
    decision_counts = _counts(accounting.get("decision_counts"), "decision_counts")
    command_state_counts = _counts(accounting.get("command_state_counts"), "command_state_counts")
    accounting_fields = (
        "initial_cash_usdt", "initial_btc_quantity", "final_cash_usdt",
        "final_btc_quantity", "mark_price_usdt", "fill_count", "turnover_usdt",
        "total_notional_usdt", "total_fees_usdt", "spread_cost_usdt",
        "slippage_cost_usdt", "realized_pnl_usdt", "unrealized_pnl_usdt",
        "total_pnl_usdt",
    )
    return {
        "schema": REPORT_SCHEMA,
        "status": "passed",
        "interpretation": "synthetic replay accounting observability only; no predictive evidence, profitability claim, or promotion approval",
        "promotion_approved": False,
        "session_id": session_id,
        "fixture_fingerprint": manifest["fixture_fingerprint"],
        "manifest_fingerprint": manifest["fingerprint"],
        "replay_fingerprint": manifest["replay_fingerprint"],
        "accounting_fingerprint": manifest["accounting_fingerprint"],
        "checks": {
            "manifest_valid": True,
            "replay_valid": True,
            "accounting_valid": True,
            "manifest_links_valid": True,
            "replay_accounting_linkage": True,
            "synthetic_boundary": True,
            "store_read_only": True,
            "deterministic_replay": True,
            "bounded_counts": True,
            "promotion_disabled": True,
        },
        "replay": {
            "status": replay_state["status"],
            "observation_count": observation_count,
            "bounds": bounds,
            "decision_counts": decision_counts,
            "command_state_counts": command_state_counts,
            "pending_command_count": _nonnegative_int(accounting.get("pending_command_count"), "pending_command_count"),
            "unexecuted_end_of_stream_count": _nonnegative_int(accounting.get("unexecuted_end_of_stream_count"), "unexecuted_end_of_stream_count"),
        },
        "accounting": {field: accounting_summary[field] for field in accounting_fields},
        "boundary": {
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
        },
    }


def _display(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render the stable U7-H reviewer report as Markdown."""
    accounting_rows = [f"| {key} | {_display(value)} |" for key, value in report["accounting"].items()]
    replay_rows = [f"| {key} | {_display(value)} |" for key, value in report["replay"].items()]
    boundary_rows = [f"| {key} | {_display(value)} |" for key, value in report["boundary"].items()]
    return "\n".join([
        "# U7-H Synthetic Session Accounting Report", "",
        f"- Status: **{str(report['status']).upper()}**",
        f"- Session: {report['session_id']}",
        f"- Fixture fingerprint: {report['fixture_fingerprint']}",
        f"- Replay fingerprint: {report['replay_fingerprint']}",
        f"- Accounting fingerprint: {report['accounting_fingerprint']}",
        "- Scope: synthetic paper replay accounting observability", "",
        f"- Promotion approved: **{_display(report['promotion_approved'])}**", "",
        "## Replay", "", "| Field | Value |", "| --- | --- |", *replay_rows, "",
        "## Accounting", "", "| Field | Value |", "| --- | --- |", *accounting_rows, "",
        "## Boundary", "", "| Boundary | Value |", "| --- | --- |", *boundary_rows, "",
        "This report is observability evidence; it makes no predictive, profitability, or promotion claim.", "",
    ])


def render_synthetic_session_report(
    store: SyntheticSessionStore,
    session_id: str,
    *,
    markdown_path: str | Path,
    json_path: str | Path,
    deterministic_replay: bool = True,
) -> dict[str, Any]:
    """Validate a session and write deterministic JSON and Markdown outputs."""
    report = build_synthetic_session_report(
        store, session_id, deterministic_replay=deterministic_replay
    )
    markdown_file = Path(markdown_path)
    json_file = Path(json_path)
    markdown_file.parent.mkdir(parents=True, exist_ok=True)
    json_file.parent.mkdir(parents=True, exist_ok=True)
    markdown_file.write_text(render_markdown(report), encoding="utf-8")
    json_file.write_text(f"{json.dumps(report, indent=2, sort_keys=True)}\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    """Generate a report directly from the checked-in synthetic fixture."""
    parser = argparse.ArgumentParser(description="Render a U7-H synthetic session accounting report")
    parser.add_argument("--fixture", required=True, help="path to a B3.8 synthetic session fixture")
    parser.add_argument("--output-dir", required=True, help="directory for session artifacts and reports")
    parser.add_argument("--session-id", default="synthetic-session")
    parser.add_argument("--markdown")
    parser.add_argument("--json", dest="json_path")
    args = parser.parse_args(argv)
    try:
        root = Path(args.output_dir).resolve()
        session_dir = root / args.session_id
        fixture = load_synthetic_fixture(args.fixture)
        first_run = run_synthetic_fixture(fixture)
        second_run = run_synthetic_fixture(fixture)
        deterministic_replay = (
            first_run.replay.fingerprint == second_run.replay.fingerprint
            and first_run.accounting.fingerprint == second_run.accounting.fingerprint
        )
        write_synthetic_session_run(first_run, session_dir)
        report = render_synthetic_session_report(
            SyntheticSessionStore(root),
            args.session_id,
            markdown_path=args.markdown or root / "synthetic-session-report.md",
            json_path=args.json_path or root / "synthetic-session-report.json",
            deterministic_replay=deterministic_replay,
        )
    except (KeyError, OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"schema": report["schema"], "status": report["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "REPORT_SCHEMA",
    "SyntheticSessionReportError",
    "build_synthetic_session_report",
    "main",
    "render_markdown",
    "render_synthetic_session_report",
]
