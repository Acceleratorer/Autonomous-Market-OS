from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from market_os.u8c_paper_mode import PAPER_MODE_SCHEMA, U8CPaperModeError, build_paper_mode_from_files, main


ROOT = Path(__file__).resolve().parents[2]
INPUTS = {
    "u8a": ROOT / "docs" / "evidence" / "u8-a-live-readiness-decision.json",
    "u8b": ROOT / "docs" / "evidence" / "u8-b-local-operational-readiness.json",
}


def _copy_inputs(tmp_path: Path) -> dict[str, Path]:
    copied: dict[str, Path] = {}
    for kind, source in INPUTS.items():
        destination = tmp_path / f"{kind}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        copied[kind] = destination
    return copied


def _rewrite(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_u8c_accepts_permanent_paper_only_decision() -> None:
    report = build_paper_mode_from_files(INPUTS)

    assert report["schema"] == PAPER_MODE_SCHEMA
    assert report["status"] == "accepted"
    assert report["classification"] == "permanent_paper_only_by_owner_decision"
    assert report["decision"]["paper_only_permanent"] is True
    assert report["decision"]["execution_boundary_change"] is False
    assert all(report["checks"].values())
    assert report["boundary"]["read_only"] is True
    assert report["boundary"]["mutation_routes"] is False
    assert report["boundary"]["live_execution"] is False
    assert len(report["decision_fingerprint"]) == 64


def test_u8c_rejects_non_permanent_decision() -> None:
    with pytest.raises(U8CPaperModeError, match="only accepts the permanent-paper-only decision"):
        build_paper_mode_from_files(INPUTS, decision="continue-live-readiness")


def test_u8c_rejects_unblocked_u8a_gate(tmp_path: Path) -> None:
    paths = _copy_inputs(tmp_path)
    payload = copy.deepcopy(json.loads(paths["u8a"].read_text(encoding="utf-8")))
    payload["external_gates"]["owner_vm_access"]["status"] = "passed"
    _rewrite(paths["u8a"], payload)

    with pytest.raises(U8CPaperModeError, match="U8-A external gates are not blocked"):
        build_paper_mode_from_files(paths)


def test_u8c_rejects_changed_boundary(tmp_path: Path) -> None:
    paths = _copy_inputs(tmp_path)
    payload = copy.deepcopy(json.loads(paths["u8b"].read_text(encoding="utf-8")))
    payload["boundary"]["paper_only"] = False
    _rewrite(paths["u8b"], payload)

    with pytest.raises(U8CPaperModeError, match="U8-B boundary paper_only is unsafe"):
        build_paper_mode_from_files(paths)


def test_u8c_fingerprint_is_line_ending_stable(tmp_path: Path) -> None:
    lf_paths = _copy_inputs(tmp_path / "lf")
    expected = build_paper_mode_from_files(lf_paths)
    crlf_paths: dict[str, Path] = {}
    for kind, source in lf_paths.items():
        destination = tmp_path / "crlf" / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        crlf_paths[kind] = destination

    actual = build_paper_mode_from_files(crlf_paths)
    assert actual["decision_fingerprint"] == expected["decision_fingerprint"]
    assert [item["source_sha256"] for item in actual["items"]] == [item["source_sha256"] for item in expected["items"]]


def test_u8c_cli_writes_json_and_markdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output_json = tmp_path / "paper-mode.json"
    output_markdown = tmp_path / "paper-mode.md"
    assert main(
        [
            "--u8-a",
            str(INPUTS["u8a"]),
            "--u8-b",
            str(INPUTS["u8b"]),
            "--decision",
            "permanent-paper-only",
            "--markdown",
            str(output_markdown),
            "--json",
            str(output_json),
        ]
    ) == 0

    summary = json.loads(capsys.readouterr().out)
    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["schema"] == PAPER_MODE_SCHEMA
    assert summary["decision_fingerprint"] == report["decision_fingerprint"]
    assert output_markdown.read_text(encoding="utf-8").startswith("# U8-C Permanent Paper-Only Decision")
