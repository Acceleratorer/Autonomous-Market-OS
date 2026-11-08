from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from market_os.evidence_pack import (
    PACK_SCHEMA,
    EvidencePackError,
    build_evidence_pack_from_files,
    main,
)


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs" / "evidence"
FILES = {
    "release": EVIDENCE / "u7-f-cross-target-release-catalog-report.json",
    "quality": EVIDENCE / "u7-g-quality-benchmark-report.json",
    "session": EVIDENCE / "u7-h-synthetic-session-accounting-report.json",
}


def test_u7_i_pack_is_stable_and_preserves_shared_boundary() -> None:
    first = build_evidence_pack_from_files(FILES)
    second = build_evidence_pack_from_files(FILES)

    assert first == second
    assert first["schema"] == PACK_SCHEMA
    assert first["status"] == "passed"
    assert first["checks"]["boundaries_consistent"] is True
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
    }
    assert [item["milestone"] for item in first["items"]] == ["U7-F", "U7-G", "U7-H"]


def test_u7_i_rejects_tampered_required_check(tmp_path: Path) -> None:
    paths: dict[str, Path] = {}
    for kind, source in FILES.items():
        payload = json.loads(source.read_text(encoding="utf-8"))
        if kind == "quality":
            payload = copy.deepcopy(payload)
            payload["checks"]["replay_stable"] = False
        path = tmp_path / f"{kind}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths[kind] = path

    with pytest.raises(EvidencePackError, match="quality check replay_stable"):
        build_evidence_pack_from_files(paths)


def test_u7_i_cli_writes_json_and_markdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([
        "--release", str(FILES["release"]),
        "--quality", str(FILES["quality"]),
        "--session", str(FILES["session"]),
        "--markdown", str(tmp_path / "pack.md"),
        "--json", str(tmp_path / "pack.json"),
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["schema"] == PACK_SCHEMA
    assert json.loads((tmp_path / "pack.json").read_text(encoding="utf-8"))["status"] == "passed"
    assert (tmp_path / "pack.md").read_text(encoding="utf-8").startswith("# U7-I Local Evidence Pack")
