from __future__ import annotations

import math

import pytest

from market_os.evaluation_protocol import (
    B31_TARGET_VERSION,
    CalibrationConfig,
    CalibrationMethod,
    CoverageStatus,
    DatasetClass,
    DatasetIdentity,
    DatasetRow,
    EvidenceState,
    FeatureRowIdentity,
    FoldSpec,
    OfflineRuntimeAssumptions,
    FusionInput,
    RegularizedLogisticFusionConfig,
    TargetStatus,
    build_chronological_folds,
    build_dataset_identity,
    coverage_status_counts,
    encode_fusion_inputs,
    fit_calibrator,
    fit_regularized_logistic_fusion,
    fold_variance,
    expected_calibration_error,
    join_b2_target,
    log_loss,
    brier_score,
    balanced_accuracy,
    calibration_bins,
    matched_row_accounting,
    replay_fingerprint,
    B31_EVALUATION_PLAN_SCHEMA,
    EvaluationGate,
    EvaluationPlanStatus,
    EvaluationFoldPlan,
    OfflineEvaluationPlan,
    recommended_evaluation_folds,
    compile_synthetic_evaluation_plan,
    materialize_synthetic_evaluation_plan,
    B31_SYNTHETIC_PLAN_SCHEMA,
    B31_SYNTHETIC_MATERIALIZATION_SCHEMA,
)


def _identity(**overrides: object) -> DatasetIdentity:
    values: dict[str, object] = {
        "dataset_revision": "synthetic-revision",
        "symbol": "BTCUSDT",
        "interval": "1m",
        "start_ms": 0,
        "end_ms": 600_000,
        "row_count": 11,
        "raw_fingerprint": "a" * 64,
        "provenance_fingerprint": "b" * 64,
        "replay_fingerprint": "c" * 64,
        "coverage_status": "continuous",
        "gap_count": 0,
        "dataset_class": DatasetClass.SMOKE,
    }
    values.update(overrides)
    return DatasetIdentity(**values)


def test_dataset_identity_validates_revision_bounds_fingerprints_and_gaps() -> None:
    assert _identity().to_dict()["dataset_class"] == "smoke"
    assert _identity(dataset_class="smoke").dataset_class is DatasetClass.SMOKE
    assert _identity(dataset_class="research").dataset_class is DatasetClass.RESEARCH
    assert _identity().coverage_status is CoverageStatus.CONTINUOUS
    with pytest.raises(ValueError, match="UTC bounds"):
        _identity(end_ms=0)
    with pytest.raises(ValueError, match="fingerprint"):
        _identity(raw_fingerprint="bad")
    with pytest.raises(ValueError, match="continuous"):
        _identity(coverage_status="continuous", gap_count=1)
    with pytest.raises(ValueError, match="research dataset"):
        _identity(dataset_class=DatasetClass.RESEARCH, gap_count=1, coverage_status="gapped")
    with pytest.raises(ValueError, match="research dataset"):
        _identity(dataset_class="research", gap_count=1, coverage_status="gapped")
    with pytest.raises(ValueError, match="research dataset"):
        _identity(dataset_class="research", coverage_status="gapped")


def test_build_dataset_identity_rejects_gaps_and_counts_rows() -> None:
    rows = [DatasetRow(open_time_ms=i * 60_000, row_fingerprint=f"{i:064x}") for i in range(3)]
    identity = build_dataset_identity(
        dataset_revision="synthetic-revision",
        symbol="BTCUSDT",
        interval="1m",
        rows=rows,
        start_ms=0,
        end_ms=180_000,
        raw_fingerprint="a" * 64,
        provenance_fingerprint="b" * 64,
        dataset_class=DatasetClass.SMOKE,
    )
    assert identity.row_count == 3
    assert identity.coverage_status == "continuous"
    with pytest.raises(ValueError, match="gap"):
        build_dataset_identity(
            dataset_revision="synthetic-revision",
            symbol="BTCUSDT",
            interval="1m",
            rows=[rows[0], rows[2]],
            start_ms=0,
            end_ms=180_000,
            raw_fingerprint="a" * 64,
            provenance_fingerprint="b" * 64,
            dataset_class=DatasetClass.RESEARCH,
        )


