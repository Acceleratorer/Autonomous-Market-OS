"""Pure reporting for synthetic B3.1 evaluation artifacts.

This module summarizes already-produced synthetic runner artifacts.  It does
not fit models, reinterpret Jev semantics, or access data or providers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .b31_offline import balanced_accuracy, brier_score, expected_calibration_error, log_loss
from .b31_synthetic_runner import (
    SyntheticArmArtifact,
    SyntheticEvaluationReport,
    SyntheticFoldArtifact,
    SyntheticMetric,
)


REPORT_SCHEMA = "market-os.b3-1.synthetic-stability-report@v1"
_LOWER_IS_BETTER = frozenset({"log_loss", "brier", "ece"})
_PREDICTIVE_METRICS = ("log_loss", "brier", "balanced_accuracy", "ece")
_EXCLUDED_SPLITS = frozenset({"purged", "embargoed", "outside", "untouched"})


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _plain(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _canonical(value: Any) -> str:
    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _metric(name: str, status: str, value: float | None, n: int, reason: str | None = None) -> SyntheticMetric:
    return SyntheticMetric(name, status, value, n, reason)


@dataclass(frozen=True)
class SyntheticFoldMetricSummary:
    arm_id: str
    metric_name: str
    measured_fold_count: int
    unavailable_fold_count: int
    unavailable_reasons: tuple[str, ...]
    mean: float | None
    population_variance: float | None
    worst_fold_id: str | None
    worst_fold_value: float | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "unavailable_reasons", tuple(sorted(set(self.unavailable_reasons))))
        for value in (self.mean, self.population_variance, self.worst_fold_value):
            if value is not None and (not math.isfinite(value) or value < 0 and value is self.population_variance):
                raise ValueError("metric summary values must be finite")

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm_id": self.arm_id,
            "metric_name": self.metric_name,
            "measured_fold_count": self.measured_fold_count,
            "unavailable_fold_count": self.unavailable_fold_count,
            "unavailable_reasons": list(self.unavailable_reasons),
            "mean": self.mean,
            "population_variance": self.population_variance,
            "worst_fold_id": self.worst_fold_id,
            "worst_fold_value": self.worst_fold_value,
        }


@dataclass(frozen=True)
class SyntheticCoverageCell:
    arm_id: str
    fold_id: str
    split: str
    status: str
    count: int
    denominator: int
    denominator_definition: str = "all row artifacts for this arm and fold"

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm_id": self.arm_id,
            "fold_id": self.fold_id,
            "split": self.split,
            "status": self.status,
            "count": self.count,
            "denominator": self.denominator,
            "denominator_definition": self.denominator_definition,
        }


@dataclass(frozen=True)
class SyntheticFailureSummary:
    arm_id: str
    fold_id: str
    fold_status: str
    partial: bool
    unavailable_metric_count: int
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasons", tuple(sorted(set(self.reasons))))

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm_id": self.arm_id,
            "fold_id": self.fold_id,
            "fold_status": self.fold_status,
            "partial": self.partial,
            "unavailable_metric_count": self.unavailable_metric_count,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class SyntheticStabilityReport:
    source_fingerprint: str
    metric_summaries: tuple[SyntheticFoldMetricSummary, ...]
    coverage: tuple[SyntheticCoverageCell, ...]
    status_counts_by_arm: Mapping[str, Mapping[str, int]]
    predictive_metrics: tuple[SyntheticMetric, ...]
    failures: tuple[SyntheticFailureSummary, ...]
    excluded_counts: Mapping[str, int]
    runtime_assumptions: Mapping[str, str]
    fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_summaries", tuple(self.metric_summaries))
        object.__setattr__(self, "coverage", tuple(self.coverage))
        object.__setattr__(self, "predictive_metrics", tuple(self.predictive_metrics))
        object.__setattr__(self, "failures", tuple(self.failures))
        object.__setattr__(self, "status_counts_by_arm", MappingProxyType({k: MappingProxyType(dict(v)) for k, v in self.status_counts_by_arm.items()}))
        object.__setattr__(self, "excluded_counts", MappingProxyType(dict(self.excluded_counts)))
        object.__setattr__(self, "runtime_assumptions", MappingProxyType(dict(self.runtime_assumptions)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": REPORT_SCHEMA,
            "source_fingerprint": self.source_fingerprint,
            "metric_summaries": [item.to_dict() for item in self.metric_summaries],
            "coverage": [item.to_dict() for item in self.coverage],
            "status_counts_by_arm": {key: dict(sorted(value.items())) for key, value in sorted(self.status_counts_by_arm.items())},
            "predictive_metrics": [item.to_dict() for item in self.predictive_metrics],
            "failures": [item.to_dict() for item in self.failures],
            "excluded_counts": dict(sorted(self.excluded_counts.items())),
            "runtime_assumptions": dict(sorted(self.runtime_assumptions.items())),
            "fingerprint": self.fingerprint,
        }


def _fold_metric_summary(arm_id: str, metric_name: str, folds: Sequence[SyntheticFoldArtifact]) -> SyntheticFoldMetricSummary:
    measured: list[tuple[str, float]] = []
    unavailable = 0
    reasons: list[str] = []
    for fold in folds:
        item = next((metric for metric in fold.metrics if metric.name == metric_name), None)
        if item is not None and item.status == "measured" and item.value is not None:
            measured.append((fold.fold_id, float(item.value)))
        else:
            unavailable += 1
            if item is not None and item.reason:
                reasons.append(f"{fold.fold_id}: {item.reason}")
            elif fold.unavailable_reasons:
                reasons.extend(f"{fold.fold_id}: {reason}" for reason in fold.unavailable_reasons)
            else:
                reasons.append(f"{fold.fold_id}: metric unavailable")
    if not measured:
        return SyntheticFoldMetricSummary(arm_id, metric_name, 0, unavailable, tuple(reasons), None, None, None, None)
    values = [value for _, value in measured]
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    worst = max(measured, key=lambda pair: pair[1]) if metric_name in _LOWER_IS_BETTER else min(measured, key=lambda pair: pair[1])
    return SyntheticFoldMetricSummary(arm_id, metric_name, len(measured), unavailable, tuple(reasons), mean, variance, worst[0], worst[1])


def _coverage(arm: SyntheticArmArtifact) -> tuple[SyntheticCoverageCell, ...]:
    cells: list[SyntheticCoverageCell] = []
    for fold in arm.fold_results:
        denominator = len(fold.row_artifacts)
        counts: dict[tuple[str, str], int] = {}
        for row in fold.row_artifacts:
            key = (row.split, row.assessment_status)
            counts[key] = counts.get(key, 0) + 1
        for (split, status), count in sorted(counts.items()):
            cells.append(SyntheticCoverageCell(arm.arm_id.value, fold.fold_id, split, status, count, denominator))
    return tuple(cells)


def _status_counts(arm: SyntheticArmArtifact) -> dict[str, int]:
    result: dict[str, int] = {}
    for fold in arm.fold_results:
        for row in fold.row_artifacts:
            result[row.assessment_status] = result.get(row.assessment_status, 0) + 1
    return dict(sorted(result.items()))


def _predictive_metrics(report: SyntheticEvaluationReport, arm: SyntheticArmArtifact) -> tuple[SyntheticMetric, ...]:
    if arm.arm_id.value != "synthetic_numerical_control":
        return tuple(_metric(name, "unavailable", None, 0, "per-row numerical probabilities are unavailable for this arm") for name in _PREDICTIVE_METRICS)
    outcomes = {item.row_id: item.label for item in report.outcomes}
    pairs = [(row.probability, outcomes[row.row_id]) for fold in arm.fold_results for row in fold.row_artifacts if row.split == "test" and row.target_status == "available" and row.probability is not None and row.row_id in outcomes]
    if not pairs:
        return tuple(_metric(name, "unavailable", None, 0, "no joined test probabilities and outcomes") for name in _PREDICTIVE_METRICS)
    probabilities = [pair[0] for pair in pairs]
    labels = [pair[1] for pair in pairs]
    values = {
        "log_loss": log_loss(probabilities, labels),
        "brier": brier_score(probabilities, labels),
        "balanced_accuracy": balanced_accuracy(probabilities, labels),
        "ece": expected_calibration_error(probabilities, labels),
    }
    return tuple(values[name] for name in _PREDICTIVE_METRICS)


def build_synthetic_stability_report(report: SyntheticEvaluationReport) -> SyntheticStabilityReport:
    """Summarize a runner report without changing or reinterpreting it."""
    source = report.fingerprint
    summaries = tuple(summary for arm in report.arms for name in _PREDICTIVE_METRICS + ("coverage",) for summary in (_fold_metric_summary(arm.arm_id.value, name, arm.fold_results),))
    coverage = tuple(cell for arm in report.arms for cell in _coverage(arm))
    statuses = {arm.arm_id.value: _status_counts(arm) for arm in report.arms}
    predictive = _predictive_metrics(report, next(arm for arm in report.arms if arm.arm_id.value == "synthetic_numerical_control"))
    failures: list[SyntheticFailureSummary] = []
    for arm in report.arms:
        for fold in arm.fold_results:
            unavailable = [metric for metric in fold.metrics if metric.status != "measured"]
            reasons = list(fold.unavailable_reasons) + [metric.reason for metric in unavailable if metric.reason]
            if fold.status != "measured" or unavailable:
                failures.append(SyntheticFailureSummary(arm.arm_id.value, fold.fold_id, fold.status, fold.status == "measured" and bool(unavailable), len(unavailable), tuple(reasons)))
    excluded: dict[str, int] = {}
    for row in report.rows:
        if row.split in _EXCLUDED_SPLITS:
            key = f"{row.split}:{row.target_status}"
            excluded[key] = excluded.get(key, 0) + 1
    runtime = {"latency": "unknown_not_observed_offline", "usage": "unknown_not_observed_offline", "cost": "unknown_not_observed_offline"}
    base = {
        "source_fingerprint": source,
        "metric_summaries": [item.to_dict() for item in summaries],
        "coverage": [item.to_dict() for item in coverage],
        "status_counts_by_arm": statuses,
        "predictive_metrics": [item.to_dict() for item in predictive],
        "failures": [item.to_dict() for item in failures],
        "excluded_counts": excluded,
        "runtime_assumptions": runtime,
    }
    return SyntheticStabilityReport(source, summaries, coverage, statuses, predictive, tuple(failures), excluded, runtime, _fingerprint(base))


def verify_synthetic_stability_replay(first: SyntheticStabilityReport, second: SyntheticStabilityReport) -> bool:
    return first.fingerprint == second.fingerprint and first.to_dict() == second.to_dict()


__all__ = [
    "REPORT_SCHEMA",
    "SyntheticFoldMetricSummary",
    "SyntheticCoverageCell",
    "SyntheticFailureSummary",
    "SyntheticStabilityReport",
    "build_synthetic_stability_report",
    "verify_synthetic_stability_replay",
]
