"""Build the local U8-A live-readiness decision pack."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

DECISION_SCHEMA = "market-os.u8-a-live-readiness-decision@v1"
CANONICAL_BOUNDARY = {
    "private": True,
    "synthetic_only": True,
    "paper_only": True,
    "read_only": True,
    "network_access": False,
    "provider_requests": 0,
    "credentials": False,
    "mutation_routes": False,
    "live_execution": False,
}
_EXPECTED = {
    "local_exit": {"milestone": "local-exit", "schema": "market-os.local-exit-gate@v1", "status": "green-local-boundary", "artifact": "local-exit-gate.json"},
    "stack": {"milestone": "U5.5", "schema": "market-os.u5-5.stack-runtime-review-evidence@v1", "status": "locally-verified-not-enabled", "artifact": "stack-runtime-review.json"},
    "promotion": {"milestone": "U5.5", "schema": "market-os.u5-5.promotion-evidence@v1", "status": "locally-verified-not-enabled", "artifact": "promotion-evidence.json"},
    "browser": {"milestone": "U5.5", "schema": "market-os.u5-5.connected-browser-smoke@v1", "status": "passed", "artifact": "connected-browser-smoke.json"},
    "release": {"milestone": "U6.4-C", "schema": "market-os.u6.4-release-hardening@v1", "status": "ci-verified-with-release-reports", "artifact": "release-hardening.json"},
    "u7": {"milestone": "U7-O", "schema": "market-os.u7-o-evidence-catalog@v1", "status": "passed", "artifact": "evidence-catalog.json"},
}


class U8AReadinessError(ValueError):
    """Raised when a U8-A source evidence item fails closed."""


def _fail(message: str) -> None:
    raise U8AReadinessError(message)


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{field} must be an object")
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        _fail(f"{field} must be a lowercase SHA-256 digest")
    return value


def _source_sha256(raw: bytes) -> str:
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def _read_inputs(paths: Mapping[str, str | Path]) -> dict[str, tuple[Mapping[str, Any], str, str]]:
    if set(paths) != set(_EXPECTED):
        _fail("U8-A requires exactly local_exit, stack, promotion, browser, release, and u7 inputs")
    result: dict[str, tuple[Mapping[str, Any], str, str]] = {}
    for kind in ("local_exit", "stack", "promotion", "browser", "release", "u7"):
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


def _require_boundary(boundary: Mapping[str, Any], label: str) -> None:
    for key, expected in CANONICAL_BOUNDARY.items():
        if boundary.get(key) != expected:
            _fail(f"{label} boundary {key} is unsafe")


def _validate_source(kind: str, payload: Mapping[str, Any], source_name: str, source_sha256: str) -> dict[str, Any]:
    _require_schema_status(payload, kind)
    _digest(source_sha256, f"{kind} source_sha256")
    if kind == "local_exit":
        scope = _object(payload.get("scope"), "local_exit scope")
        for key, expected in {
            "synthetic": True,
            "paper_only": True,
            "loopback_only": True,
            "external_mutation_api": False,
            "live_trading": False,
        }.items():
            if scope.get(key) is not expected:
                _fail(f"local exit scope {key} is unsafe")
    elif kind == "stack":
        if payload.get("contract") != "market-os.u5-5.connected-runtime-identity@v1":
            _fail("U5.5 stack contract is invalid")
        matrix = _object(payload.get("contract_matrix"), "stack contract_matrix")
        for key in (
            "runtime_trust_boundary", "principal_assertion", "subject_portfolio_authorization",
            "storage_isolation", "session_replay_and_revocation", "audit_and_redaction",
            "server_only_secrets", "abuse_limits",
        ):
            if matrix.get(key) != "locally_verified":
                _fail(f"stack contract matrix {key} is not locally verified")
        if matrix.get("promotion_health_and_rollback") != "procedure_verified_not_promoted":
            _fail("stack promotion state is unsafe")
        boundary = _object(payload.get("deployment_boundary"), "stack deployment_boundary")
        if boundary.get("owner_linux_vm_promotion") != "not-run" or boundary.get("credentials_added") is not False:
            _fail("stack deployment boundary is unsafe")
    elif kind == "promotion":
        if payload.get("mode") != "dry-run":
            _fail("promotion evidence is not dry-run")
        checks = _object(payload.get("checks"), "promotion checks")
        for key, entry in checks.items():
            status = _object(entry, f"promotion check {key}").get("status")
            if key.startswith("owner_vm_"):
                if status != "not_run":
                    _fail(f"promotion check {key} must remain not_run")
            elif status not in {"validated", "passed"}:
                _fail(f"promotion check {key} is not locally verified")
        boundary = _object(payload.get("promotion_boundary"), "promotion boundary")
        if boundary.get("enabled") is not False or boundary.get("owner_vm_promotion") != "pending" or boundary.get("rollback") != "pending":
            _fail("promotion boundary is unsafe")
        if payload.get("failed_checks") != []:
            _fail("promotion evidence has failed checks")
    elif kind == "browser":
        if payload.get("status") != "passed" or payload.get("failed_requests") != []:
            _fail("connected browser smoke did not pass")
        browser = _object(payload.get("browser"), "browser smoke")
        for key in ("direct_next_status", "direct_python_status", "owner_disallowed_route_status", "owner_other_portfolio_status", "unknown_subject_status"):
            if browser.get(key) in {200, 201}:
                _fail(f"browser denial check {key} is unsafe")
    elif kind == "release":
        smoke = _object(payload.get("signed_smoke"), "release signed_smoke")
        for version in ("known_good", "candidate"):
            entry = _object(smoke.get(version), f"release {version} smoke")
            for key in ("readyz_status", "healthz_status", "overview_status", "runtime_status"):
                if entry.get(key) != 200:
                    _fail(f"release {version} {key} is not 200")
            for key in ("identity", "audit", "read_only_paper_only", "private_loopback", "storage_isolation", "api_closed", "next_closed"):
                if entry.get(key) is not True:
                    _fail(f"release {version} {key} is unsafe")
        drill = _object(payload.get("promotion_rollback"), "release promotion_rollback")
        for key in ("candidate_signed", "known_good_signed", "versions_differ", "failed_launch_restored_metadata", "promotion_current_candidate", "known_good_preserved", "rollback_available_before", "rollback_to_known_good", "storage_isolation"):
            if drill.get(key) is not True:
                _fail(f"release rollback check {key} is unsafe")
        boundary = _object(payload.get("boundary"), "release boundary")
        if boundary.get("u5_5_owner_vm_enabled") is not False or boundary.get("live_trading") is not False:
            _fail("release boundary is unsafe")
    elif kind == "u7":
        checks = _object(payload.get("checks"), "U7-O checks")
        if not checks or any(value is not True for value in checks.values()):
            _fail("U7-O checks are not all true")
        _digest(payload.get("catalog_fingerprint"), "U7-O catalog_fingerprint")
        _require_boundary(_object(payload.get("boundary"), "U7-O boundary"), "U7-O")
    return {
        "id": kind,
        "milestone": _EXPECTED[kind]["milestone"],
        "schema": _EXPECTED[kind]["schema"],
        "status": _EXPECTED[kind]["status"],
        "source_artifact": source_name,
        "source_sha256": source_sha256,
    }


def build_decision(inputs: Mapping[str, tuple[Mapping[str, Any], str, str]]) -> dict[str, Any]:
    if set(inputs) != set(_EXPECTED):
        _fail("U8-A requires exactly local_exit, stack, promotion, browser, release, and u7 inputs")
    items = [_validate_source(kind, *inputs[kind]) for kind in ("local_exit", "stack", "promotion", "browser", "release", "u7")]
    required_before_live = list(inputs["stack"][0].get("required_before_connected_web", []))
    if not required_before_live:
        _fail("U5.5 required_before_connected_web is empty")
    local_checks = {
        "local_exit_gate_green": True,
        "u7_catalog_passed": True,
        "u5_5_contract_defined": True,
        "identity_and_authorization_contract": True,
        "storage_isolation_contract": True,
        "session_replay_revocation_contract": True,
        "audit_redaction_contract": True,
        "server_only_secrets_contract": True,
        "abuse_limits_contract": True,
        "connected_browser_smoke_passed": True,
        "local_promotion_rollback_simulation": True,
        "u6_4_signed_smoke_and_rollback": True,
        "paper_boundary_consistent": True,
    }
    external_gates = {
        "owner_vm_access": {"status": "blocked", "blocking": True, "reason": "owner VM/access is not available"},
        "owner_vm_health": {"status": "blocked", "blocking": True, "reason": "owner VM health probe has not run"},
        "owner_tailscale": {"status": "blocked", "blocking": True, "reason": "owner-only Tailscale Serve probe has not run"},
        "owner_vm_promotion_and_rollback": {"status": "blocked", "blocking": True, "reason": "connected promotion and rollback remain pending"},
        "production_observability": {"status": "blocked", "blocking": True, "reason": "production retention, alerting, and operator review are not verified"},
        "credentials_provider_approval": {"status": "blocked", "blocking": True, "reason": "credentials and provider approval remain disabled"},
        "live_execution_authorization": {"status": "blocked", "blocking": True, "reason": "live execution is disabled and separately gated"},
    }
    decision = {
        "status": "gated",
        "classification": "local_preflight_passed_connected_runtime_not_verified",
        "execution_boundary_change": False,
        "paper_only_default": True,
        "owner_decision_required": True,
        "options": [
            {"id": "permanent-paper-only", "status": "available-after-owner-decision"},
            {"id": "continue-live-readiness", "status": "blocked-on-external-gates"},
        ],
    }
    report: dict[str, Any] = {
        "schema": DECISION_SCHEMA,
        "status": "gated",
        "decision": decision,
        "items": items,
        "local_checks": local_checks,
        "external_gates": external_gates,
        "boundary": dict(CANONICAL_BOUNDARY),
        "required_before_live": required_before_live,
        "deferred": sorted({
            "owner VM/access",
            "owner-only Tailscale Serve verification",
            "connected promotion and rollback",
            "production observability retention and alerting",
            "credentials and provider approval",
            "live execution authorization",
            "mutation routes",
            "mobile",
            "embedded Python runtime/native installer",
        }),
        "interpretation": "Local U8-A preflight passes the existing paper-only contracts but does not verify or enable a connected runtime or live execution boundary.",
        "next_gate": "Owner decision plus VM/access evidence for U5.5 before any connected or live-readiness change.",
    }
    report["decision_fingerprint"] = hashlib.sha256(_canonical(report)).hexdigest()
    return report


def build_decision_from_files(paths: Mapping[str, str | Path]) -> dict[str, Any]:
    return build_decision(_read_inputs(paths))


def render_markdown(report: Mapping[str, Any]) -> str:
    items = [f"| {item['milestone']} | `{item['schema']}` | {item['status']} | `{item['source_sha256']}` |" for item in report["items"]]
    local = [f"| {key} | {'PASS' if value else 'FAIL'} |" for key, value in report["local_checks"].items()]
    external = [f"| {key} | {entry['status']} | {entry['reason']} |" for key, entry in report["external_gates"].items()]
    boundary = [f"| {key} | {value} |" for key, value in report["boundary"].items()]
    deferred = "\n".join(f"- {item}" for item in report["deferred"])
    return "\n".join([
        "# U8-A Live-Readiness Decision Pack", "",
        f"- Status: **{report['status'].upper()}**",
        f"- Decision fingerprint: `{report['decision_fingerprint']}`",
        f"- Classification: `{report['decision']['classification']}`", "",
        "## Evidence items", "", "| Milestone | Schema | Status | Source SHA-256 |", "| --- | --- | --- | --- |", *items,
        "", "## Local checks", "", "| Check | Result |", "| --- | --- |", *local,
        "", "## External gates", "", "| Gate | Status | Reason |", "| --- | --- | --- |", *external,
        "", "## Boundary", "", "| Boundary | Value |", "| --- | --- |", *boundary,
        "", "## Decision", "", f"- Paper-only default: **{report['decision']['paper_only_default']}**",
        f"- Execution boundary change: **{report['decision']['execution_boundary_change']}**",
        f"- Owner decision required: **{report['decision']['owner_decision_required']}**", "",
        "## Deferred gates", "", deferred, "", report["interpretation"], "",
    ])


def render_decision(paths: Mapping[str, str | Path], *, markdown_path: str | Path, json_path: str | Path) -> dict[str, Any]:
    report = build_decision_from_files(paths)
    markdown = Path(markdown_path)
    output = Path(json_path)
    markdown.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the U8-A local live-readiness decision pack")
    for name in ("local-exit", "stack", "promotion", "browser", "release", "u7"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--markdown", required=True)
    parser.add_argument("--json", dest="json_path", required=True)
    args = parser.parse_args(argv)
    try:
        report = render_decision(
            {"local_exit": args.local_exit, "stack": args.stack, "promotion": args.promotion,
             "browser": args.browser, "release": args.release, "u7": args.u7},
            markdown_path=args.markdown,
            json_path=args.json_path,
        )
    except (OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"schema": report["schema"], "status": report["status"], "decision_fingerprint": report["decision_fingerprint"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["CANONICAL_BOUNDARY", "DECISION_SCHEMA", "U8AReadinessError", "build_decision", "build_decision_from_files", "main", "render_decision", "render_markdown"]