def test_target_join_is_leakage_safe_and_labels_zero_non_positive() -> None:
    feature = FeatureRowIdentity("synthetic-revision", 600_000, "d" * 64)
    positive = join_b2_target(feature, close=100.0, target_close=101.0, target_available=True)
    assert positive.target_version == B31_TARGET_VERSION
    assert positive.label == "positive"
    zero = join_b2_target(feature, close=100.0, target_close=100.0, target_available=True)
    assert zero.label == "non_positive"
    missing = join_b2_target(feature, close=100.0, target_close=None, target_available=False)
    assert missing.status is TargetStatus.UNAVAILABLE
    assert missing.label is None
    base = {
        "dataset_revision": "synthetic-revision",
        "feature_close_time_ms": 600_000,
        "input_fingerprint": "d" * 64,
    }
    for forbidden in (
        "future_target",
        "target_labels",
        "future_return",
        "foo_future_value",
        "realized_outcome",
        "target_fingerprint",
    ):
        with pytest.raises(ValueError, match="future-derived"):
            FeatureRowIdentity.from_mapping({**base, forbidden: 1.0})
    lineage = FeatureRowIdentity.from_mapping(
        {
            **base,
            "target_definition_id": "btc.b2.close-return-5m",
            "target_version": B31_TARGET_VERSION,
        }
    )
    assert lineage.dataset_revision == "synthetic-revision"


def _rows() -> list[DatasetRow]:
    return [
        DatasetRow(i * 60_000, f"{i:064x}", target_end_ms=(i + 5) * 60_000, label=(i % 2 == 0))
        for i in range(20)
    ]


def test_chronological_folds_order_purge_embargo_and_fingerprint() -> None:
    specs = [
        FoldSpec("fold-1", train=(0, 600_000), validation=(600_000, 900_000), calibration=(900_000, 1_020_000), test=(1_020_000, 1_200_000)),
    ]
    first = build_chronological_folds(_rows(), specs)
    second = build_chronological_folds(list(reversed(_rows())), specs)
    assert first.split_fingerprint == second.split_fingerprint
    assert first.folds[0].assignments[0].split == "train"
    assert any(item.split == "purged" for item in first.folds[0].assignments)
    assert any(item.split == "embargoed" for item in first.folds[0].assignments)
    assert first.status_counts["train"] > 0
    with pytest.raises(ValueError, match="shuffle"):
        build_chronological_folds(_rows(), specs, shuffle=True)
    with pytest.raises(ValueError, match="duplicate timestamps"):
        build_chronological_folds(_rows() + [_rows()[0]], specs)
    with pytest.raises(ValueError, match="outside configured"):
        build_chronological_folds(_rows() + [DatasetRow(1_800_000, "e" * 64, target_end_ms=2_100_000)], specs)
    with pytest.raises(ValueError, match="target_end_ms"):
        DatasetRow(0, "f" * 64, target_end_ms=6 * 60_000)


def test_calibration_enforces_test_separation_and_isotonic_approval() -> None:
    scores = {str(i): float(i - 2) for i in range(6)}
    labels = {str(i): i >= 3 for i in range(6)}
    artifact = fit_calibrator(scores, labels, CalibrationConfig(CalibrationMethod.ONE_BIN), calibration_row_ids=("0", "1", "2"), test_row_ids=("3", "4", "5"))
    assert artifact.status == "measured"
    assert 0.0 <= artifact.predict(0.0) <= 1.0
    assert CalibrationConfig("one_bin").to_dict()["method"] == "one_bin"
    with pytest.raises(ValueError, match="unsupported calibration method"):
        CalibrationConfig("unknown")
    with pytest.raises(ValueError, match="overlap"):
        fit_calibrator(scores, labels, CalibrationConfig(CalibrationMethod.ONE_BIN), calibration_row_ids=("0", "1"), test_row_ids=("1", "2"))
    with pytest.raises(ValueError, match="unique"):
        fit_calibrator(scores, labels, CalibrationConfig(CalibrationMethod.ONE_BIN), calibration_row_ids=("0", "0"), test_row_ids=("1", "2"))
    with pytest.raises(ValueError, match="approved"):
        CalibrationConfig(CalibrationMethod.ISOTONIC)
    assert CalibrationConfig(CalibrationMethod.ISOTONIC, isotonic_min_rows=100, isotonic_approved=True).to_dict()["isotonic_approved"] is True


