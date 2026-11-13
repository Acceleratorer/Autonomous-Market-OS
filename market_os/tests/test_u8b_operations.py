from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from market_os.u8b_operations import OPERATIONS_SCHEMA, U8BOperationsError, build_operations_from_files, main


ROOT = Path(__file__).resolve().parents[2]
INPUTS = {
    "observability": ROOT / "docs" / "evidence" / "u5-3-deployment-access-observability.json",
    "retention": ROOT / "docs" / "evidence" / "b4-20-retention-archive-preflight.json",
    "platform": ROOT / "docs" / "evidence" / "platform-toolchain-readiness.json",
    "release": ROOT / "docs" / "evidence" / "u6-4-release-hardening.json",
    "u8a": ROOT / "docs" / "evidence" / "u8-a-live-readiness-decision.json",
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


def test_u8b_happy_path_is_gated_and_preserves_boundary() -> None:
    report = build_operations_from_files(INPUTS)

    assert report["schema"] == OPERATIONS_SCHEMA
    assert report["status"] == "gated"
    assert report["classification"] == "local_operational_controls_passed_production_operations_not_verified"
    assert report["paper_only_default"] is True
    assert report["execution_boundary_change"] is False
    assert all(report["local_checks"].values())
    assert all(entry["status"] == "blocked" for entry in report["external_gates"].values())
    assert report["boundary"]["read_only"] is True
    assert report["boundary"]["mutation_routes"] is False
    assert report["boundary"]["live_execution"] is False
    assert len(report["operations_fingerprint"]) == 64


def test_u8b_rejects_public_observability_deployment(tmp_path: Path) -> None:
    paths = _copy_inputs(tmp_path)
    payload = copy.deepcopy(json.loads(paths["observability"].read_text(encoding="utf-8")))
    payload["static_handoff"]["public_deployment"] = True
    _rewrite(paths["observability"], payload)

    with pytest.raises(U8BOperationsError, match="public_deployment is unsafe"):
        build_operations_from_files(paths)


def test_u8b_rejects_retention_deletion(tmp_path: Path) -> None:
    paths = _copy_inputs(tmp_path)
    payload = copy.deepcopy(json.loads(paths["retention"].read_text(encoding="utf-8")))
    payload["policy"]["deletion"] = True
    _rewrite(paths["retention"], payload)

    with pytest.raises(U8BOperationsError, match="retention policy deletion is unsafe"):
        build_operations_from_files(paths)


def test_u8b_rejects_u8a_boundary_change(tmp_path: Path) -> None:
    paths = _copy_inputs(tmp_path)
    payload = copy.deepcopy(json.loads(paths["u8a"].read_text(encoding="utf-8")))
    payload["decision"]["execution_boundary_change"] = True
    _rewrite(paths["u8a"], payload)

    with pytest.raises(U8BOperationsError, match="U8-A decision execution_boundary_change is unsafe"):
        build_operations_from_files(paths)


def test_u8b_fingerprint_is_line_ending_stable(tmp_path: Path) -> None:
    lf_paths = _copy_inputs(tmp_path / "lf")
    expected = build_operations_from_files(lf_paths)
    crlf_paths: dict[str, Path] = {}
    for kind, source in lf_paths.items():
        destination = tmp_path / "crlf" / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n").replace(b"\n", b"\r\n"))
        crlf_paths[kind] = destination

    actual = build_operations_from_files(crlf_paths)
    assert actual["operations_fingerprint"] == expected["operations_fingerprint"]
    assert [item["source_sha256"] for item in actual["items"]] == [item["source_sha256"] for item in expected["items"]]


def test_u8b_cli_writes_json_and_markdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output_json = tmp_path / "operations.json"
    output_markdown = tmp_path / "operations.md"
    assert main(
        [
            "--observability",
            str(INPUTS["observability"]),
            "--retention",
            str(INPUTS["retention"]),
            "--platform",
            str(INPUTS["platform"]),
            "--release",
            str(INPUTS["release"]),
            "--u8-a",
            str(INPUTS["u8a"]),
            "--markdown",
            str(output_markdown),
            "--json",
            str(output_json),
        ]
    ) == 0

    summary = json.loads(capsys.readouterr().out)
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["schema"] == OPERATIONS_SCHEMA
    assert summary["operations_fingerprint"] == report["operations_fingerprint"]
    assert output_markdown.read_text(encoding="utf-8").startswith("# U8-B Local Operational Readiness")
