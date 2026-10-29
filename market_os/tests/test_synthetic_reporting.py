from __future__ import annotations

import pytest

from market_os.synthetic_reporting import (
    build_synthetic_stability_report,
    verify_synthetic_stability_replay,
)
from market_os.synthetic_evaluation import (
    SyntheticArmArtifact,
    SyntheticArmId,
    SyntheticArmStatus,
    SyntheticEvaluationReport,
    SyntheticFoldArtifact,
    SyntheticMetric,
    SyntheticOutcome,
    SyntheticRowArtifact,
)


def _row(row_id: str, split: str, status: str, probability: float | None = None, target: str = "available") -> SyntheticRowArtifact:
    row_id = f"synthetic-{row_id}"
    return SyntheticRowArtifact(
        row_id, "a" * 64, "F1", split, target, "eligible" if probability is not None else "unavailable",
        status, None, "b" * 64, "c" * 64, (), status == "contradictory", status == "usable" and probability == 1.0, (), probability, None,
    )


def _fold(fold_id: str, values: tuple[float, ...], *, unavailable: bool = False) -> SyntheticFoldArtifact:
    metrics = (SyntheticMetric("log_loss", "unavailable", None, 0, "no test rows") if unavailable else SyntheticMetric("log_loss", "measured", values[0], 2),)
    rows = (_row(f"{fold_id}-a", "test", "usable", 0.8), _row(f"{fold_id}-b", "test", "abstained", 0.2))
    return SyntheticFoldArtifact(
        fold_id, "unavailable" if unavailable else "measured", rows, {"usable": 1, "abstained": 1}, (), tuple(row.row_id for row in rows),
        "unavailable", "one_bin", None, "", metrics, ("no test rows",) if unavailable else (), "d" * 64, {}, len(rows), 2, 2,
    )


def _report() -> SyntheticEvaluationReport:
    folds = (_fold("F1", (0.1,)), _fold("F2", (0.3,)), _fold("F3", (0.2,), unavailable=True))
    arm = SyntheticArmArtifact(SyntheticArmId.NUMERICAL_CONTROL, SyntheticArmStatus.MEASURED, folds, 6, 6, 6, {"usable": 3, "abstained": 3}, ("F1-a", "F1-b", "F2-a", "F2-b"), (SyntheticMetric("log_loss", "measured", 0.2, 4),), (), "e" * 64)
    jev = SyntheticArmArtifact(SyntheticArmId.JEV_COVERAGE, SyntheticArmStatus.MEASURED, folds, 6, 6, 0, {"usable": 3, "abstained": 3}, (), (SyntheticMetric("coverage", "measured", 0.5, 6),), (), "f" * 64)
    fusion = SyntheticArmArtifact(SyntheticArmId.FUSION_PLACEHOLDER, SyntheticArmStatus.UNAVAILABLE_DEFERRED, (folds[0],), 2, 2, 2, {"usable": 1, "abstained": 1}, (), (SyntheticMetric("coverage", "unavailable", None, 0, "fusion fitting is deferred"),), ("fusion fitting is deferred",), "0" * 64)
    rows = tuple(item for fold in folds for item in fold.row_artifacts)
    outcomes = tuple(SyntheticOutcome(row.row_id, index % 2 == 0) for index, row in enumerate(rows[:4]))
    return SyntheticEvaluationReport(rows, outcomes, (arm, jev, fusion), "a" * 64, "b" * 64, "c" * 64, True, "synthetic", {"latency": "unknown_not_observed_offline"}, "1" * 64)


def test_fold_mean_population_variance_and_worst_fold() -> None:
    summary = next(item for item in build_synthetic_stability_report(_report()).metric_summaries if item.arm_id == SyntheticArmId.NUMERICAL_CONTROL.value and item.metric_name == "log_loss")
    assert summary.measured_fold_count == 2
    assert summary.unavailable_fold_count == 1
    assert summary.mean == 0.2
    assert summary.population_variance == pytest.approx(0.01)
    assert summary.worst_fold_id == "F2"


def test_coverage_status_and_failure_accounting_are_explicit() -> None:
    result = build_synthetic_stability_report(_report())
    assert any(cell.status == "usable" and cell.count == 1 and cell.denominator == 2 for cell in result.coverage)
    assert result.status_counts_by_arm[SyntheticArmId.NUMERICAL_CONTROL.value]["abstained"] == 3
    assert any(item.fold_id == "F3" and item.unavailable_metric_count == 1 for item in result.failures)
    assert result.runtime_assumptions["latency"] == "unknown_not_observed_offline"


def test_predictive_metrics_use_only_joined_numerical_test_rows_and_replay_is_stable() -> None:
    first = build_synthetic_stability_report(_report())
    second = build_synthetic_stability_report(_report())
    assert verify_synthetic_stability_replay(first, second)
    assert any(metric.status == "measured" for metric in first.predictive_metrics)
    assert first.to_dict()["schema"] == "market-os.b3-1.synthetic-stability-report@v1"