def test_fusion_encoding_keeps_explicit_missingness_without_neutral_probability() -> None:
    assert FusionInput("string-state", "test", None, "abstained").to_dict()["state"] == "abstained"
    with pytest.raises(ValueError, match="unsupported fusion input state"):
        FusionInput("invalid-state", "test", 0.1, "not-a-state")
    encoded = encode_fusion_inputs([
        FusionInput("score", "numerical_score", 0.2, EvidenceState.USABLE),
        FusionInput("jev", "jev_semantic", None, EvidenceState.ABSTAINED),
        FusionInput("probability", "calibrated_probability", None, EvidenceState.MISSING),
    ])
    assert encoded.values["score"] == 0.2
    assert encoded.values["probability__missing"] == 1.0
    assert encoded.values["probability"] == 0.0
    assert encoded.values["probability"] != 0.5
    with pytest.raises(ValueError, match="cannot carry"):
        FusionInput("stale", "jev_semantic", None, EvidenceState.STALE, dimensions={"support": 0.9})
    with pytest.raises(ValueError, match="unique"):
        encode_fusion_inputs([FusionInput("dup", "a", 0.1, EvidenceState.USABLE), FusionInput("dup", "b", 0.2, EvidenceState.USABLE)])
    config = RegularizedLogisticFusionConfig(l2_lambda=0.1)
    assert config.to_dict()["l2_lambda"] == 0.1
    fusion = fit_regularized_logistic_fusion(config, train_row_ids=("a",), test_row_ids=("b",))
    assert fusion.status == "unavailable"
    with pytest.raises(ValueError, match="overlap"):
        fit_regularized_logistic_fusion(config, train_row_ids=("a",), test_row_ids=("a",))
    with pytest.raises(ValueError, match="unique"):
        fit_regularized_logistic_fusion(config, train_row_ids=("a", "a"), test_row_ids=("b",))


def test_metrics_report_unavailable_support_and_deterministic_values() -> None:
    assert log_loss((0.9, 0.1), (True, False)).value is not None
    assert brier_score((0.9, 0.1), (True, False)).value == pytest.approx(0.01)
    assert balanced_accuracy((0.9, 0.1), (True, False)).value == pytest.approx(1.0)
    assert log_loss((0.9,), (True,)).status == "unavailable"
    with pytest.raises(ValueError, match="labels must be bool"):
        log_loss((0.9, 0.1), (1, False))
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        brier_score((1.1, 0.1), (True, False))
    with pytest.raises(ValueError, match="finite"):
        brier_score((float("nan"), 0.1), (True, False))
    bins = calibration_bins((0.9, 0.1), (True, False), bin_count=2)
    assert bins.status == "measured"
    assert expected_calibration_error((0.9, 0.1), (True, False), bin_count=2).name == "ece"
    assert coverage_status_counts(("usable", "abstained", "usable")) == {"abstained": 1, "usable": 2}
    assert fold_variance((0.1, 0.3)).value == pytest.approx(0.01)
    assert matched_row_accounting(("a", "b"), ("b", "c")).intersection_count == 1
    assert OfflineRuntimeAssumptions().to_dict()["cost"] == "unknown_not_observed_offline"


def test_artifact_replay_fingerprint_is_stable() -> None:
    identity = _identity()
    first = replay_fingerprint(identity.to_dict(), {"latency": "unknown_not_observed_offline"})
    second = replay_fingerprint({"latency": "unknown_not_observed_offline"}, identity.to_dict())
    assert first == second


def test_synthetic_evaluation_plan_is_deterministic_and_dataset_unbound() -> None:
    plan = OfflineEvaluationPlan()
    assert plan.status is EvaluationPlanStatus.DATASET_UNBOUND
    assert plan.to_dict()["schema_id"] == B31_EVALUATION_PLAN_SCHEMA
    assert plan.fingerprint == OfflineEvaluationPlan().fingerprint
    assert plan.gate_status(EvaluationGate.IMPLEMENTATION) == "eligible_synthetic_only"
    assert plan.gate_status(EvaluationGate.OFFLINE_EVALUATION) == "blocked_dataset_unbound"
    assert tuple(fold.fold_id for fold in plan.folds) == ("F1", "F2", "F3")
    assert plan.purge_ms == plan.embargo_ms == 300_000
    assert plan.folds[0].train_blocks == (1, 2, 3, 4)
    assert plan.folds[0].validation_block == 5
    assert plan.folds[0].calibration_block == 6
    assert plan.folds[0].test_block == 7
    assert plan.folds[1].train_blocks == (1, 2, 3, 4, 5)
    assert plan.folds[1].test_block == 8
    assert plan.folds[2].train_blocks == (1, 2, 3, 4, 5, 6)
    assert plan.folds[2].test_block == 9


def test_evaluation_plan_rejects_real_binding_and_non_chronological_folds() -> None:
    with pytest.raises(ValueError, match="real dataset binding"):
        OfflineEvaluationPlan(dataset_revision="real-revision")
    with pytest.raises(ValueError, match="chronological"):
        EvaluationFoldPlan("bad", (1, 3), 2, 4, 5)
    with pytest.raises(ValueError, match="shuffle"):
        build_chronological_folds(_rows(), (FoldSpec("f", (0, 600_000), None, (600_000, 900_000), (900_000, 1_200_000)),), shuffle=True)


