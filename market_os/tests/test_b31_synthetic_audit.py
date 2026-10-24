from __future__ import annotations

from copy import deepcopy

import pytest

from market_os.b31_synthetic_audit import (
    CHECK_FAIL,
    CHECK_PASS,
    GATE_OFFLINE_RESEARCH_EVALUATION,
    GATE_PROVIDER_INTEGRATION,
    GATE_REAL_DATASET_BINDING,
    GATE_SHADOW_STUDY,
    GATE_SYNTHETIC_IMPLEMENTATION,
    audit_synthetic_artifact_bundle,
)
from market_os.b31_synthetic_bundle import SyntheticArtifactBundle, create_synthetic_artifact_bundle
from market_os.tests.test_b31_synthetic_bundle import _artifacts


def _bundle() -> SyntheticArtifactBundle:
    report, stability = _artifacts()
    return create_synthetic_artifact_bundle(report, stability)


def _repack(payload: dict) -> SyntheticArtifactBundle:
    """Recompute the existing bundle's canonical hashes after a test mutation."""
    from market_os.b31_synthetic_bundle import _artifact_projection, _fingerprint
    from market_os.b31_synthetic_runner import RUNNER_SCHEMA
    from market_os.b31_synthetic_reporting import REPORT_SCHEMA

    report = payload["artifacts"]["evaluation_report"]
    report_projection = _artifact_projection(report)
    report_projection.pop("version", None)
    report_projection.pop("status", None)
    row_counts = report_projection.get("row_counts")
    if isinstance(row_counts, dict):
        row_counts = dict(row_counts)
        row_counts.pop("untouched", None)
        report_projection["row_counts"] = row_counts
    report["fingerprint"] = _fingerprint(report_projection)

    stability = payload["artifacts"]["stability_report"]
    stability["source_fingerprint"] = report["fingerprint"]
    stability_projection = _artifact_projection(stability)
    stability_projection.pop("schema", None)
    stability["fingerprint"] = _fingerprint(stability_projection)
    payload["source_fingerprints"] = {
        "evaluation_report": report["fingerprint"],
        "stability_report": stability["fingerprint"],
    }
    projection = dict(payload)
    projection.pop("bundle_fingerprint", None)
    payload["bundle_fingerprint"] = _fingerprint(projection)
    assert report.get("schema") == RUNNER_SCHEMA
    assert stability.get("schema") == REPORT_SCHEMA
    return SyntheticArtifactBundle(payload)


def _audit_payload() -> dict:
    return deepcopy(_bundle().to_dict())


def _check(audit, check_id: str) -> str:
    return next(check.status for check in audit.checks if check.check_id == check_id)


def test_valid_bundle_produces_deterministic_audit_and_expected_gates() -> None:
    bundle = _bundle()
    first = audit_synthetic_artifact_bundle(bundle)
    second = audit_synthetic_artifact_bundle(bundle)

    assert first.verify_replay(second)
    assert first.audit_fingerprint == second.audit_fingerprint
    assert first.overall_status == CHECK_PASS
    assert _check(first, "audit_replay_deterministic") == CHECK_PASS
    gates = {gate.gate_id: gate.status for gate in first.gates}
    assert gates[GATE_SYNTHETIC_IMPLEMENTATION] == CHECK_PASS
    assert gates[GATE_OFFLINE_RESEARCH_EVALUATION] == "blocked"
    assert gates[GATE_REAL_DATASET_BINDING] == "blocked"
    assert gates[GATE_PROVIDER_INTEGRATION] == "blocked"
    assert gates[GATE_SHADOW_STUDY] == "blocked"
    assert "contract/replay readiness only" in first.interpretation
    assert "never predictive evidence" in first.interpretation


