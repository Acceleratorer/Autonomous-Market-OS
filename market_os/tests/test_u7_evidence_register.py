from __future__ import annotations

import json
from pathlib import Path

import pytest

from market_os.u7_evidence_register import EvidenceRegisterError, build_register_from_files


ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "docs" / "evidence" / "u7-i-local-evidence-pack.json"
DRIFT = ROOT / "docs" / "evidence" / "u7-m-release-evidence-drift.json"


def _copy_json(source: Path, destination: Path, mutate) -> Path:
    payload = json.loads(source.read_text(encoding="utf-8"))
    mutate(payload)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return destination


def test_u7_n_register_passes_committed_u7_i_and_hosted_u7_m() -> None:
    register = build_register_from_files(PACK, DRIFT)

    assert register["schema"] == "market-os.u7-n-unified-evidence-register@v1"
    assert register["status"] == "passed"
    assert register["checks"]["boundaries_consistent"] is True
    assert register["items"][1]["status"] == "ci-verified"
    assert len(register["register_fingerprint"]) == 64


def test_u7_n_register_fails_on_boundary_drift(tmp_path: Path) -> None:
    drift = _copy_json(DRIFT, tmp_path / "drift.json", lambda payload: payload["boundary"].update({"read_only": False}))

    with pytest.raises(EvidenceRegisterError, match="boundary"):
        build_register_from_files(PACK, drift)


def test_u7_n_register_fails_on_nonzero_drift_count(tmp_path: Path) -> None:
    drift = _copy_json(DRIFT, tmp_path / "drift.json", lambda payload: payload.update({"drift": [{"code": "unsafe"}], "drift_count": 1}))

    with pytest.raises(EvidenceRegisterError, match="drift report"):
        build_register_from_files(PACK, drift)


def test_u7_n_register_fails_on_invalid_input_schema(tmp_path: Path) -> None:
    pack = _copy_json(PACK, tmp_path / "pack.json", lambda payload: payload.update({"status": "failed"}))

    with pytest.raises(EvidenceRegisterError, match="status"):
        build_register_from_files(pack, DRIFT)


def test_u7_n_register_fingerprint_is_line_ending_independent(tmp_path: Path) -> None:
    pack_path = tmp_path / "pack" / PACK.name
    drift_path = tmp_path / "drift" / DRIFT.name
    for source, destination in ((PACK, pack_path), (DRIFT, drift_path)):
        destination.parent.mkdir(parents=True, exist_ok=True)
        normalized = source.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        destination.write_bytes(normalized.replace(b"\n", b"\r\n"))

    expected = build_register_from_files(PACK, DRIFT)
    actual = build_register_from_files(pack_path, drift_path)

    assert actual["register_fingerprint"] == expected["register_fingerprint"]
