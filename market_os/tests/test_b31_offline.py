from __future__ import annotations

import math

import pytest

from market_os.b31_offline import (
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


def test_calibration_enforces_test_separation_and_isotonic_approval() -> None:
    scores = {str(i): float(i - 2) for i in range(6)}
    labels = {str(i): i >= 3 for i in range(6)}
    artifact = fit_calibrator(scores, labels, CalibrationConfig(CalibrationMethod.ONE_BIN), calibration_row_ids=("0", "1", "2"), test_row_ids=("3", "4", "5"))
    assert artifact.status == "measured"
    assert 0.0 <= artifact.predict(0.0) <= 1.0
    with pytest.raises(ValueError, match="overlap"):
        fit_calibrator(scores, labels, CalibrationConfig(CalibrationMethod.ONE_BIN), calibration_row_ids=("0", "1"), test_row_ids=("1", "2"))
    with pytest.raises(ValueError, match="approved"):
        CalibrationConfig(CalibrationMethod.ISOTONIC)
    assert CalibrationConfig(CalibrationMethod.ISOTONIC, isotonic_min_rows=100, isotonic_approved=True).to_dict()["isotonic_approved"] is True


def test_fusion_encoding_keeps_explicit_missingness_without_neutral_probability() -> None:
    assert FusionInput("string-state", "test", 0.1, "abstained").to_dict()["state"] == "abstained"
    with pytest.raises(ValueError, match="unsupported fusion input state"):
        FusionInput("invalid-state", "test", 0.1, "not-a-state")
    encoded = encode_fusion_inputs([
        FusionInput("score", "numerical_score", 0.2, EvidenceState.USABLE),
        FusionInput("jev", "jev_semantic", None, EvidenceState.ABSTAINED, dimensions={"support": 0.9}),
        FusionInput("probability", "calibrated_probability", None, EvidenceState.MISSING),
    ])
    assert encoded.values["score"] == 0.2
    assert encoded.values["jev__support"] == 0.9
    assert encoded.values["probability__missing"] == 1.0
    assert encoded.values["probability"] == 0.0
    assert encoded.values["probability"] != 0.5
    config = RegularizedLogisticFusionConfig(l2_lambda=0.1)
    assert config.to_dict()["l2_lambda"] == 0.1
    fusion = fit_regularized_logistic_fusion(config, train_row_ids=("a",), test_row_ids=("b",))
    assert fusion.status == "unavailable"
    with pytest.raises(ValueError, match="overlap"):
        fit_regularized_logistic_fusion(config, train_row_ids=("a",), test_row_ids=("a",))


def test_metrics_report_unavailable_support_and_deterministic_values() -> None:
    assert log_loss((0.9, 0.1), (True, False)).value is not None
    assert brier_score((0.9, 0.1), (True, False)).value == pytest.approx(0.01)
    assert balanced_accuracy((0.9, 0.1), (True, False)).value == pytest.approx(1.0)
    assert log_loss((0.9,), (True,)).status == "unavailable"
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