def test_tampered_bundle_and_source_fingerprint_mismatch_are_rejected() -> None:
    tampered = _audit_payload()
    tampered["artifacts"]["evaluation_report"]["interpretation"] = "tampered"
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        audit_synthetic_artifact_bundle(SyntheticArtifactBundle(tampered))

    mismatch = _repack(_audit_payload()).to_dict()
    mismatch["artifacts"]["stability_report"]["source_fingerprint"] = "0" * 64
    mismatch_bundle = mismatch
    from market_os.b31_synthetic_bundle import _artifact_projection, _fingerprint
    stability = mismatch_bundle["artifacts"]["stability_report"]
    stability["fingerprint"] = _fingerprint({key: value for key, value in _artifact_projection(stability).items() if key != "schema"})
    mismatch_bundle["source_fingerprints"]["stability_report"] = stability["fingerprint"]
    projection = dict(mismatch_bundle)
    projection.pop("bundle_fingerprint", None)
    mismatch_bundle["bundle_fingerprint"] = _fingerprint(projection)
    with pytest.raises(ValueError, match="source fingerprint"):
        audit_synthetic_artifact_bundle(SyntheticArtifactBundle(mismatch_bundle))


@pytest.mark.parametrize("mutation", ["missing", "duplicate"])
def test_missing_or_duplicate_arm_fails_synthetic_gate(mutation: str) -> None:
    payload = _audit_payload()
    arms = payload["artifacts"]["evaluation_report"]["arms"]
    if mutation == "missing":
        arms.pop()
    else:
        arms.append(deepcopy(arms[0]))
    audit = audit_synthetic_artifact_bundle(_repack(payload))
    assert _check(audit, "expected_arm_set") == CHECK_FAIL
    assert next(gate for gate in audit.gates if gate.gate_id == GATE_SYNTHETIC_IMPLEMENTATION).status == CHECK_FAIL


def test_b10_outcome_contamination_fails() -> None:
    payload = _audit_payload()
    b10_id = next(row["row_id"] for row in payload["artifacts"]["evaluation_report"]["rows"] if row["fold_id"] == "B10")
    payload["artifacts"]["evaluation_report"]["outcomes"].append({"row_id": b10_id, "label": True})
    audit = audit_synthetic_artifact_bundle(_repack(payload))
    assert _check(audit, "no_b10_realized_outcomes") == CHECK_FAIL


def test_jev_predictive_metric_contamination_fails() -> None:
    payload = _audit_payload()
    jev = next(arm for arm in payload["artifacts"]["evaluation_report"]["arms"] if arm["arm_id"] == "synthetic_jev_coverage")
    jev["metrics"].append({"schema": "market-os.b3-1.synthetic-metric@v1", "name": "brier", "status": "measured", "value": 0.2, "n": 1, "reason": None})
    audit = audit_synthetic_artifact_bundle(_repack(payload))
    assert _check(audit, "numerical_metrics_only_control") == CHECK_FAIL


def test_calibration_test_overlap_fails() -> None:
    payload = _audit_payload()
    fold = payload["artifacts"]["evaluation_report"]["arms"][0]["fold_results"][0]
    fold["test_row_ids"].append(fold["calibration_row_ids"][0])
    audit = audit_synthetic_artifact_bundle(_repack(payload))
    assert _check(audit, "calibration_test_disjoint") == CHECK_FAIL


def test_fusion_measured_instead_of_deferred_fails() -> None:
    payload = _audit_payload()
    fusion = next(arm for arm in payload["artifacts"]["evaluation_report"]["arms"] if arm["arm_id"] == "synthetic_fusion_placeholder")
    fusion["status"] = "measured"
    audit = audit_synthetic_artifact_bundle(_repack(payload))
    assert _check(audit, "fusion_unavailable_deferred") == CHECK_FAIL


def test_external_identity_is_rejected() -> None:
    payload = _audit_payload()
    payload["artifacts"]["evaluation_report"]["external_url"] = "https://example.invalid"
    with pytest.raises(ValueError, match="fingerprint mismatch|forbidden external"):
        audit_synthetic_artifact_bundle(_repack(payload))


def test_self_referential_audit_fingerprint_is_rejected() -> None:
    payload = _audit_payload()
    payload["artifacts"]["evaluation_report"]["audit_fingerprint"] = "a" * 64
    with pytest.raises(ValueError, match="self-referential"):
        audit_synthetic_artifact_bundle(_repack(payload))
