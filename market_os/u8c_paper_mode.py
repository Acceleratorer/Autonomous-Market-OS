"""Record an explicit permanent paper-only U8 owner decision."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .u8a_readiness import CANONICAL_BOUNDARY

PAPER_MODE_SCHEMA = "market-os.u8-c-permanent-paper-only@v1"
_EXPECTED = {
    "u8a": {
        "schema": "market-os.u8-a-live-readiness-decision@v1",
        "status": "gated",
        "artifact": "u8-a-live-readiness-decision.json",
    },
    "u8b": {
        "schema": "market-os.u8-b-local-operational-readiness@v1",
        "status": "gated",
        "artifact": "u8-b-local-operational-readiness.json",
    },
}


class U8CPaperModeError(ValueError):
    """Raised when a U8-C source evidence item fails closed."""


def _fail(message: str) -> None:
    raise U8CPaperModeError(message)


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{field} must be an object")
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _source_sha256(raw: bytes) -> str:
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def _read_inputs(paths: Mapping[str, str | Path]) -> dict[str, tuple[Mapping[str, Any], str, str]]:
    if set(paths) != set(_EXPECTED):
        _fail("U8-C requires exactly u8a and u8b inputs")
    result: dict[str, tuple[Mapping[str, Any], str, str]] = {}
    for kind in ("u8a", "u8b"):
        path = Path(paths[kind])
        try:
            raw = path.read_bytes()
            payload = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            _fail(f"cannot read {kind} evidence: {exc}")
        result[kind] = (_object(payload, f"{kind} evidence"), _EXPECTED[kind]["artifact"], _source_sha256(raw))
    return result


def _require_schema_status(payload: Mapping[str, Any], kind: str) -> None:
    expected = _EXPECTED[kind]
    if payload.get("schema") != expected["schema"]:
        _fail(f"{kind} schema is invalid")
    if payload.get("status") != expected["status"]:
        _fail(f"{kind} status is invalid")


def _require_boundary(payload: Mapping[str, Any], label: str) -> None:
    boundary = _object(payload.get("boundary"), f"{label} boundary")
    for key, expected in CANONICAL_BOUNDARY.items():
        if boundary.get(key) != expected:
            _fail(f"{label} boundary {key} is unsafe")


def _require_blocked_gates(payload: Mapping[str, Any], label: str) -> None:
    gates = _object(payload.get("external_gates"), f"{label} external_gates")
    if not gates or any(_object(entry, f"{label} external gate").get("status") != "blocked" for entry in gates.values()):
        _fail(f"{label} external gates are not blocked")


def _validate_source(kind: str, payload: Mapping[str, Any], source_name: str, source_sha256: str) -> dict[str, Any]:
    _require_schema_status(payload, kind)
    label = "U8-A" if kind == "u8a" else "U8-B"
    _require_boundary(payload, label)
    _require_blocked_gates(payload, label)
    if kind == "u8a":
        decision = _object(payload.get("decision"), "U8-A decision")
        for key, expected in {
            "classification": "local_preflight_passed_connected_runtime_not_verified",
            "paper_only_default": True,
            "execution_boundary_change": False,
            "owner_decision_required": True,
        }.items():
            if decision.get(key) != expected:
                _fail(f"U8-A decision {key} is unsafe")
        raw_options = decision.get("options")
        if not isinstance(raw_options, list):
            _fail("U8-A decision options must be a list")
        options: dict[str, Mapping[str, Any]] = {}
        for entry in raw_options:
            option = _object(entry, "U8-A decision option")
            option_id = option.get("id")
            if not isinstance(option_id, str):
                _fail("U8-A decision option id is invalid")
            options[option_id] = option
        if options.get("permanent-paper-only", {}).get("status") != "available-after-owner-decision":
            _fail("U8-A permanent-paper-only option is unavailable")
    else:
        if payload.get("classification") != "local_operational_controls_passed_production_operations_not_verified":
            _fail("U8-B classification is unsafe")
        for key, expected in {"paper_only_default": True, "execution_boundary_change": False, "owner_decision_required": True}.items():
            if payload.get(key) != expected:
                _fail(f"U8-B {key} is unsafe")
    return {
        "id": kind,
        "schema": _EXPECTED[kind]["schema"],
        "status": _EXPECTED[kind]["status"],
        "source_artifact": source_name,
        "source_sha256": source_sha256,
    }


def build_paper_mode(inputs: Mapping[str, tuple[Mapping[str, Any], str, str]], *, decision: str) -> dict[str, Any]:
    if decision != "permanent-paper-only":
        _fail("U8-C only accepts the permanent-paper-only decision")
    if set(inputs) != set(_EXPECTED):
        _fail("U8-C requires exactly u8a and u8b inputs")
    items = [_validate_source(kind, *inputs[kind]) for kind in ("u8a", "u8b")]
    u8a = inputs["u8a"][0]
    u8b = inputs["u8b"][0]
    report: dict[str, Any] = {
        "schema": PAPER_MODE_SCHEMA,
        "status": "accepted",
        "classification": "permanent_paper_only_by_owner_decision",
        "decision": {
            "id": "permanent-paper-only",
            "status": "accepted",
            "paper_only_permanent": True,
            "execution_boundary_change": False,
            "owner_decision_required": False,
            "rationale": "Owner selected permanent paper-only mode while connected runtime and live-readiness gates remain unavailable.",
        },
        "items": items,
        "checks": {
            "u8a_gated": u8a.get("status") == "gated",
            "u8b_gated": u8b.get("status") == "gated",
            "u8a_external_gates_blocked": all(entry.get("status") == "blocked" for entry in _object(u8a["external_gates"], "U8-A external_gates").values()),
            "u8b_external_gates_blocked": all(entry.get("status") == "blocked" for entry in _object(u8b["external_gates"], "U8-B external_gates").values()),
            "paper_only_default": u8a["decision"].get("paper_only_default") is True and u8b.get("paper_only_default") is True,
            "execution_boundary_unchanged": u8a["decision"].get("execution_boundary_change") is False and u8b.get("execution_boundary_change") is False,
            "boundary_consistent": u8a["boundary"] == u8b["boundary"] == CANONICAL_BOUNDARY,
            "credentials_disabled": CANONICAL_BOUNDARY["credentials"] is False,
            "provider_requests_zero": CANONICAL_BOUNDARY["provider_requests"] == 0,
            "mutation_routes_disabled": CANONICAL_BOUNDARY["mutation_routes"] is False,
            "live_execution_disabled": CANONICAL_BOUNDARY["live_execution"] is False,
        },
        "boundary": dict(CANONICAL_BOUNDARY),
        "external_gates": {
            "u8a": u8a["external_gates"],
            "u8b": u8b["external_gates"],
        },
        "reopen_requirements": [
            "new explicit owner decision",
            "owner VM/access and health evidence",
            "owner-only Tailscale Serve verification",
            "production observability retention and alerting evidence",
            "connected reconciliation evidence",
            "credentials and provider approval",
            "live execution authorization",
        ],
        "next_gate": "No connected or live-readiness work is authorized; reopening requires a new explicit owner decision and a complete U8 review.",
    }
    report["decision_fingerprint"] = hashlib.sha256(_canonical(report)).hexdigest()
    return report


def build_paper_mode_from_files(paths: Mapping[str, str | Path], *, decision: str = "permanent-paper-only") -> dict[str, Any]:
    return build_paper_mode(_read_inputs(paths), decision=decision)


def render_markdown(report: Mapping[str, Any]) -> str:
    items = [f"| {item['id']} | `{item['schema']}` | {item['status']} | `{item['source_sha256']}` |" for item in report["items"]]
    checks = [f"| {key} | {'PASS' if value else 'FAIL'} |" for key, value in report["checks"].items()]
    boundary = [f"| {key} | {value} |" for key, value in report["boundary"].items()]
    gates = []
    for source, entries in report["external_gates"].items():
        gates.extend(f"| {source} | {key} | {entry['status']} | {entry['reason']} |" for key, entry in entries.items())
    reopen = "\n".join(f"- {item}" for item in report["reopen_requirements"])
    return "\n".join([
        "# U8-C Permanent Paper-Only Decision", "",
        f"- Status: **{report['status'].upper()}**",
        f"- Decision fingerprint: `{report['decision_fingerprint']}`",
        f"- Classification: `{report['classification']}`", "",
        "The owner selected permanent paper-only mode. This record does not enable a connected runtime, credentials, providers, mutation routes, or live execution.", "",
        "## Source evidence", "", "| Source | Schema | Status | SHA-256 |", "| --- | --- | --- | --- |", *items,
        "", "## Checks", "", "| Check | Result |", "| --- | --- |", *checks,
        "", "## Boundary", "", "| Field | Value |", "| --- | --- |", *boundary,
        "", "## Inherited external gates", "", "| Pack | Gate | Status | Reason |", "| --- | --- | --- | --- |", *gates,
        "", "## Reopen requirements", "", reopen, "", report["next_gate"], "",
    ])


def render_paper_mode(paths: Mapping[str, str | Path], *, markdown_path: str | Path, json_path: str | Path, decision: str = "permanent-paper-only") -> dict[str, Any]:
    report = build_paper_mode_from_files(paths, decision=decision)
    markdown = Path(markdown_path)
    output = Path(json_path)
    markdown.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the U8-C permanent paper-only decision pack")
    parser.add_argument("--u8-a", required=True)
    parser.add_argument("--u8-b", required=True)
    parser.add_argument("--decision", required=True, choices=["permanent-paper-only"])
    parser.add_argument("--markdown", required=True)
    parser.add_argument("--json", dest="json_path", required=True)
    args = parser.parse_args(argv)
    try:
        report = render_paper_mode(
            {"u8a": args.u8_a, "u8b": args.u8_b},
            markdown_path=args.markdown,
            json_path=args.json_path,
            decision=args.decision,
        )
    except (OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"schema": report["schema"], "status": report["status"], "decision_fingerprint": report["decision_fingerprint"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "PAPER_MODE_SCHEMA",
    "U8CPaperModeError",
    "build_paper_mode",
    "build_paper_mode_from_files",
    "main",
    "render_markdown",
    "render_paper_mode",
]
