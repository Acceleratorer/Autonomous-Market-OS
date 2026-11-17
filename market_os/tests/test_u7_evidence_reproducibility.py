from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path

import pytest

from market_os.cli import main as cli_main
import market_os.u7_evidence_reproducibility as reproducibility
from market_os.u7_evidence_reproducibility import (
    EvidenceReproducibilityError,
    REPRODUCIBILITY_SCHEMA,
    build_reproducibility_report,
    main,
    render_reproducibility_report,
)


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "docs" / "evidence" / "u7-o-evidence-catalog.json"
PACK = ROOT / "docs" / "evidence" / "u7-i-local-evidence-pack.json"
DRIFT = ROOT / "docs" / "evidence" / "u7-m-release-evidence-drift.json"
ECONOMIC = ROOT / "market_os" / "tests" / "fixtures" / "economic" / "u7_j_synthetic_economic.json"
TOOLS = ROOT / "market_os" / "tests" / "fixtures" / "tools" / "u7_k_cli_anything_registry.json"
RESEARCH = ROOT / "market_os" / "tests" / "fixtures" / "research" / "u7_l_cited_research.json"


def _paths(catalog: Path = CATALOG, research: Path = RESEARCH, economic: Path = ECONOMIC) -> dict[str, Path]:
    return {
        "catalog": catalog,
        "pack": PACK,
        "drift": DRIFT,
        "economic": economic,
        "tools": TOOLS,
        "research": research,
    }


def test_u7_p_reproduces_committed_catalog_twice() -> None:
    report = build_reproducibility_report(**_paths())

    assert report["schema"] == REPRODUCIBILITY_SCHEMA
    assert report["status"] == "passed"
    assert all(report["checks"].values())
    assert report["run_catalog_fingerprints"] == [report["committed_catalog_fingerprint"]] * 2
    assert report["boundary"]["paper_only"] is True
    assert report["boundary"]["network_access"] is False


def test_u7_p_reports_catalog_drift_without_writing_sources(tmp_path: Path) -> None:
    mutated = json.loads(CATALOG.read_text(encoding="utf-8"))
    mutated["catalog_fingerprint"] = "0" * 64
    catalog = tmp_path / CATALOG.name
    catalog.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")

    report = build_reproducibility_report(**_paths(catalog))

    assert report["status"] == "failed"
    assert report["checks"]["catalog_fingerprint_match"] is False
    assert "catalog_fingerprint" in report["mismatches"]


