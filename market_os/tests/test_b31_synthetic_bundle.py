from __future__ import annotations

import json

import pytest

from market_os.b31_offline import DatasetRow, OfflineEvaluationPlan, compile_synthetic_evaluation_plan, materialize_synthetic_evaluation_plan
from market_os.b31_synthetic_bundle import (
    BUNDLE_SCHEMA,
    create_synthetic_artifact_bundle,
    load_synthetic_artifact_bundle,
    write_synthetic_artifact_bundle,
)
from market_os.b31_synthetic_reporting import build_synthetic_stability_report
from market_os.b31_synthetic_runner import build_synthetic_outcome, build_synthetic_row, run_synthetic_evaluation


def _artifacts():
    duration = 1_200_000
    plan = OfflineEvaluationPlan()
    compilation = compile_synthetic_evaluation_plan(plan, synthetic_start_ms=0, block_duration_ms=duration)
    rows = []
    material_rows = []
    outcomes = []
    for block_id in range(1, 11):
        start = (block_id - 1) * duration
        for offset, label in ((600_000, True), (660_000, False)):
            row_id = f"synthetic-b{block_id}-{offset}"
            feature = f"{block_id * 100 + offset:064x}"
            available = block_id != 10
            rows.append(build_synthetic_row(row_id=row_id, timestamp_ms=start + offset, feature_fingerprint=feature, numerical_score=0.2 if label else 0.8, target_available=available, assessment_status="missing"))
            material_rows.append(DatasetRow(start + offset, feature, start + offset + 300_000, label) if available else DatasetRow(start + offset, feature))
            if available:
                outcomes.append(build_synthetic_outcome(row_id, label))
    materialization = materialize_synthetic_evaluation_plan(compilation, material_rows)
    report = run_synthetic_evaluation(plan, compilation, materialization, rows, outcomes)
    return report, build_synthetic_stability_report(report)


def test_bundle_round_trip_is_canonical_and_deterministic(tmp_path) -> None:
    report, stability = _artifacts()
    first = create_synthetic_artifact_bundle(report, stability)
    second = create_synthetic_artifact_bundle(report, stability)
    assert first.fingerprint == second.fingerprint
    assert first.to_dict()["schema"] == BUNDLE_SCHEMA
    path = tmp_path / "bundle.json"
    write_synthetic_artifact_bundle(first, path)
    loaded = load_synthetic_artifact_bundle(path)
    assert loaded.to_dict() == first.to_dict()
    assert path.read_text(encoding="utf-8") == json.dumps(first.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"


def test_bundle_rejects_tampering_and_cross_artifact_mismatch(tmp_path) -> None:
    report, stability = _artifacts()
    bundle = create_synthetic_artifact_bundle(report, stability).to_dict()
    path = tmp_path / "tampered.json"
    bundle["artifacts"]["evaluation_report"]["interpretation"] = "changed"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        load_synthetic_artifact_bundle(path)
    report, stability = _artifacts()
    mismatch = create_synthetic_artifact_bundle(report, stability).to_dict()
    mismatch["artifacts"]["stability_report"]["source_fingerprint"] = "0" * 64
    path.write_text(json.dumps(mismatch), encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint mismatch|source fingerprint"):
        load_synthetic_artifact_bundle(path)


def test_bundle_rejects_unknown_schema_external_identity_and_self_reference(tmp_path) -> None:
    report, stability = _artifacts()
    bundle = create_synthetic_artifact_bundle(report, stability).to_dict()
    path = tmp_path / "invalid.json"
    bundle["schema"] = "market-os.b3-1.synthetic-artifact-bundle@v999"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    with pytest.raises(ValueError, match="schema or version"):
        load_synthetic_artifact_bundle(path)
    bundle = create_synthetic_artifact_bundle(report, stability).to_dict()
    bundle["artifacts"]["evaluation_report"]["external_ref"] = "https://example.invalid"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint mismatch|forbidden external"):
        load_synthetic_artifact_bundle(path)
    bundle = create_synthetic_artifact_bundle(report, stability).to_dict()
    bundle["bundle_fingerprint"] = bundle["bundle_fingerprint"]
    bundle["artifacts"]["evaluation_report"]["bundle_fingerprint"] = bundle["bundle_fingerprint"]
    path.write_text(json.dumps(bundle), encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint mismatch|forbidden"):
        load_synthetic_artifact_bundle(path)