def test_recommended_folds_use_symbolic_expanding_blocks() -> None:
    folds = recommended_evaluation_folds()
    assert folds[0].train_blocks == (1, 2, 3, 4)
    assert folds[-1].test_block == 9
    assert 10 not in {block for fold in folds for block in (fold.validation_block, fold.calibration_block, fold.test_block)}


def _synthetic_rows(start_ms: int, block_duration_ms: int) -> list[DatasetRow]:
    rows: list[DatasetRow] = []
    # Two labelled rows per block give every used split both binary labels.
    for block_id in range(1, 11):
        block_start = start_ms + (block_id - 1) * block_duration_ms
        rows.extend((
            DatasetRow(block_start + 360_000, f"{block_id * 2:064x}", block_start + 660_000, True),
            DatasetRow(block_start + 420_000, f"{block_id * 2 + 1:064x}", block_start + 720_000, False),
        ))
    return rows


def test_synthetic_plan_compiler_maps_frozen_blocks_without_real_dataset() -> None:
    plan = OfflineEvaluationPlan()
    compiled = compile_synthetic_evaluation_plan(plan, synthetic_start_ms=0, block_duration_ms=1_200_000)
    repeat = compile_synthetic_evaluation_plan(plan, synthetic_start_ms=0, block_duration_ms=1_200_000)
    assert compiled.to_dict()["schema_id"] == B31_SYNTHETIC_PLAN_SCHEMA
    assert compiled.fingerprint == repeat.fingerprint
    assert len(compiled.blocks) == 10
    assert compiled.blocks[0].start_ms == 0
    assert compiled.blocks[-1].end_ms == 12_000_000
    assert compiled.fold_specs[0].train == (0, 4_800_000)
    assert compiled.fold_specs[0].validation == (4_800_000, 6_000_000)
    assert compiled.fold_specs[0].calibration == (6_000_000, 7_200_000)
    assert compiled.fold_specs[0].test == (7_200_000, 8_400_000)
    with pytest.raises(ValueError, match="minute-aligned"):
        compile_synthetic_evaluation_plan(plan, synthetic_start_ms=1, block_duration_ms=1_200_000)
    with pytest.raises(ValueError, match="real dataset binding"):
        compile_synthetic_evaluation_plan(OfflineEvaluationPlan(dataset_revision="not-allowed"), synthetic_start_ms=0, block_duration_ms=1_200_000)


def test_synthetic_materializer_preserves_b10_and_target_unavailability() -> None:
    compiled = compile_synthetic_evaluation_plan(OfflineEvaluationPlan(), synthetic_start_ms=0, block_duration_ms=1_200_000)
    rows = _synthetic_rows(0, 1_200_000)
    unavailable = DatasetRow(120_000, f"{999:064x}", None, None)
    materialized = materialize_synthetic_evaluation_plan(compiled, rows + [unavailable])
    replay = materialize_synthetic_evaluation_plan(compiled, list(reversed(rows + [unavailable])))
    assert materialized.to_dict()["schema_id"] == B31_SYNTHETIC_MATERIALIZATION_SCHEMA
    assert materialized.replay_fingerprint == replay.replay_fingerprint
    assert materialized.status == "materialized"
    assert materialized.status_counts["untouched"] == 2
    assert materialized.status_counts["target_unavailable"] == 1
    assert all(item.row_fingerprint != f"{20:064x}" for fold in materialized.fold_set.folds for item in fold.assignments)
    assert materialized.fold_label_counts["F1"]["test"] == {"positive": 1, "non_positive": 1}


def test_synthetic_materializer_reports_insufficient_support_and_rejects_out_of_plan_rows() -> None:
    compiled = compile_synthetic_evaluation_plan(OfflineEvaluationPlan(), synthetic_start_ms=0, block_duration_ms=1_200_000)
    positive_only = [
        DatasetRow((block_id - 1) * 1_200_000 + 600_000, f"{block_id:064x}", (block_id - 1) * 1_200_000 + 900_000, True)
        for block_id in range(1, 10)
    ]
    result = materialize_synthetic_evaluation_plan(compiled, positive_only)
    assert result.status == "unavailable_insufficient_label_support"
    with pytest.raises(ValueError, match="outside B1-B10"):
        materialize_synthetic_evaluation_plan(compiled, [DatasetRow(12_000_000, "f" * 64, 12_300_000, True)])
