"""Fail-closed catalog for the complete local U7 evidence surface."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

CATALOG_SCHEMA = "market-os.u7-o-evidence-catalog@v1"
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
    "register": {
        "milestone": "U7-N",
        "schema": "market-os.u7-n-unified-evidence-register@v1",
        "status": "passed",
        "artifact": "unified-evidence-register.json",
    },
    "economic": {
        "milestone": "U7-J",
        "schema": "market-os.u7-j-synthetic-economic-report@v1",
        "status": "passed",
        "artifact": "economic-report.json",
    },
    "tools": {
        "milestone": "U7-K",
        "schema": "market-os.u7-k-cli-tool-registry-report@v1",
        "status": "passed",
        "artifact": "tool-registry.json",
    },
    "research": {
        "milestone": "U7-L",
        "schema": "market-os.u7-l-research-brief-evidence@v1",
        "status": "passed",
        "artifact": "research-brief-evidence.json",
    },
}


class EvidenceCatalogError(ValueError):
    """Raised when a U7 evidence input fails the catalog contract."""


def _fail(message: str) -> None:
    raise EvidenceCatalogError(message)


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{field} must be an object")
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _source_sha256(raw: bytes) -> str:
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        _fail(f"{label} must be a lowercase SHA-256 digest")
    return value


def _require_schema_status(payload: Mapping[str, Any], kind: str) -> None:
    expected = _EXPECTED[kind]
    if payload.get("schema") != expected["schema"]:
        _fail(f"{kind} schema is invalid")
    if payload.get("status") != expected["status"]:
        _fail(f"{kind} status is invalid")


def _require_all_checks(payload: Mapping[str, Any], kind: str) -> None:
    checks = _object(payload.get("checks"), f"{kind} checks")
    if not checks or any(value is not True for value in checks.values()):
        _fail(f"{kind} checks are not all true")


def _normalize_boundary(payload: Mapping[str, Any], kind: str) -> dict[str, Any]:
    boundary = _object(payload.get("boundary"), f"{kind} boundary")
    for key, expected in CANONICAL_BOUNDARY.items():
        if boundary.get(key) != expected:
            _fail(f"{kind} boundary {key} is unsafe")
    if kind == "economic" and boundary.get("predictive_evidence") is not False:
        _fail("economic boundary predictive_evidence is unsafe")
    if kind == "economic" and boundary.get("promotion_approved") is not False:
        _fail("economic boundary promotion_approved is unsafe")
    if kind == "tools" and boundary.get("generated_cli_execution") is not False:
        _fail("tools boundary generated_cli_execution is unsafe")
    return dict(CANONICAL_BOUNDARY)


def _report_fingerprint(payload: Mapping[str, Any], kind: str) -> str:
    expected = _digest(payload.get("report_fingerprint"), f"{kind} report_fingerprint")
    body = {key: value for key, value in payload.items() if key != "report_fingerprint"}
    if _fingerprint(body) != expected:
        _fail(f"{kind} report fingerprint is invalid")
    return expected


def _register_fingerprint(payload: Mapping[str, Any]) -> str:
    expected = _digest(payload.get("register_fingerprint"), "register_fingerprint")
    body = {key: value for key, value in payload.items() if key != "register_fingerprint"}
    if _fingerprint(body) != expected:
        _fail("register fingerprint is invalid")
    return expected


def _source_hash(payload: Mapping[str, Any], kind: str) -> str:
    if kind == "register":
        return _digest(payload.get("register_fingerprint"), "register_fingerprint")
    if kind == "research":
        source = _object(payload.get("source"), "research source")
        return _digest(source.get("sha256"), "research source.sha256")
    fixture = _object(payload.get("fixture"), f"{kind} fixture")
    return _digest(fixture.get("source_sha256"), f"{kind} fixture.source_sha256")


def _lineage(payload: Mapping[str, Any], kind: str, fingerprint: str) -> dict[str, Any]:
    if kind == "register":
        return {"register_fingerprint": fingerprint}
    if kind == "research":
        source = _object(payload.get("source"), "research source")
        artifact = _object(payload.get("artifact"), "research artifact")
        return {
            "report_fingerprint": fingerprint,
            "synthesis_fingerprint": _digest(source.get("synthesis_fingerprint"), "research synthesis_fingerprint"),
            "artifact_sha256": _digest(artifact.get("sha256"), "research artifact.sha256"),
        }
    fixture = _object(payload.get("fixture"), f"{kind} fixture")
    return {
        "report_fingerprint": fingerprint,
        "fixture_fingerprint": _digest(fixture.get("fixture_fingerprint"), f"{kind} fixture_fingerprint"),
    }


def _validate_item(kind: str, payload: Mapping[str, Any], source_name: str, source_sha256: str) -> tuple[dict[str, Any], dict[str, Any]]:
    _require_schema_status(payload, kind)
    if kind == "register":
        _require_all_checks(payload, kind)
        fingerprint = _register_fingerprint(payload)
    else:
        _require_all_checks(payload, kind)
        fingerprint = _report_fingerprint(payload, kind)
    boundary = _normalize_boundary(payload, kind)
    source_digest = _source_hash(payload, kind)
    _digest(source_sha256, f"{kind} evidence source_sha256")
    expected = _EXPECTED[kind]
    item = {
        "id": kind,
        "milestone": expected["milestone"],
        "schema": expected["schema"],
        "status": expected["status"],
        "source_artifact": expected["artifact"],
        "source_sha256": source_sha256,
        "lineage": _lineage(payload, kind, fingerprint),
        "fixture_or_source_sha256": source_digest,
        "boundary": boundary,
        "deferred": sorted(str(value) for value in payload.get("deferred", [])),
    }
    return item, boundary


def build_catalog(inputs: Mapping[str, tuple[Mapping[str, Any], str, str]]) -> dict[str, Any]:
    """Build a deterministic catalog from U7-N/J/K/L evidence."""
    if set(inputs) != set(_EXPECTED):
        _fail("evidence catalog requires exactly register, economic, tools, and research inputs")
    items: list[dict[str, Any]] = []
    boundaries: list[dict[str, Any]] = []
    for kind in ("register", "economic", "tools", "research"):
        item, boundary = _validate_item(kind, *inputs[kind])
        items.append(item)
        boundaries.append(boundary)
    if any(boundary != CANONICAL_BOUNDARY for boundary in boundaries):
        _fail("U7 evidence boundaries are inconsistent")
    deferred = sorted({entry for item in items for entry in item["deferred"]})
    catalog: dict[str, Any] = {
        "schema": CATALOG_SCHEMA,
        "status": "passed",
        "items": items,
        "checks": {
            "schemas_statuses_exact": True,
            "source_hashes_valid": True,
            "report_fingerprints_valid": True,
            "lineage_present": True,
            "boundaries_consistent": True,
            "private_read_only_paper_only": True,
            "no_provider_network_credentials": True,
            "no_mutation_or_live_execution": True,
            "promotion_disabled": True,
        },
        "boundary": dict(CANONICAL_BOUNDARY),
        "deferred": deferred,
        "interpretation": "U7-N, U7-J, U7-K, and U7-L evidence are cataloged without deployment, generated-tool execution, provider access, or live-readiness claims.",
        "next_gate": "Select the next bounded local U7 evaluation/evidence product; U5.5 remains gated on owner VM/access.",
    }
    catalog["catalog_fingerprint"] = _fingerprint(catalog)
    return catalog


def _read_input(path: str | Path, label: str) -> tuple[Mapping[str, Any], str, str]:
    source = Path(path)
    try:
        raw = source.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _fail(f"cannot read {label}: {exc}")
    return _object(payload, label), source.name, _source_sha256(raw)


def build_catalog_from_files(paths: Mapping[str, str | Path]) -> dict[str, Any]:
    if set(paths) != set(_EXPECTED):
        _fail("evidence catalog requires register, economic, tools, and research paths")
    inputs = {kind: _read_input(paths[kind], f"{_EXPECTED[kind]['milestone']} evidence") for kind in _EXPECTED}
    return build_catalog(inputs)


def render_markdown(catalog: Mapping[str, Any]) -> str:
    items = [
        f"| {item['milestone']} | `{item['schema']}` | {item['status']} | `{item['source_sha256']}` |"
        for item in catalog["items"]
    ]
    checks = [f"| {key} | {'PASS' if value else 'FAIL'} |" for key, value in catalog["checks"].items()]
    boundary = [f"| {key} | {value} |" for key, value in catalog["boundary"].items()]
    deferred = "\n".join(f"- {item}" for item in catalog["deferred"])
    return "\n".join([
        "# U7-O Evidence Catalog", "",
        f"- Status: **{catalog['status'].upper()}**",
        f"- Catalog fingerprint: `{catalog['catalog_fingerprint']}`",
        "- Scope: complete local U7 evidence surface through U7-N/J/K/L", "",
        "## Evidence items", "", "| Milestone | Schema | Status | Evidence SHA-256 |", "| --- | --- | --- | --- |",
        *items, "", "## Catalog checks", "", "| Check | Result |", "| --- | --- |", *checks,
        "", "## Shared boundary", "", "| Boundary | Value |", "| --- | --- |", *boundary,
        "", "## Deferred gates", "", deferred, "", catalog["interpretation"], "",
    ])


def render_catalog(paths: Mapping[str, str | Path], *, markdown_path: str | Path, json_path: str | Path) -> dict[str, Any]:
    catalog = build_catalog_from_files(paths)
    markdown = Path(markdown_path)
    output = Path(json_path)
    markdown.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text(render_markdown(catalog), encoding="utf-8", newline="\n")
    output.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the U7-O evidence catalog")
    parser.add_argument("--register", required=True)
    parser.add_argument("--economic", required=True)
    parser.add_argument("--tools", required=True)
    parser.add_argument("--research", required=True)
    parser.add_argument("--markdown", required=True)
    parser.add_argument("--json", dest="json_path", required=True)
    args = parser.parse_args(argv)
    try:
        catalog = render_catalog(
            {
                "register": args.register,
                "economic": args.economic,
                "tools": args.tools,
                "research": args.research,
            },
            markdown_path=args.markdown,
            json_path=args.json_path,
        )
    except (OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"schema": catalog["schema"], "status": catalog["status"], "catalog_fingerprint": catalog["catalog_fingerprint"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CATALOG_SCHEMA",
    "CANONICAL_BOUNDARY",
    "EvidenceCatalogError",
    "build_catalog",
    "build_catalog_from_files",
    "main",
    "render_catalog",
    "render_markdown",
]
