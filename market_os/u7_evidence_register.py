"""Fail-closed register joining the committed U7-I and hosted U7-M evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

REGISTER_SCHEMA = "market-os.u7-n-unified-evidence-register@v1"
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
_PACK_SCHEMA = "market-os.u7-i-local-evidence-pack-evidence@v1"
_DRIFT_SCHEMA = "market-os.u7-m-release-evidence-drift-evidence@v1"
_PACK_CHECKS = (
    "schemas_exact",
    "statuses_exact",
    "required_checks_passed",
    "lineage_present",
    "boundaries_consistent",
    "private_read_only_paper_only",
    "no_provider_network_credentials",
    "no_mutation_or_live_execution",
)


class EvidenceRegisterError(ValueError):
    """Raised when a U7 evidence input fails the register contract."""


def _fail(message: str) -> None:
    raise EvidenceRegisterError(message)


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{field} must be an object")
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_schema_status(payload: Mapping[str, Any], schema: str, status: str, label: str) -> None:
    if payload.get("schema") != schema:
        _fail(f"{label} schema is invalid")
    if payload.get("status") != status:
        _fail(f"{label} status is invalid")


def _require_true_checks(checks: Mapping[str, Any], keys: tuple[str, ...], label: str) -> None:
    for key in keys:
        if checks.get(key) is not True:
            _fail(f"{label} check {key} is not true")


def _normalize_drift_boundary(boundary: Mapping[str, Any]) -> dict[str, Any]:
    if dict(boundary) == CANONICAL_BOUNDARY:
        return dict(CANONICAL_BOUNDARY)
    expected = {
        "loopback_only": True,
        "synthetic": True,
        "paper_only": True,
        "read_only": True,
        "credentials": False,
        "provider_requests": 0,
        "mutation_routes": False,
        "live_trading": False,
    }
    for key, value in expected.items():
        if boundary.get(key) != value:
            _fail(f"U7-M boundary {key} is unsafe")
    return dict(CANONICAL_BOUNDARY)


def _item(identifier: str, milestone: str, schema: str, status: str, source_name: str, source_sha256: str) -> dict[str, str]:
    return {
        "id": identifier,
        "milestone": milestone,
        "schema": schema,
        "status": status,
        "source_artifact": source_name,
        "source_sha256": source_sha256,
    }


def build_register(
    pack: Mapping[str, Any],
    pack_source_name: str,
    pack_source_sha256: str,
    drift: Mapping[str, Any],
    drift_source_name: str,
    drift_source_sha256: str,
) -> dict[str, Any]:
    """Build a deterministic register from the U7-I and U7-M evidence."""
    _require_schema_status(pack, _PACK_SCHEMA, "local-verified", "U7-I evidence")
    _require_schema_status(drift, _DRIFT_SCHEMA, "ci-verified", "U7-M evidence")
    pack_checks = _object(pack.get("checks"), "U7-I checks")
    _require_true_checks(pack_checks, _PACK_CHECKS, "U7-I")
    drift_checks = _object(drift.get("checks"), "U7-M checks")
    if not drift_checks or any(value is not True for value in drift_checks.values()):
        _fail("U7-M checks are not all true")
    if drift.get("drift_count") != 0 or drift.get("drift") != []:
        _fail("U7-M drift report is not empty")
    if drift.get("targets") != ["windows-x64", "linux-x64"]:
        _fail("U7-M targets are invalid")
    versions = drift.get("release_versions")
    if not isinstance(versions, list) or len(versions) != 2 or len(set(versions)) != 2:
        _fail("U7-M release versions are invalid")

    pack_boundary = dict(_object(pack.get("boundary"), "U7-I boundary"))
    if pack_boundary != CANONICAL_BOUNDARY:
        _fail("U7-I boundary is unsafe")
    drift_boundary = _normalize_drift_boundary(_object(drift.get("boundary"), "U7-M boundary"))
    if drift_boundary != pack_boundary:
        _fail("U7-I and U7-M boundaries differ")

    deferred = sorted({str(item) for item in (*pack.get("deferred", []), *drift.get("deferred", []))})
    report: dict[str, Any] = {
        "schema": REGISTER_SCHEMA,
        "status": "passed",
        "items": [
            _item("u7-i", "U7-I", _PACK_SCHEMA, "local-verified", pack_source_name, pack_source_sha256),
            _item("u7-m", "U7-M", _DRIFT_SCHEMA, "ci-verified", drift_source_name, drift_source_sha256),
        ],
        "checks": {
            "u7_i_schema_status": True,
            "u7_m_schema_status": True,
            "u7_i_pack_passed": True,
            "u7_m_drift_count_zero": True,
            "u7_m_checks_all_true": True,
            "boundaries_consistent": True,
            "lineage_present": True,
            "private_read_only_paper_only": True,
            "no_provider_network_credentials": True,
            "no_mutation_or_live_execution": True,
        },
        "boundary": pack_boundary,
        "deferred": deferred,
        "interpretation": "Committed U7-I evidence and hosted U7-M release drift evidence are joined without deployment or live-readiness claims.",
        "next_gate": "Select the next bounded local U7 evaluation/evidence product; U5.5 remains gated on owner VM/access.",
    }
    report["register_fingerprint"] = _sha256(_canonical(report))
    return report


def _read_input(path: str | Path, label: str) -> tuple[Mapping[str, Any], str, str]:
    source = Path(path)
    try:
        raw = source.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _fail(f"cannot read {label}: {exc}")
    return _object(payload, label), source.name, _sha256(raw)


def build_register_from_files(pack_path: str | Path, drift_path: str | Path) -> dict[str, Any]:
    pack, pack_name, pack_sha256 = _read_input(pack_path, "U7-I evidence")
    drift, drift_name, drift_sha256 = _read_input(drift_path, "U7-M evidence")
    return build_register(pack, pack_name, pack_sha256, drift, drift_name, drift_sha256)


def render_markdown(register: Mapping[str, Any]) -> str:
    items = [
        f"| {item['milestone']} | `{item['schema']}` | {item['status']} | `{item['source_sha256']}` |"
        for item in register["items"]
    ]
    checks = [f"| {key} | {'PASS' if value else 'FAIL'} |" for key, value in register["checks"].items()]
    boundary = [f"| {key} | {value} |" for key, value in register["boundary"].items()]
    deferred = "\n".join(f"- {item}" for item in register["deferred"])
    return "\n".join([
        "# U7-N Unified Evidence Register",
        "",
        f"- Status: **{register['status'].upper()}**",
        f"- Register fingerprint: `{register['register_fingerprint']}`",
        "- Scope: committed U7-I evidence joined with hosted U7-M provenance evidence",
        "",
        "## Evidence items",
        "",
        "| Milestone | Schema | Status | Source SHA-256 |",
        "| --- | --- | --- | --- |",
        *items,
        "",
        "## Register checks",
        "",
        "| Check | Result |",
        "| --- | --- |",
        *checks,
        "",
        "## Shared boundary",
        "",
        "| Boundary | Value |",
        "| --- | --- |",
        *boundary,
        "",
        "## Deferred gates",
        "",
        deferred,
        "",
        register["interpretation"],
        "",
    ])


def render_register(
    pack_path: str | Path,
    drift_path: str | Path,
    *,
    markdown_path: str | Path,
    json_path: str | Path,
) -> dict[str, Any]:
    register = build_register_from_files(pack_path, drift_path)
    markdown = Path(markdown_path)
    output = Path(json_path)
    markdown.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text(render_markdown(register), encoding="utf-8")
    output.write_text(json.dumps(register, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return register


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the U7-N unified evidence register")
    parser.add_argument("--pack", required=True)
    parser.add_argument("--drift", required=True)
    parser.add_argument("--markdown", required=True)
    parser.add_argument("--json", dest="json_path", required=True)
    args = parser.parse_args(argv)
    try:
        register = render_register(
            args.pack,
            args.drift,
            markdown_path=args.markdown,
            json_path=args.json_path,
        )
    except (OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"schema": register["schema"], "status": register["status"], "register_fingerprint": register["register_fingerprint"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CANONICAL_BOUNDARY",
    "EvidenceRegisterError",
    "REGISTER_SCHEMA",
    "build_register",
    "build_register_from_files",
    "main",
    "render_markdown",
    "render_register",
]
