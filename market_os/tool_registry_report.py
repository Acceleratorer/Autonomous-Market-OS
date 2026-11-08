"""Deterministic, read-only audit of a typed CLI tool registry fixture."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


FIXTURE_SCHEMA = "market-os.u7-k.cli-tool-registry-fixture@v1"
REPORT_SCHEMA = "market-os.u7-k-cli-tool-registry-report@v1"
INTERPRETATION = "synthetic tool registry audit only; no tool execution or live capability claim"
SOURCE_REFERENCE = {
    "repository": "CLI-Anything",
    "commit": "34f519533bc175d2fe287ab8316b0dd99bb9cc43",
    "path": "registry.json",
    "source_sha256": "daf5393852daf8db79ed4ea0b9cb0f20109fd512f69c9a911944ee1ec6e469ef",
    "semantic_source": "cli-anything-plugin/commands/list.md",
    "imported_runtime": False,
}
_SAFE_SANDBOX = {
    "read_only": True,
    "network_access": False,
    "credentials": False,
    "mutation_routes": False,
    "live_execution": False,
}
_BOUNDARY = {
    "private": True,
    "synthetic_only": True,
    "paper_only": True,
    "read_only": True,
    "network_access": False,
    "provider_requests": 0,
    "credentials": False,
    "mutation_routes": False,
    "live_execution": False,
    "generated_cli_execution": False,
}
_SHELL_TOKENS = frozenset(";&|<>`$(){}[]\n\r")


class ToolRegistryReportError(ValueError):
    """Raised when a tool registry fixture is unsafe or malformed."""


def _fail(message: str) -> None:
    raise ToolRegistryReportError(message)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{field} must be an object")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{field} must be a non-empty string")
    return value


def _text_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        _fail(f"{field} must be a non-empty list")
    result = [_text(item, f"{field}[{index}]") for index, item in enumerate(value)]
    return result


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        _fail(f"{field} must be a boolean")
    return value


def _validate_tool(tool: Mapping[str, Any], index: int, allowed: set[str], denied: set[str]) -> dict[str, Any]:
    prefix = f"tools[{index}]"
    name = _text(tool.get("name"), f"{prefix}.name")
    display_name = _text(tool.get("display_name"), f"{prefix}.display_name")
    version = _text(tool.get("version"), f"{prefix}.version")
    category = _text(tool.get("category"), f"{prefix}.category")
    status = tool.get("status")
    if status not in {"enabled", "deferred"}:
        _fail(f"{prefix}.status is invalid")
    entry_point = _text_list(tool.get("entry_point"), f"{prefix}.entry_point")
    if any(any(token in part for token in _SHELL_TOKENS) for part in entry_point):
        _fail(f"{prefix}.entry_point contains shell metacharacters")
    capabilities = set(_text_list(tool.get("capabilities"), f"{prefix}.capabilities"))
    if status == "enabled" and not capabilities <= allowed:
        _fail(f"{prefix}.capabilities exceed the allowlist")
    if not capabilities <= allowed | denied:
        _fail(f"{prefix}.capabilities contain unknown values")
    requires = tool.get("requires")
    if not isinstance(requires, list) or any(not isinstance(item, str) or not item.strip() for item in requires):
        _fail(f"{prefix}.requires must be a list of strings")
    sandbox = _mapping(tool.get("sandbox"), f"{prefix}.sandbox")
    for key, expected in _SAFE_SANDBOX.items():
        _bool(sandbox.get(key), f"{prefix}.sandbox.{key}")
        if status == "enabled" and sandbox[key] != expected:
            _fail(f"{prefix}.sandbox.{key} is unsafe")
    execution_enabled = _bool(tool.get("execution_enabled"), f"{prefix}.execution_enabled")
    if execution_enabled:
        _fail(f"{prefix}.execution_enabled must remain false")
    if status == "enabled" and requires:
        _fail(f"{prefix}.enabled tool cannot require external services")
    if status == "deferred":
        _text(tool.get("defer_reason"), f"{prefix}.defer_reason")
    return {
        "name": name,
        "display_name": display_name,
        "version": version,
        "category": category,
        "status": status,
        "entry_point": entry_point,
        "capabilities": sorted(capabilities),
        "requires": list(requires),
        "sandbox": {key: bool(sandbox[key]) for key in _SAFE_SANDBOX},
        "execution_enabled": execution_enabled,
        "defer_reason": tool.get("defer_reason"),
    }


def _load_fixture(path: str | Path) -> tuple[dict[str, Any], str, str]:
    fixture = Path(path)
    try:
        raw = fixture.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _fail(f"cannot read tool registry fixture: {exc}")
    if not isinstance(payload, dict):
        _fail("tool registry fixture must be an object")
    expected = payload.get("fixture_fingerprint")
    body = {key: value for key, value in payload.items() if key != "fixture_fingerprint"}
    actual = _fingerprint(body)
    if expected != actual:
        _fail("tool registry fixture fingerprint mismatch")
    if payload.get("schema") != FIXTURE_SCHEMA or payload.get("synthetic_only") is not True:
        _fail("tool registry fixture schema or boundary is invalid")
    if payload.get("interpretation") != INTERPRETATION:
        _fail("tool registry fixture interpretation is invalid")
    _text(payload.get("fixture_id"), "fixture_id")
    _text(payload.get("label"), "label")
    license_metadata = _mapping(payload.get("license"), "license")
    if license_metadata.get("classification") != "synthetic-internal":
        _fail("tool registry fixture license classification is invalid")
    _text(license_metadata.get("attribution"), "license.attribution")
    if payload.get("source_reference") != SOURCE_REFERENCE:
        _fail("tool registry source reference is invalid")
    allowed = set(_text_list(payload.get("allowed_capabilities"), "allowed_capabilities"))
    denied = set(_text_list(payload.get("denied_capabilities"), "denied_capabilities"))
    if allowed & denied:
        _fail("allowed and denied capabilities overlap")
    tools = payload.get("tools")
    if not isinstance(tools, list) or not tools:
        _fail("tools must be a non-empty list")
    normalized = [_validate_tool(_mapping(tool, f"tools[{index}]"), index, allowed, denied) for index, tool in enumerate(tools)]
    names = [tool["name"] for tool in normalized]
    if len(names) != len(set(names)):
        _fail("tool names must be unique")
    payload["_normalized_tools"] = normalized
    return payload, actual, hashlib.sha256(raw).hexdigest()


def build_tool_registry_report(path: str | Path) -> dict[str, Any]:
    """Validate a typed registry and return a deterministic local audit."""
    fixture, fixture_fingerprint, source_sha256 = _load_fixture(path)
    normalized = fixture.pop("_normalized_tools")
    allowed = sorted(str(value) for value in fixture["allowed_capabilities"])
    denied = sorted(str(value) for value in fixture["denied_capabilities"])
    deferred = [tool for tool in normalized if tool["status"] == "deferred"]
    enabled = [tool for tool in normalized if tool["status"] == "enabled"]
    blocked_capabilities = Counter(
        capability
        for tool in deferred
        for capability in tool["capabilities"]
        if capability in denied
    )
    report = {
        "schema": REPORT_SCHEMA,
        "status": "passed",
        "fixture": {
            "fixture_id": fixture["fixture_id"],
            "label": fixture["label"],
            "schema": fixture["schema"],
            "fixture_fingerprint": fixture_fingerprint,
            "source_sha256": source_sha256,
            "tool_count": len(normalized),
        },
        "source_reference": dict(SOURCE_REFERENCE),
        "registry": {
            "allowed_capabilities": allowed,
            "denied_capabilities": denied,
            "tools": normalized,
        },
        "summary": {
            "tool_count": len(normalized),
            "enabled_tool_count": len(enabled),
            "deferred_tool_count": len(deferred),
            "blocked_capabilities": dict(sorted(blocked_capabilities.items())),
            "execution_count": 0,
        },
        "checks": {
            "fixture_valid": True,
            "tool_names_unique": True,
            "typed_entry_points": True,
            "shell_metacharacters_rejected": True,
            "enabled_capabilities_allowlisted": True,
            "enabled_sandbox_safe": True,
            "deferred_tools_blocked": all(not tool["execution_enabled"] for tool in deferred),
            "deterministic_replay": True,
            "synthetic_boundary": True,
            "execution_disabled": True,
        },
        "boundary": dict(_BOUNDARY),
        "promotion": {
            "approved": False,
            "status": "Not ready — registry audit only",
            "reasons": [
                "generated CLI runtimes are not imported or executed",
                "external services and mutation capabilities remain deferred",
            ],
        },
        "interpretation": INTERPRETATION,
        "deferred": [
            "generated CLI execution",
            "external services",
            "credentials",
            "network access",
            "mutation routes",
            "live execution",
        ],
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report


def _display(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def render_markdown(report: Mapping[str, Any]) -> str:
    rows = [
        f"| {tool['name']} | {tool['status']} | {', '.join(tool['capabilities'])} | {tool['execution_enabled']} |"
        for tool in report["registry"]["tools"]
    ]
    return "\n".join([
        "# U7-K CLI Tool Registry Audit", "",
        f"- Status: **{str(report['status']).upper()}**",
        f"- Fixture fingerprint: `{report['fixture']['fixture_fingerprint']}`",
        f"- Tools: **{report['summary']['tool_count']}** ({report['summary']['enabled_tool_count']} enabled, {report['summary']['deferred_tool_count']} deferred)",
        f"- Promotion approved: **{report['promotion']['approved']}**", "",
        "## Registry", "", "| Tool | Status | Capabilities | Execution enabled |", "| --- | --- | --- | --- |", *rows, "",
        "## Boundary", "", "| Boundary | Value |", "| --- | --- |",
        *[f"| {key} | {_display(value)} |" for key, value in report["boundary"].items()], "",
        report["interpretation"], "",
    ])


def render_tool_registry_report(
    fixture_path: str | Path,
    *,
    markdown_path: str | Path,
    json_path: str | Path,
) -> dict[str, Any]:
    report = build_tool_registry_report(fixture_path)
    markdown = Path(markdown_path)
    output = Path(json_path)
    markdown.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text(render_markdown(report), encoding="utf-8")
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a U7-K CLI tool registry audit")
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--markdown", required=True)
    parser.add_argument("--json", dest="json_path", required=True)
    args = parser.parse_args(argv)
    try:
        report = render_tool_registry_report(
            args.fixture,
            markdown_path=args.markdown,
            json_path=args.json_path,
        )
    except (OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"schema": report["schema"], "status": report["status"], "report_fingerprint": report["report_fingerprint"]}, sort_keys=True))
    return 0


__all__ = [
    "FIXTURE_SCHEMA",
    "INTERPRETATION",
    "REPORT_SCHEMA",
    "SOURCE_REFERENCE",
    "ToolRegistryReportError",
    "build_tool_registry_report",
    "main",
    "render_markdown",
    "render_tool_registry_report",
]


if __name__ == "__main__":
    raise SystemExit(main())
