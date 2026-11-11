from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from market_os import cli
from market_os.synthetic_economic_report import (
    REPORT_SCHEMA,
    SyntheticEconomicReportError,
    build_synthetic_economic_report,
    render_synthetic_economic_report,
)


FIXTURE = Path(__file__).parent / "fixtures" / "economic" / "u7_j_synthetic_economic.json"


def test_u7_j_is_stable_and_applies_quality_threshold() -> None:
    first = build_synthetic_economic_report(FIXTURE)
    second = build_synthetic_economic_report(FIXTURE)

    assert first == second
    assert first["schema"] == REPORT_SCHEMA
    assert first["status"] == "passed"
    assert first["economics"]["tasks_paid"] == 1
    assert first["economics"]["tasks_rejected"] == 1
    assert first["economics"]["total_income_usd"] == 3.0
    assert first["economics"]["net_usd"] == 2.957485
    assert first["economics"]["total_costs_usd"] == {
        "llm_tokens": 0.0225,
        "search_api": 0.000015,
        "ocr_api": 0.02,
        "other_api": 0.0,
        "total": 0.042515,
    }
    assert first["boundary"]["network_access"] is False
    assert first["promotion"]["approved"] is False
    assert first["boundary"]["private"] is True
    assert first["source_reference"]["repository"] == "ClawWork"
    assert first["source_reference"]["imported_runtime"] is False


def test_u7_j_source_hash_is_line_ending_independent(tmp_path: Path) -> None:
    windows_fixture = tmp_path / FIXTURE.name
    normalized = FIXTURE.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    windows_fixture.write_bytes(normalized.replace(b"\n", b"\r\n"))

    assert build_synthetic_economic_report(windows_fixture) == build_synthetic_economic_report(FIXTURE)


def test_u7_j_rejects_tampered_fixture(tmp_path: Path) -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload = copy.deepcopy(payload)
    payload["tasks"][0]["base_payment_usd"] = 99.0
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SyntheticEconomicReportError, match="fingerprint mismatch"):
        build_synthetic_economic_report(path)


def test_u7_j_rejects_unsafe_license_even_with_recomputed_fingerprint(tmp_path: Path) -> None:
    payload = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
    payload["license"]["classification"] = "public"
    body = {key: value for key, value in payload.items() if key != "fixture_fingerprint"}
    payload["fixture_fingerprint"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    path = tmp_path / "unsafe-license.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SyntheticEconomicReportError, match="license classification"):
        build_synthetic_economic_report(path)


def test_u7_j_render_and_cli_write_json_and_markdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    report = render_synthetic_economic_report(
        FIXTURE,
        markdown_path=tmp_path / "direct.md",
        json_path=tmp_path / "direct.json",
    )
    assert json.loads((tmp_path / "direct.json").read_text(encoding="utf-8")) == report
    assert (tmp_path / "direct.md").read_text(encoding="utf-8").startswith("# U7-J Synthetic Economic Report")

    assert cli.main([
        "synthetic",
        "economic-report",
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
