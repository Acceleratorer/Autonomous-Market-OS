from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from market_os import cli
from market_os.tool_registry_report import (
    REPORT_SCHEMA,
    ToolRegistryReportError,
    build_tool_registry_report,
    render_tool_registry_report,
)


FIXTURE = Path(__file__).parent / "fixtures" / "tools" / "u7_k_cli_anything_registry.json"


def _write_fixture(path: Path, payload: dict) -> None:
    body = {key: value for key, value in payload.items() if key != "fixture_fingerprint"}
    payload["fixture_fingerprint"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_u7_k_audit_is_stable_and_blocks_external_tools() -> None:
    first = build_tool_registry_report(FIXTURE)
    second = build_tool_registry_report(FIXTURE)

    assert first == second
    assert first["schema"] == REPORT_SCHEMA
    assert first["status"] == "passed"
    assert first["summary"] == {
        "tool_count": 3,
        "enabled_tool_count": 2,
        "deferred_tool_count": 1,
        "blocked_capabilities": {"mutate": 1, "network": 1},
        "execution_count": 0,
    }
    assert first["checks"]["enabled_sandbox_safe"] is True
    assert first["checks"]["deferred_tools_blocked"] is True
    assert first["boundary"] == {
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
    assert first["source_reference"]["repository"] == "CLI-Anything"
    assert first["source_reference"]["imported_runtime"] is False


def test_u7_k_rejects_tampered_fixture(tmp_path: Path) -> None:
    payload = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
    payload["tools"][0]["entry_point"] = ["market-os", ";", "unsafe"]
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ToolRegistryReportError, match="fingerprint mismatch"):
        build_tool_registry_report(path)


def test_u7_k_rejects_unsafe_enabled_tool_with_recomputed_fingerprint(tmp_path: Path) -> None:
    payload = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
    payload["tools"][0]["capabilities"] = ["execute"]
    path = tmp_path / "unsafe.json"
    _write_fixture(path, payload)

    with pytest.raises(ToolRegistryReportError, match="exceed the allowlist"):
        build_tool_registry_report(path)


def test_u7_k_render_and_cli_write_json_and_markdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    report = render_tool_registry_report(
        FIXTURE,
        markdown_path=tmp_path / "direct.md",
        json_path=tmp_path / "direct.json",
    )
    assert json.loads((tmp_path / "direct.json").read_text(encoding="utf-8")) == report
    assert (tmp_path / "direct.md").read_text(encoding="utf-8").startswith("# U7-K CLI Tool Registry Audit")

    assert cli.main([
        "tools",
        "report",
        "--fixture",
        str(FIXTURE),
        "--markdown",
        str(tmp_path / "cli.md"),
        "--json",
        str(tmp_path / "cli.json"),
    ]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["schema"] == REPORT_SCHEMA
    assert json.loads((tmp_path / "cli.json").read_text(encoding="utf-8"))["report_fingerprint"] == report["report_fingerprint"]
