from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from market_os.u8a_readiness import DECISION_SCHEMA, U8AReadinessError, build_decision_from_files, main


ROOT = Path(__file__).resolve().parents[2]
INPUTS = {
    "local_exit": ROOT / "docs" / "evidence" / "local-exit-gate.json",
    "stack": ROOT / "docs" / "evidence" / "u5-5-stack-runtime-review.json",
    "promotion": ROOT / "docs" / "evidence" / "u5-5-promotion-evidence.json",
    "browser": ROOT / "docs" / "evidence" / "u5-5-connected-browser-smoke.json",
    "release": ROOT / "docs" / "evidence" / "u6-4-release-hardening.json",
    "u7": ROOT / "docs" / "evidence" / "u7-o-evidence-catalog.json",
}


def _copy_inputs(tmp_path: Path) -> dict[str, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    copied: dict[str, Path] = {}
    for kind, source in INPUTS.items():
        destination = tmp_path / f"{kind}.json"
        destination.write_bytes(source.read_bytes())
        copied[kind] = destination
    return copied


def _rewrite(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_u8a_happy_path_is_gated_and_preserves_paper_boundary() -> None:
    report = build_decision_from_files(INPUTS)

    assert report["schema"] == DECISION_SCHEMA
    assert report["status"] == "gated"
    assert report["decision"]["classification"] == "local_preflight_passed_connected_runtime_not_verified"
    assert report["decision"]["paper_only_default"] is True
    assert report["decision"]["execution_boundary_change"] is False
    assert all(report["local_checks"].values())
    assert all(gate["status"] == "blocked" for gate in report["external_gates"].values())
    assert report["boundary"]["read_only"] is True
    assert report["boundary"]["mutation_routes"] is False
    assert report["boundary"]["live_execution"] is False
    assert len(report["decision_fingerprint"]) == 64


def test_u8a_rejects_unsafe_promotion_boundary(tmp_path: Path) -> None:
    paths = _copy_inputs(tmp_path)
    payload = copy.deepcopy(json.loads(paths["promotion"].read_text(encoding="utf-8")))
    payload["promotion_boundary"]["enabled"] = True
    _rewrite(paths["promotion"], payload)

    with pytest.raises(U8AReadinessError, match="promotion boundary is unsafe"):
        build_decision_from_files(paths)


def test_u8a_rejects_owner_vm_checks_marked_passed(tmp_path: Path) -> None:
    paths = _copy_inputs(tmp_path)
    payload = copy.deepcopy(json.loads(paths["promotion"].read_text(encoding="utf-8")))
    payload["checks"]["owner_vm_health"]["status"] = "validated"
    _rewrite(paths["promotion"], payload)

    with pytest.raises(U8AReadinessError, match="owner_vm_health must remain not_run"):
        build_decision_from_files(paths)


def test_u8a_fingerprint_is_line_ending_stable(tmp_path: Path) -> None:
    lf_paths = _copy_inputs(tmp_path / "lf")
    expected = build_decision_from_files(lf_paths)
    crlf_paths: dict[str, Path] = {}
    for kind, source in lf_paths.items():
        destination = tmp_path / "crlf" / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n").replace(b"\n", b"\r\n"))
        crlf_paths[kind] = destination

    actual = build_decision_from_files(crlf_paths)
    assert actual["decision_fingerprint"] == expected["decision_fingerprint"]
    assert [item["source_sha256"] for item in actual["items"]] == [item["source_sha256"] for item in expected["items"]]


def test_u8a_cli_writes_json_and_markdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output_json = tmp_path / "decision.json"
    output_markdown = tmp_path / "decision.md"
    assert main(
        [
            "--local-exit",
            str(INPUTS["local_exit"]),
            "--stack",
            str(INPUTS["stack"]),
            "--promotion",
            str(INPUTS["promotion"]),
            "--browser",
            str(INPUTS["browser"]),
            "--release",
            str(INPUTS["release"]),
            "--u7",
            str(INPUTS["u7"]),
            "--markdown",
            str(output_markdown),
            "--json",
            str(output_json),
        ]
    ) == 0

    summary = json.loads(capsys.readouterr().out)
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["schema"] == DECISION_SCHEMA
    assert summary["decision_fingerprint"] == report["decision_fingerprint"]
    assert output_markdown.read_text(encoding="utf-8").startswith("# U8-A Live-Readiness Decision Pack")
