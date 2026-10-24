from __future__ import annotations

import ast
from pathlib import Path

import pytest

from market_os.b31_offline import DatasetRow, OfflineEvaluationPlan, compile_synthetic_evaluation_plan, materialize_synthetic_evaluation_plan
from market_os.b31_synthetic_runner import (
    SyntheticArmId,
    SyntheticArmStatus,
    SyntheticAssessmentSummary,
    build_synthetic_outcome,
    build_synthetic_row,
    run_synthetic_evaluation,
    verify_deterministic_replay,
)


START = 0
DURATION = 1_200_000


def _fixture() -> tuple[OfflineEvaluationPlan, object, object, list[object], list[object]]:
    plan = OfflineEvaluationPlan()
    compilation = compile_synthetic_evaluation_plan(plan, synthetic_start_ms=START, block_duration_ms=DURATION)
    rows = []
    outcomes = []
    material_rows = []
    for block_id in range(1, 11):
        block_start = (block_id - 1) * DURATION
        for offset, label in ((600_000, True), (660_000, False)):
            row_id = f"synthetic-b{block_id}-{offset}"
            feature = f"{block_id * 100 + offset:064x}"
            available = block_id != 10
            rows.append(build_synthetic_row(row_id=row_id, timestamp_ms=block_start + offset, feature_fingerprint=feature, numerical_score=0.2 if label else 0.8, target_available=available, assessment_status="missing"))
            if available:
                outcomes.append(build_synthetic_outcome(row_id, label))
                material_rows.append(DatasetRow(block_start + offset, feature, block_start + offset + 300_000, label))
            else:
                material_rows.append(DatasetRow(block_start + offset, feature))
    materialization = materialize_synthetic_evaluation_plan(compilation, material_rows)
    return plan, compilation, materialization, rows, outcomes


def test_runner_is_end_to_end_deterministic_and_keeps_arms_separate() -> None:
    plan, compilation, materialization, rows, outcomes = _fixture()
    first = run_synthetic_evaluation(plan, compilation, materialization, rows, outcomes)
    second = run_synthetic_evaluation(plan, compilation, materialization, list(reversed(rows)), list(reversed(outcomes)))
    assert verify_deterministic_replay(first, second)
    arms = {arm.arm_id: arm for arm in first.arms}
    assert arms[SyntheticArmId.NUMERICAL_CONTROL].status is SyntheticArmStatus.MEASURED
    assert arms[SyntheticArmId.JEV_COVERAGE].status is SyntheticArmStatus.MEASURED
    assert arms[SyntheticArmId.FUSION_PLACEHOLDER].status is SyntheticArmStatus.UNAVAILABLE_DEFERRED
    assert all(metric.name in {"log_loss", "brier", "balanced_accuracy", "ece", "coverage", "fold_variance"} for metric in arms[SyntheticArmId.NUMERICAL_CONTROL].metrics)
    assert all(row.fold_id != "B10" for row in first.rows if row.split == "untouched") is False
    assert any(row.fold_id == "B10" and row.split == "untouched" for row in first.rows)
    assert "predictive" in first.interpretation


def test_one_bin_uses_calibration_only_and_test_mutation_does_not_change_calibration() -> None:
    plan, compilation, materialization, rows, outcomes = _fixture()
    first = run_synthetic_evaluation(plan, compilation, materialization, rows, outcomes)
    changed = [build_synthetic_outcome(outcome.row_id, not outcome.label) if outcome.row_id.startswith("synthetic-b7") else outcome for outcome in outcomes]
    changed_material_rows = [
        DatasetRow(row.timestamp_ms, row.feature_fingerprint, row.target.target_end_ms, next(item.label for item in changed if item.row_id == row.row_id))
        if row.target.status.value == "available" else DatasetRow(row.timestamp_ms, row.feature_fingerprint)
        for row in rows
    ]
    changed_materialization = materialize_synthetic_evaluation_plan(compilation, changed_material_rows)
    second = run_synthetic_evaluation(plan, compilation, changed_materialization, rows, changed)
    first_calibration = first.arms[0].fold_results[0].to_dict()["calibration"]
    second_calibration = second.arms[0].fold_results[0].to_dict()["calibration"]
    assert first_calibration == second_calibration


