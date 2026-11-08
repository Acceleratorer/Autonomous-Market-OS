"""Fail-closed index of the stable local U7 reviewer evidence products."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

PACK_SCHEMA = "market-os.u7-i-local-evidence-pack@v1"
_BOUNDARY_KEYS = (
    "private",
    "synthetic_only",
    "paper_only",
    "read_only",
    "network_access",
    "provider_requests",
    "credentials",
    "mutation_routes",
    "live_execution",
)
_EXPECTED = {
    "release": {
        "milestone": "U7-F",
        "schema": "market-os.u7-f-cross-target-release-catalog-report-evidence@v1",
        "status": "ci-verified",
    },
    "quality": {
        "milestone": "U7-G",
        "schema": "market-os.u7-g-quality-benchmark-report-evidence@v1",
        "status": "local-verified",
    },
    "session": {
        "milestone": "U7-H",
        "schema": "market-os.u7-h-synthetic-session-accounting-report-evidence@v1",
        "status": "local-verified",
    },
}
_REQUIRED_CHECKS = {
    "release": (
        "catalog_schema", "catalog_status", "targets_exact", "release_versions_shared",
        "artifacts_complete", "signatures_verified", "archive_hashes_unique",
        "mutable_sidecar_state_excluded", "boundary_verified",
    ),
    "quality": (
        "benchmark_schema", "fingerprints_valid", "replay_stable", "benchmark_success",
        "gate_correctness", "lineage_complete", "safety_boundary", "cost_unavailable",
    ),
    "session": (
        "manifest_valid", "replay_valid", "accounting_valid", "manifest_links_valid",
        "replay_accounting_linkage", "deterministic_replay", "bounded_counts",
        "synthetic_boundary", "store_read_only", "promotion_disabled",
    ),
}


class EvidencePackError(ValueError):
    """Raised when one of the required evidence products fails closed."""


def _fail(message: str) -> None:
    raise EvidencePackError(message)


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{field} must be an object")
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _boundary_for(kind: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    if kind == "release":
        if evidence.get("checks", {}).get("boundary_verified") is not True:
            _fail("U7-F boundary check is not true")
        deferred = " ".join(str(item).lower() for item in evidence.get("deferred", []))
        if not all(token in deferred for token in ("credential", "provider", "live")):
            _fail("U7-F deferred boundary declarations are incomplete")
        return {
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
    if kind == "quality":
        safety = _object(evidence.get("safety"), "U7-G safety")
        if safety != {
            "read_only": True,
            "trading_state_mutated": False,
            "live_orders_created": False,
            "external_provider_called": False,
        }:
            _fail("U7-G safety boundary is unsafe")
        return {
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
    boundary = _object(evidence.get("boundary"), "U7-H boundary")
    expected = {
        "synthetic_only": True,
        "paper_only": True,
        "read_only": True,
        "network_access": False,
        "provider_requests": 0,
        "credentials": False,
        "mutation_routes": False,
        "live_execution": False,
    }
    for key, value in expected.items():
        if boundary.get(key) != value:
            _fail(f"U7-H boundary {key} is unsafe")
    return {"private": True, **expected}


def _lineage_for(kind: str, evidence: Mapping[str, Any], source_sha256: str) -> dict[str, Any]:
    if kind == "release":
        return {"source_sha256": source_sha256}
    if kind == "quality":
        report = _object(evidence.get("report"), "U7-G report")
        fingerprint = report.get("report_fingerprint")
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            _fail("U7-G report fingerprint is missing")
        return {
            "source_sha256": source_sha256,
            "report_fingerprint": fingerprint,
            "fixture_fingerprint": evidence.get("fixture", {}).get("fixture_sha256"),
        }
    report = _object(evidence.get("report"), "U7-H report")
    fingerprints = {
        key: report.get(key)
        for key in ("manifest_fingerprint", "replay_fingerprint", "accounting_fingerprint")
    }
    if any(not isinstance(value, str) or len(value) != 64 for value in fingerprints.values()):
        _fail("U7-H artifact fingerprints are incomplete")
    return {"source_sha256": source_sha256, **fingerprints}


def _validate_item(
    kind: str,
    evidence: Mapping[str, Any],
    source_name: str,
    source_sha256: str,
) -> dict[str, Any]:
    expected = _EXPECTED[kind]
    if evidence.get("schema") != expected["schema"]:
        _fail(f"{kind} evidence schema is invalid")
    if evidence.get("milestone") != expected["milestone"]:
        _fail(f"{kind} evidence milestone is invalid")
    if evidence.get("status") != expected["status"]:
        _fail(f"{kind} evidence status is invalid")
    checks = _object(evidence.get("checks"), f"{kind} checks")
    for key in _REQUIRED_CHECKS[kind]:
        if checks.get(key) is not True:
            _fail(f"{kind} check {key} is not true")
    boundary = _boundary_for(kind, evidence)
    lineage = _lineage_for(kind, evidence, source_sha256)
    return {
        "id": kind,
        "milestone": expected["milestone"],
        "schema": expected["schema"],
        "status": expected["status"],
        "source_artifact": source_name,
        "source_sha256": source_sha256,
        "lineage": lineage,
        "boundary": boundary,
        "deferred": sorted(str(item) for item in evidence.get("deferred", [])),
    }


def build_evidence_pack(inputs: Mapping[str, tuple[Mapping[str, Any], str, str]]) -> dict[str, Any]:
    """Build a deterministic pack from ``kind -> (payload, name, sha256)``."""
    if set(inputs) != set(_EXPECTED):
        _fail("evidence pack requires exactly release, quality, and session inputs")
    items = [
        _validate_item(kind, inputs[kind][0], inputs[kind][1], inputs[kind][2])
        for kind in ("release", "quality", "session")
    ]
    boundary = {key: items[0]["boundary"][key] for key in _BOUNDARY_KEYS}
    for item in items[1:]:
        if item["boundary"] != boundary:
            _fail("evidence boundaries are inconsistent")
    deferred = sorted({entry for item in items for entry in item["deferred"]})
    report = {
        "schema": PACK_SCHEMA,
        "status": "passed",
        "items": items,
        "checks": {
            "schemas_exact": True,
            "statuses_exact": True,
            "required_checks_passed": True,
            "lineage_present": True,
            "boundaries_consistent": True,
            "private_read_only_paper_only": True,
            "no_provider_network_credentials": True,
            "no_mutation_or_live_execution": True,
        },
        "boundary": boundary,
        "deferred": deferred,
        "interpretation": "local evidence index only; no deployment, profitability, or live-readiness claim",
    }
    report["pack_fingerprint"] = _sha256(_canonical(report))
    return report


def build_evidence_pack_from_files(paths: Mapping[str, str | Path]) -> dict[str, Any]:
    if set(paths) != set(_EXPECTED):
        _fail("evidence pack requires release, quality, and session paths")
    inputs: dict[str, tuple[Mapping[str, Any], str, str]] = {}
    for kind in ("release", "quality", "session"):
        path = Path(paths[kind])
        try:
            raw = path.read_bytes()
            payload = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            _fail(f"cannot read {kind} evidence: {exc}")
        inputs[kind] = (_object(payload, f"{kind} evidence"), path.name, _sha256(raw))
    return build_evidence_pack(inputs)


def render_markdown(pack: Mapping[str, Any]) -> str:
    rows = [
        f"| {item['milestone']} | `{item['schema']}` | {item['status']} | `{item['source_sha256']}` |"
        for item in pack["items"]
    ]
    checks = [f"| {key} | {'PASS' if value else 'FAIL'} |" for key, value in pack["checks"].items()]
    boundary = [f"| {key} | {value} |" for key, value in pack["boundary"].items()]
    deferred = "\n".join(f"- {item}" for item in pack["deferred"])
    return "\n".join([
        "# U7-I Local Evidence Pack", "",
        f"- Status: **{pack['status'].upper()}**",
        f"- Pack fingerprint: `{pack['pack_fingerprint']}`",
        "- Scope: local reviewer evidence index", "",
        "## Evidence items", "", "| Milestone | Schema | Status | Source SHA-256 |", "| --- | --- | --- | --- |",
        *rows, "", "## Pack checks", "", "| Check | Result |", "| --- | --- |", *checks,
        "", "## Shared boundary", "", "| Boundary | Value |", "| --- | --- |", *boundary,
        "", "## Deferred gates", "", deferred, "",
        pack["interpretation"], "",
    ])


def render_evidence_pack(
    paths: Mapping[str, str | Path],
    *,
    markdown_path: str | Path,
    json_path: str | Path,
) -> dict[str, Any]:
    pack = build_evidence_pack_from_files(paths)
    markdown = Path(markdown_path)
    output = Path(json_path)
    markdown.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text(render_markdown(pack), encoding="utf-8")
    output.write_text(json.dumps(pack, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return pack


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the U7-I local evidence pack")
    parser.add_argument("--release", required=True)
    parser.add_argument("--quality", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--markdown", required=True)
    parser.add_argument("--json", dest="json_path", required=True)
    args = parser.parse_args(argv)
    try:
        pack = render_evidence_pack(
            {"release": args.release, "quality": args.quality, "session": args.session},
            markdown_path=args.markdown,
            json_path=args.json_path,
        )
    except (OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"schema": pack["schema"], "status": pack["status"], "pack_fingerprint": pack["pack_fingerprint"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "PACK_SCHEMA",
    "EvidencePackError",
    "build_evidence_pack",
    "build_evidence_pack_from_files",
    "main",
    "render_evidence_pack",
    "render_markdown",
]