def test_u7_p_rejects_type_changed_catalog_boundary(tmp_path: Path) -> None:
    mutated = json.loads(CATALOG.read_text(encoding="utf-8"))
    mutated["boundary"]["paper_only"] = 1
    body = {key: value for key, value in mutated.items() if key != "catalog_fingerprint"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    mutated["catalog_fingerprint"] = hashlib.sha256(canonical).hexdigest()
    catalog = tmp_path / CATALOG.name
    catalog.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")

    report = build_reproducibility_report(**_paths(catalog))

    assert report["status"] == "failed"
    assert report["checks"]["catalog_body_match"] is False
    assert report["checks"]["boundaries_consistent"] is False
    assert "boundary" in report["mismatches"]


def test_u7_p_hashes_the_captured_source_bytes(tmp_path: Path, monkeypatch) -> None:
    economic = tmp_path / ECONOMIC.name
    original_bytes = ECONOMIC.read_bytes()
    economic.write_bytes(original_bytes)
    regenerate = reproducibility._regenerate_catalogs

    def mutate_original_after_capture(pack, drift, economic_snapshot, tools, research):
        economic.write_bytes(b"changed after audit snapshot")
        return regenerate(pack, drift, economic_snapshot, tools, research)

    monkeypatch.setattr(reproducibility, "_regenerate_catalogs", mutate_original_after_capture)

    report = build_reproducibility_report(**_paths(economic=economic))
    economic_hash = next(item["sha256"] for item in report["source_artifacts"] if item["id"] == "economic_fixture")
    normalized = original_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

    assert economic_hash == hashlib.sha256(normalized).hexdigest()


def test_u7_p_rejects_report_paths_that_collide_with_sources_or_each_other(tmp_path: Path) -> None:
    original_catalog = CATALOG.read_bytes()
    same_output = tmp_path / "same-output.txt"

    with pytest.raises(EvidenceReproducibilityError, match="different paths"):
        render_reproducibility_report(
            **_paths(), markdown_path=same_output, json_path=same_output
        )
    with pytest.raises(EvidenceReproducibilityError, match="overwrite source evidence"):
        render_reproducibility_report(
            **_paths(), markdown_path=CATALOG, json_path=tmp_path / "report.json"
        )

    assert CATALOG.read_bytes() == original_catalog


def test_u7_p_failed_publication_restores_both_reports(tmp_path: Path, monkeypatch) -> None:
    markdown = tmp_path / "report.md"
    output = tmp_path / "report.json"
    markdown.write_bytes(b"old markdown")
    output.write_bytes(b"old json")
    real_replace = os.replace
    replace_count = 0

    def fail_second_replace(source, destination):
        nonlocal replace_count
        replace_count += 1
        if replace_count == 2:
            raise OSError("simulated publish failure")
        return real_replace(source, destination)

    monkeypatch.setattr(reproducibility.os, "replace", fail_second_replace)

    with pytest.raises(OSError, match="simulated publish failure"):
        render_reproducibility_report(
            **_paths(), markdown_path=markdown, json_path=output
        )

    assert markdown.read_bytes() == b"old markdown"
    assert output.read_bytes() == b"old json"


def test_u7_p_invalid_research_emits_failed_report_through_both_clis(tmp_path: Path, capsys) -> None:
    invalid = json.loads(RESEARCH.read_text(encoding="utf-8"))
    invalid.pop("coverage", None)
    research = tmp_path / "invalid-research.json"
    research.write_text(json.dumps(invalid), encoding="utf-8")

    for command, prefix in ((main, "module"), (cli_main, "market-os")):
        markdown = tmp_path / f"{prefix}.md"
        output = tmp_path / f"{prefix}.json"
        args = [
            "--catalog", str(CATALOG),
            "--pack", str(PACK),
            "--drift", str(DRIFT),
            "--economic", str(ECONOMIC),
            "--tools", str(TOOLS),
            "--research", str(research),
            "--markdown", str(markdown),
            "--json", str(output),
        ]
        if command is cli_main:
            args = ["u7", "evidence-repro"] + args

        assert command(args) == 1
        result = json.loads(output.read_text(encoding="utf-8"))
        assert result["status"] == "failed"
        assert result["mismatches"] == ["catalog_regeneration"]
        assert result["regeneration_error_type"] == "KeyError"
        assert markdown.exists()


def test_u7_p_cli_writes_json_and_markdown(tmp_path: Path, capsys) -> None:
    output_json = tmp_path / "reproducibility.json"
    output_md = tmp_path / "reproducibility.md"

    assert main([
        "--catalog", str(CATALOG),
        "--pack", str(PACK),
        "--drift", str(DRIFT),
        "--economic", str(ECONOMIC),
        "--tools", str(TOOLS),
        "--research", str(RESEARCH),
        "--markdown", str(output_md),
        "--json", str(output_json),
    ]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["schema"] == REPRODUCIBILITY_SCHEMA
    assert json.loads(output_json.read_text(encoding="utf-8"))["status"] == "passed"
    assert output_md.read_text(encoding="utf-8").startswith("# U7-P Evidence Reproducibility Audit")


def test_u7_p_market_os_cli_writes_json_and_markdown(tmp_path: Path, capsys) -> None:
    output_json = tmp_path / "cli-reproducibility.json"
    output_md = tmp_path / "cli-reproducibility.md"

    assert cli_main([
        "u7", "evidence-repro",
        "--catalog", str(CATALOG),
        "--pack", str(PACK),
        "--drift", str(DRIFT),
        "--economic", str(ECONOMIC),
        "--tools", str(TOOLS),
        "--research", str(RESEARCH),
        "--markdown", str(output_md),
        "--json", str(output_json),
    ]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "passed"
    assert json.loads(output_json.read_text(encoding="utf-8"))["schema"] == REPRODUCIBILITY_SCHEMA
