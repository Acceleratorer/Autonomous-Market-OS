from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from market_os.research_brief import render_research_brief_files
from market_os.synthetic_economic_report import render_synthetic_economic_report
from market_os.tool_registry_report import render_tool_registry_report
from market_os.u7_evidence_catalog import CATALOG_SCHEMA, EvidenceCatalogError, build_catalog_from_files, main


ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "docs" / "evidence" / "u7-n-unified-evidence-register.json"
ECONOMIC_FIXTURE = ROOT / "market_os" / "tests" / "fixtures" / "economic" / "u7_j_synthetic_economic.json"
TOOLS_FIXTURE = ROOT / "market_os" / "tests" / "fixtures" / "tools" / "u7_k_cli_anything_registry.json"
RESEARCH_FIXTURE = ROOT / "market_os" / "tests" / "fixtures" / "research" / "u7_l_cited_research.json"


def _render_inputs(tmp_path: Path) -> dict[str, Path]:
    economic = tmp_path / "economic.json"
    render_synthetic_economic_report(ECONOMIC_FIXTURE, markdown_path=tmp_path / "economic.md", json_path=economic)
    tools = tmp_path / "tools.json"
    render_tool_registry_report(TOOLS_FIXTURE, markdown_path=tmp_path / "tools.md", json_path=tools)
    research = tmp_path / "research.json"
    render_research_brief_files(RESEARCH_FIXTURE, tmp_path / "research.md", research)
    return {"register": REGISTER, "economic": economic, "tools": tools, "research": research}


def test_u7_o_catalog_is_stable_and_keeps_shared_boundary(tmp_path: Path) -> None:
    first = build_catalog_from_files(_render_inputs(tmp_path))
    second = build_catalog_from_files(_render_inputs(tmp_path))

    assert first == second
    assert first["schema"] == CATALOG_SCHEMA
    assert first["status"] == "passed"
    assert [item["milestone"] for item in first["items"]] == ["U7-N", "U7-J", "U7-K", "U7-L"]
    assert first["checks"]["boundaries_consistent"] is True
    assert first["boundary"]["read_only"] is True
    assert first["boundary"]["network_access"] is False
    assert len(first["catalog_fingerprint"]) == 64


def test_u7_o_rejects_unsafe_boundary(tmp_path: Path) -> None:
    paths = _render_inputs(tmp_path)
    payload = copy.deepcopy(json.loads(paths["tools"].read_text(encoding="utf-8")))
    payload["boundary"]["generated_cli_execution"] = True
    body = {key: value for key, value in payload.items() if key != "report_fingerprint"}
    import hashlib

    payload["report_fingerprint"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    paths["tools"].write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(EvidenceCatalogError, match="generated_cli_execution"):
        build_catalog_from_files(paths)


def test_u7_o_catalog_is_line_ending_independent(tmp_path: Path) -> None:
    paths = _render_inputs(tmp_path / "lf")
    expected = build_catalog_from_files(paths)
    crlf_paths: dict[str, Path] = {}
    for kind, source in paths.items():
        destination = tmp_path / "crlf" / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        normalized = source.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        destination.write_bytes(normalized.replace(b"\n", b"\r\n"))
        crlf_paths[kind] = destination

    actual = build_catalog_from_files(crlf_paths)
    assert actual["catalog_fingerprint"] == expected["catalog_fingerprint"]


def test_u7_o_cli_writes_json_and_markdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    paths = _render_inputs(tmp_path / "inputs")
    output_json = tmp_path / "catalog.json"
    output_md = tmp_path / "catalog.md"
    assert main([
        "--register", str(paths["register"]),
        "--economic", str(paths["economic"]),
        "--tools", str(paths["tools"]),
        "--research", str(paths["research"]),
        "--markdown", str(output_md),
        "--json", str(output_json),
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["schema"] == CATALOG_SCHEMA
    assert json.loads(output_json.read_text(encoding="utf-8"))["status"] == "passed"
    assert output_md.read_text(encoding="utf-8").startswith("# U7-O Evidence Catalog")