def test_unavailable_calibration_is_explicit() -> None:
    plan, compilation, materialization, rows, outcomes = _fixture()
    only_positive = [build_synthetic_outcome(outcome.row_id, True) for outcome in outcomes]
    material_rows = [
        DatasetRow(row.timestamp_ms, row.feature_fingerprint, row.target.target_end_ms, True)
        if row.target.status.value == "available" else DatasetRow(row.timestamp_ms, row.feature_fingerprint)
        for row in rows
    ]
    materialization = materialize_synthetic_evaluation_plan(compilation, material_rows)
    report = run_synthetic_evaluation(plan, compilation, materialization, rows, only_positive)
    assert report.arms[0].fold_results[0].status == "unavailable"
    assert any("single-class" in reason for reason in report.arms[0].fold_results[0].unavailable_reasons)


def test_row_contract_rejects_future_fields_and_duplicate_identities() -> None:
    with pytest.raises(ValueError, match="future-derived"):
        from market_os.b31_offline import FeatureRowIdentity
        FeatureRowIdentity.from_mapping({"dataset_revision": "synthetic-v1", "feature_close_time_ms": 0, "input_fingerprint": "a" * 64, "future_target": True})
    plan, compilation, materialization, rows, outcomes = _fixture()
    with pytest.raises(ValueError, match="duplicate synthetic row ID"):
        run_synthetic_evaluation(plan, compilation, materialization, rows + [rows[0]], outcomes)
    with pytest.raises(ValueError, match="duplicate synthetic feature identity"):
        duplicate = build_synthetic_row(row_id="synthetic-duplicate", timestamp_ms=rows[1].timestamp_ms, feature_fingerprint=rows[0].feature_fingerprint, numerical_score=0.5)
        run_synthetic_evaluation(plan, compilation, materialization, rows[:1] + [duplicate], outcomes[:0])


def test_advisory_ranking_is_serialized_but_cannot_change_numerical_prediction() -> None:
    plan, compilation, materialization, rows, outcomes = _fixture()
    rows[0] = build_synthetic_row(row_id=rows[0].row_id, timestamp_ms=rows[0].timestamp_ms, feature_fingerprint=rows[0].feature_fingerprint, numerical_score=0.2, assessment=SyntheticAssessmentSummary("usable", ("synthetic-response-a",), True, 0.95, ("synthetic-h2", "synthetic-h1")), assessment_reference="synthetic-assessment-a")
    first = run_synthetic_evaluation(plan, compilation, materialization, rows, outcomes)
    rows[0] = build_synthetic_row(row_id=rows[0].row_id, timestamp_ms=rows[0].timestamp_ms, feature_fingerprint=rows[0].feature_fingerprint, numerical_score=0.2, assessment=SyntheticAssessmentSummary("usable", ("synthetic-response-a",), True, 0.95, ("synthetic-h1", "synthetic-h2")), assessment_reference="synthetic-assessment-a")
    second = run_synthetic_evaluation(plan, compilation, materialization, rows, outcomes)
    assert first.arms[0].fold_results[0].to_dict()["calibration"] == second.arms[0].fold_results[0].to_dict()["calibration"]
    assert first.arms[0].metrics == second.arms[0].metrics


def test_status_inventory_and_unavailable_numerical_score_are_explicit() -> None:
    plan, compilation, materialization, rows, outcomes = _fixture()
    statuses = ("schema_invalid", "unsupported", "internally_inconsistent", "stale", "unavailable", "abstained", "usable")
    replacements = []
    for index, status in enumerate(statuses):
        base = rows[index]
        assessment = SyntheticAssessmentSummary(status, (f"synthetic-response-{index}",), index == 6, 0.95 if index == 6 else None, ("synthetic-hypothesis",)) if status == "usable" else None
        replacements.append(build_synthetic_row(row_id=base.row_id, timestamp_ms=base.timestamp_ms, feature_fingerprint=base.feature_fingerprint, numerical_score=None if index == 0 else base.numerical_score, assessment=assessment, assessment_status=status, assessment_reference=f"synthetic-assessment-{index}" if assessment else None))
    rows[: len(replacements)] = replacements
    report = run_synthetic_evaluation(plan, compilation, materialization, rows, outcomes)
    counts = report.arms[1].assessment_status_counts
    assert all(counts[status] >= 1 for status in statuses)
    assert report.arms[0].numerical_score_eligible_row_count < report.arms[0].target_eligible_row_count


