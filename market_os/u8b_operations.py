"""Build the local U8-B operational-readiness decision pack."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .u8a_readiness import CANONICAL_BOUNDARY

OPERATIONS_SCHEMA = "market-os.u8-b-local-operational-readiness@v1"
_EXPECTED = {
    "observability": {
        "schema": "market-os.u5.3-deployment-access-observability@v1",
        "status": "implemented-local",
        "artifact": "u5-3-deployment-access-observability.json",
    },
    "retention": {
        "schema": "market-os.b4-20.retention-archive-preflight-evidence@v1",
        "status": "implemented",
        "artifact": "b4-20-retention-archive-preflight.json",
    },
    "platform": {
        "schema": "market-os.platform-toolchain-readiness@v1",
        "status": "locally-scaffolded-not-promoted",
        "artifact": "platform-toolchain-readiness.json",
    },
    "release": {
        "schema": "market-os.u6.4-release-hardening@v1",
        "status": "ci-verified-with-release-reports",
        "artifact": "u6-4-release-hardening.json",
    },
    "u8a": {
        "schema": "market-os.u8-a-live-readiness-decision@v1",
        "status": "gated",
        "artifact": "u8-a-live-readiness-decision.json",
    },
}


class U8BOperationsError(ValueError):
    """Raised when an U8-B source evidence item fails closed."""


def _fail(message: str) -> None:
    raise U8BOperationsError(message)


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{field} must be an object")
    return value


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        _fail(f"{field} must be a lowercase SHA-256 digest")
    return value


def _source_sha256(raw: bytes) -> str:
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _read_inputs(paths: Mapping[str, str | Path]) -> dict[str, tuple[Mapping[str, Any], str, str]]:
    if set(paths) != set(_EXPECTED):
        _fail("U8-B requires exactly observability, retention, platform, release, and u8a inputs")
    result: dict[str, tuple[Mapping[str, Any], str, str]] = {}
    for kind in ("observability", "retention", "platform", "release", "u8a"):
        path = Path(paths[kind])
        try:
            raw = path.read_bytes()
            payload = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            _fail(f"cannot read {kind} evidence: {exc}")
        if not isinstance(payload, Mapping):
            _fail(f"{kind} evidence must be an object")
        result[kind] = (payload, _EXPECTED[kind]["artifact"], _source_sha256(raw))
    return result


def _require_schema_status(payload: Mapping[str, Any], kind: str) -> None:
    expected = _EXPECTED[kind]
    if payload.get("schema") != expected["schema"]:
        _fail(f"{kind} schema is invalid")
    if payload.get("status") != expected["status"]:
        _fail(f"{kind} status is invalid")


def _require_flag(payload: Mapping[str, Any], field: str, expected: Any, label: str) -> None:
    actual = payload.get(field)
    matches = actual is expected if isinstance(expected, bool) else type(actual) is type(expected) and actual == expected
    if not matches:
        _fail(f"{label} {field} is unsafe")


def _validate_source(kind: str, payload: Mapping[str, Any], source_name: str, source_sha256: str) -> dict[str, Any]:
    _require_schema_status(payload, kind)
    _digest(source_sha256, f"{kind} source_sha256")
    if kind == "observability":
        handoff = _object(payload.get("static_handoff"), "observability static_handoff")
        for key in ("exact_file_set", "sha256_entries", "deterministic_fingerprint"):
            _require_flag(handoff, key, True, "observability static_handoff")
        for key in ("credentials", "public_deployment"):
            _require_flag(handoff, key, False, "observability static_handoff")
        gateway = _object(payload.get("local_gateway"), "observability local_gateway")
        for key, expected in {
            "request_id_response_header": "X-Request-ID",
            "request_id_audit_field": True,
            "query_values_logged": False,
            "loopback_only": True,
            "untrusted_host_rejected": True,
            "authentication": False,
            "mutation_routes": False,
        }.items():
            _require_flag(gateway, key, expected, "observability local_gateway")
        verification = _object(payload.get("verification"), "observability verification")
        if not verification or any(value is not True for value in verification.values()):
            _fail("observability verification is not all true")
    elif kind == "retention":
        boundary = _object(payload.get("boundary"), "retention boundary")
        for key, expected in {
            "synthetic_only": True,
            "paper_only": True,
            "local_only": True,
            "network": False,
            "http_mutation_routes": False,
            "cli_mutation_routes": False,
        }.items():
            _require_flag(boundary, key, expected, "retention boundary")
        policy = _object(payload.get("policy"), "retention policy")
        for key, expected in {
            "source_retention": "indefinite-local",
            "deletion": False,
            "deletion_eligible": False,
            "mutation": False,
        }.items():
            _require_flag(policy, key, expected, "retention policy")
        _require_flag(payload, "archive_validation", "read_only_streamed", "retention")
        _require_flag(payload, "paths_returned", False, "retention")
        verification = _object(payload.get("verification"), "retention verification")
        for key in ("compileall", "secret_scan", "diff_check"):
            _require_flag(verification, key, "passed", "retention verification")
        evidence_validation = verification.get("evidence_validation")
        if not isinstance(evidence_validation, str) or "validated" not in evidence_validation:
            _fail("retention verification evidence_validation is unsafe")
        restore_promotion = verification.get("restore_promotion")
        if not isinstance(restore_promotion, str) or not restore_promotion.startswith("passed-"):
            _fail("retention verification restore_promotion is unsafe")
    elif kind == "platform":
        observability = _object(payload.get("observability"), "platform observability")
        for key, expected in {
            "metrics": "prometheus-compatible-loopback-endpoint",
            "dashboards": "grafana-private-compose-profile",
            "logs": "loki-promtail-jsonl-compose-profile",
            "public_ingress": False,
        }.items():
            _require_flag(observability, key, expected, "platform observability")
        iac = _object(payload.get("iac"), "platform iac")
        _require_flag(iac, "production_apply", False, "platform iac")
        devsecops = _object(payload.get("devsecops"), "platform devsecops")
        if not devsecops or any(value is not True for value in devsecops.values()):
            _fail("platform devsecops checks are not all true")
        mlops = _object(payload.get("mlops"), "platform mlops")
        _require_flag(mlops, "network_requests", 0, "platform mlops")
        _require_flag(mlops, "provider_requests", 0, "platform mlops")
        _require_flag(mlops, "promotion_decision", "not-promoted", "platform mlops")
        boundary = _object(payload.get("security_boundary"), "platform security_boundary")
        for key, expected in {
            "synthetic_only": True,
            "paper_only": True,
            "read_only": True,
            "live_trading": False,
            "provider_credentials": False,
        }.items():
            _require_flag(boundary, key, expected, "platform security_boundary")
    elif kind == "release":
        smoke = _object(payload.get("signed_smoke"), "release signed_smoke")
        for version in ("known_good", "candidate"):
            entry = _object(smoke.get(version), f"release {version} smoke")
            for key in ("readyz_status", "healthz_status", "overview_status", "runtime_status"):
                _require_flag(entry, key, 200, f"release {version} smoke")
        drill = _object(payload.get("promotion_rollback"), "release promotion_rollback")
        for key in ("candidate_signed", "known_good_signed", "versions_differ", "failed_launch_restored_metadata", "promotion_current_candidate", "known_good_preserved", "rollback_available_before", "rollback_to_known_good", "storage_isolation"):
            _require_flag(drill, key, True, "release promotion_rollback")
        boundary = _object(payload.get("boundary"), "release boundary")
        for key, expected in {"u5_5_owner_vm_enabled": False, "live_trading": False}.items():
            _require_flag(boundary, key, expected, "release boundary")
    elif kind == "u8a":
        decision = _object(payload.get("decision"), "U8-A decision")
        for key, expected in {
            "classification": "local_preflight_passed_connected_runtime_not_verified",
            "paper_only_default": True,
            "execution_boundary_change": False,
            "owner_decision_required": True,
        }.items():
            _require_flag(decision, key, expected, "U8-A decision")
        boundary = _object(payload.get("boundary"), "U8-A boundary")
        for key, expected in CANONICAL_BOUNDARY.items():
            _require_flag(boundary, key, expected, "U8-A boundary")
        local_checks = _object(payload.get("local_checks"), "U8-A local_checks")
        if not local_checks or any(value is not True for value in local_checks.values()):
            _fail("U8-A local checks are not all true")
        gates = _object(payload.get("external_gates"), "U8-A external_gates")
        if not gates or any(_object(entry, "U8-A external gate").get("status") != "blocked" for entry in gates.values()):
            _fail("U8-A external gates are not blocked")
    return {
        "id": kind,
        "schema": _EXPECTED[kind]["schema"],
        "status": _EXPECTED[kind]["status"],
        "source_artifact": source_name,
        "source_sha256": source_sha256,
    }


def build_operations(inputs: Mapping[str, tuple[Mapping[str, Any], str, str]]) -> dict[str, Any]:
    if set(inputs) != set(_EXPECTED):
        _fail("U8-B requires exactly observability, retention, platform, release, and u8a inputs")
    items = [_validate_source(kind, *inputs[kind]) for kind in ("observability", "retention", "platform", "release", "u8a")]
    local_checks = {
        "request_correlation_and_redaction": True,
        "loopback_access_boundary": True,
        "bounded_metrics_labels": True,
        "private_observability_profile": True,
        "read_only_retention_preflight": True,
        "atomic_backup_restore_evidence": True,
        "signed_release_rollback_evidence": True,
        "u8a_boundary_chain": True,
    }
    external_gates = {
        "production_log_retention_and_alerting": {"status": "blocked", "blocking": True, "reason": "production retention, alert ownership, and alert delivery are not verified"},
        "operator_on_call_and_review": {"status": "blocked", "blocking": True, "reason": "owner/operator review and incident acknowledgement are not verified"},
        "owner_vm_failure_drill": {"status": "blocked", "blocking": True, "reason": "owner VM access and host failure drill are not available"},
        "connected_reconciliation": {"status": "blocked", "blocking": True, "reason": "connected broker/provider reconciliation is disabled"},
        "live_execution_authorization": {"status": "blocked", "blocking": True, "reason": "live execution remains separately gated"},
    }
    report: dict[str, Any] = {
        "schema": OPERATIONS_SCHEMA,
        "status": "gated",
        "classification": "local_operational_controls_passed_production_operations_not_verified",
        "paper_only_default": True,
        "execution_boundary_change": False,
        "owner_decision_required": True,
        "items": items,
        "local_checks": local_checks,
        "external_gates": external_gates,
        "boundary": dict(CANONICAL_BOUNDARY),
        "deferred": sorted({
            "production log retention and alerting",
            "operator on-call and review",
            "owner VM failure drill",
            "connected reconciliation",
            "credentials and providers",
            "live execution authorization",
            "mutation routes",
        }),
        "interpretation": "U8-B verifies local operational controls and preserves the paper-only boundary; production operations and connected reconciliation remain gated.",
        "next_gate": "Owner VM/access plus production observability and reconciliation evidence before any connected or live-readiness change.",
    }
    report["operations_fingerprint"] = hashlib.sha256(_canonical(report)).hexdigest()
    return report


def build_operations_from_files(paths: Mapping[str, str | Path]) -> dict[str, Any]:
    return build_operations(_read_inputs(paths))


def render_markdown(report: Mapping[str, Any]) -> str:
    items = [f"| `{item['schema']}` | {item['status']} | `{item['source_sha256']}` |" for item in report["items"]]
    local = [f"| {key} | {'PASS' if value else 'FAIL'} |" for key, value in report["local_checks"].items()]
    external = [f"| {key} | {entry['status']} | {entry['reason']} |" for key, entry in report["external_gates"].items()]
    boundary = [f"| {key} | {value} |" for key, value in report["boundary"].items()]
    deferred = "\n".join(f"- {item}" for item in report["deferred"])
    return "\n".join([
        "# U8-B Local Operational Readiness", "",
        f"- Status: **{report['status'].upper()}**",
        f"- Operations fingerprint: `{report['operations_fingerprint']}`",
        f"- Classification: `{report['classification']}`", "",
        "## Evidence items", "", "| Schema | Status | Source SHA-256 |", "| --- | --- | --- |", *items,
        "", "## Local checks", "", "| Check | Result |", "| --- | --- |", *local,
        "", "## External gates", "", "| Gate | Status | Reason |", "| --- | --- | --- |", *external,
        "", "## Boundary", "", "| Boundary | Value |", "| --- | --- |", *boundary,
        "", "## Deferred", "", deferred, "", report["interpretation"], "",
    ])


def render_operations(paths: Mapping[str, str | Path], *, markdown_path: str | Path, json_path: str | Path) -> dict[str, Any]:
    report = build_operations_from_files(paths)
    markdown = Path(markdown_path)
    output = Path(json_path)
    markdown.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the U8-B local operational-readiness pack")
    for name in ("observability", "retention", "platform", "release", "u8-a"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--markdown", required=True)
    parser.add_argument("--json", dest="json_path", required=True)
    args = parser.parse_args(argv)
    try:
        report = render_operations(
            {"observability": args.observability, "retention": args.retention, "platform": args.platform, "release": args.release, "u8a": getattr(args, "u8_a")},
            markdown_path=args.markdown,
            json_path=args.json_path,
        )
    except (OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"schema": report["schema"], "status": report["status"], "operations_fingerprint": report["operations_fingerprint"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["OPERATIONS_SCHEMA", "U8BOperationsError", "build_operations", "build_operations_from_files", "main", "render_markdown", "render_operations"]
