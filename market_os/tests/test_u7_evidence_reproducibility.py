from __future__ import annotations

import json
from pathlib import Path

from market_os.cli import main as cli_main
from market_os.u7_evidence_reproducibility import REPRODUCIBILITY_SCHEMA, build_reproducibility_report, main


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "docs" / "evidence" / "u7-o-evidence-catalog.json"
PACK = ROOT / "docs" / "evidence" / "u7-i-local-evidence-pack.json"
DRIFT = ROOT / "docs" / "evidence" / "u7-m-release-evidence-drift.json"
ECONOMIC = ROOT / "market_os" / "tests" / "fixtures" / "economic" / "u7_j_synthetic_economic.json"
TOOLS = ROOT / "market_os" / "tests" / "fixtures" / "tools" / "u7_k_cli_anything_registry.json"
RESEARCH = ROOT / "market_os" / "tests" / "fixtures" / "research" / "u7_l_cited_research.json"


def _paths(catalog: Path = CATALOG) -> dict[str, Path]:
    return {
        "catalog": catalog,
        "pack": PACK,
        "drift": DRIFT,
        "economic": ECONOMIC,
        "tools": TOOLS,
        "research": RESEARCH,
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