def test_b10_is_untouched_and_not_in_arm_eligibility() -> None:
    plan, compilation, materialization, rows, outcomes = _fixture()
    rows[-1] = build_synthetic_row(
        row_id=rows[-1].row_id,
        timestamp_ms=rows[-1].timestamp_ms,
        feature_fingerprint=rows[-1].feature_fingerprint,
        numerical_score=0.1,
        target_available=False,
        assessment_status="usable",
        assessment=SyntheticAssessmentSummary("usable", ("synthetic-response-b10",), True, 0.9, ("synthetic-h",)),
        assessment_reference="synthetic-assessment-b10",
    )
    report = run_synthetic_evaluation(plan, compilation, materialization, rows, outcomes)
    assert report.row_count == 20
    assert report.target_eligible_row_count == 18
    assert all(row.assessment_status == "missing" for row in report.rows if row.fold_id == "B10")
    assert all(arm.row_count == 18 for arm in report.arms)


def test_duplicate_assessment_reference_and_invalid_assessment_identity_rejected() -> None:
    plan, compilation, materialization, rows, outcomes = _fixture()
    summary = SyntheticAssessmentSummary("usable", ("synthetic-response-a",), False, None, ("synthetic-h",))
    rows[0] = build_synthetic_row(row_id=rows[0].row_id, timestamp_ms=rows[0].timestamp_ms, feature_fingerprint=rows[0].feature_fingerprint, numerical_score=0.2, assessment=summary, assessment_reference="synthetic-assessment-a")
    rows[1] = build_synthetic_row(row_id=rows[1].row_id, timestamp_ms=rows[1].timestamp_ms, feature_fingerprint=rows[1].feature_fingerprint, numerical_score=0.8, assessment=summary, assessment_reference="synthetic-assessment-a")
    with pytest.raises(ValueError, match="duplicate synthetic assessment reference"):
        run_synthetic_evaluation(plan, compilation, materialization, rows, outcomes)
    with pytest.raises(ValueError, match="forbidden external identity|synthetic reference"):
        SyntheticAssessmentSummary("usable", ("provider-response",), False, None, ("synthetic-h",))


def test_purge_and_embargo_assignments_are_retained_in_fold_artifacts() -> None:
    plan, compilation, _, rows, outcomes = _fixture()
    material_rows = [DatasetRow(row.timestamp_ms, row.feature_fingerprint, row.target.target_end_ms, next(item.label for item in outcomes if item.row_id == row.row_id)) if row.target.status.value == "available" else DatasetRow(row.timestamp_ms, row.feature_fingerprint) for row in rows]
    # A boundary-adjacent five-minute row is retained by the materializer as metadata.
    materialization = materialize_synthetic_evaluation_plan(compilation, material_rows)
    report = run_synthetic_evaluation(plan, compilation, materialization, rows, outcomes)
    assert all("purged" in fold.assessment_status_counts and "embargoed" in fold.assessment_status_counts for arm in report.arms[:2] for fold in arm.fold_results)


def test_fingerprints_cover_final_arm_accounting_and_fusion_fold() -> None:
    plan, compilation, materialization, rows, outcomes = _fixture()
    report = run_synthetic_evaluation(plan, compilation, materialization, rows, outcomes)
    for arm in report.arms:
        assert arm.to_dict()["fingerprint"] == arm.fingerprint
        assert all(fold.fingerprint for fold in arm.fold_results)


def test_runner_has_no_external_transport_or_execution_symbols() -> None:
    source = Path(__file__).parents[1].joinpath("b31_synthetic_runner.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imports |= {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names}
    forbidden = {"urllib", "requests", "httpx", "socket", "websocket", "subprocess", "binance", "openai"}
    assert not imports & forbidden
    assert not any(token in source.lower() for token in ("api_key", "secret_key", "fill", "portfolio", "execution_path"))
