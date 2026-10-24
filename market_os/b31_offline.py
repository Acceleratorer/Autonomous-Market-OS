"""Pure, fixture-safe foundations for a future B3.1 offline evaluation.

This module only validates and represents local artifacts. It has no transport,
provider, credential, market-data, execution, signal, or paper-trading path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
from typing import Any, Iterable, Mapping, Sequence

_MINUTE_MS = 60_000
_HORIZON_MS = 5 * _MINUTE_MS
_DIGEST_LENGTH = 64


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _digest(value: str, field: str) -> str:
    if not isinstance(value, str) or len(value) != _DIGEST_LENGTH or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field} must be a lowercase SHA-256 fingerprint")
    return value


def _finite(value: float, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{field} must be finite")
    return float(value)


class DatasetClass(str, Enum):
    SMOKE = "smoke"
    RESEARCH = "research"


class CoverageStatus(str, Enum):
    CONTINUOUS = "continuous"
    GAPPED = "gapped"
    UNAVAILABLE = "unavailable"


class TargetStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class EvidenceState(str, Enum):
    USABLE = "usable"
    MISSING = "missing"
    ABSTAINED = "abstained"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    CONTRADICTORY = "contradictory"


class CalibrationMethod(str, Enum):
    ONE_BIN = "one_bin"
    PLATT = "platt_logistic"
    ISOTONIC = "isotonic"


B31_TARGET_VERSION = "btc.b2.close-return-5m.v1"
UNKNOWN_NOT_OBSERVED_OFFLINE = "unknown_not_observed_offline"


@dataclass(frozen=True)
class DatasetRow:
    open_time_ms: int
    row_fingerprint: str
    target_end_ms: int | None = None
    label: bool | None = None

    def __post_init__(self) -> None:
        if isinstance(self.open_time_ms, bool) or self.open_time_ms < 0 or self.open_time_ms % _MINUTE_MS:
            raise ValueError("row time must be an aligned UTC millisecond timestamp")
        _digest(self.row_fingerprint, "row_fingerprint")
        if self.label is not None and type(self.label) is not bool:
            raise ValueError("label must be bool when present")
        if self.target_end_ms is not None:
            if self.target_end_ms != self.open_time_ms + _HORIZON_MS:
                raise ValueError("target_end_ms must be exactly five minutes after row time")
            if self.target_end_ms % _MINUTE_MS:
                raise ValueError("target_end_ms must be minute aligned")


@dataclass(frozen=True)
class DatasetIdentity:
    dataset_revision: str
    symbol: str
    interval: str
    start_ms: int
    end_ms: int
    row_count: int
    raw_fingerprint: str
    provenance_fingerprint: str
    replay_fingerprint: str
    coverage_status: CoverageStatus | str
    gap_count: int
    dataset_class: DatasetClass | str

    def __post_init__(self) -> None:
        if not self.dataset_revision.strip():
            raise ValueError("dataset_revision is required")
        if (self.symbol, self.interval) != ("BTCUSDT", "1m"):
            raise ValueError("B3.1 foundation is restricted to BTCUSDT 1m")
        if self.start_ms < 0 or self.end_ms <= self.start_ms or self.start_ms % _MINUTE_MS or self.end_ms % _MINUTE_MS:
            raise ValueError("UTC bounds must be aligned and end after start")
        if self.row_count < 0 or self.gap_count < 0:
            raise ValueError("row_count and gap_count must be non-negative")
        for name in ("raw_fingerprint", "provenance_fingerprint", "replay_fingerprint"):
            _digest(getattr(self, name), name)
        try:
            dataset_class = DatasetClass(self.dataset_class)
        except ValueError as exc:
            raise ValueError("unsupported dataset class") from exc
        object.__setattr__(self, "dataset_class", dataset_class)
        try:
            coverage = CoverageStatus(self.coverage_status)
        except ValueError as exc:
            raise ValueError("unsupported coverage status")
        object.__setattr__(self, "coverage_status", coverage)
        if coverage is CoverageStatus.CONTINUOUS and self.gap_count:
            raise ValueError("continuous coverage cannot report gaps")
        if self.dataset_class is DatasetClass.RESEARCH and (coverage is not CoverageStatus.CONTINUOUS or self.gap_count):
            raise ValueError("research dataset requires continuous coverage and no gaps")

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_revision": self.dataset_revision,
            "symbol": self.symbol,
            "interval": self.interval,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "row_count": self.row_count,
            "raw_fingerprint": self.raw_fingerprint,
            "provenance_fingerprint": self.provenance_fingerprint,
            "replay_fingerprint": self.replay_fingerprint,
            "coverage_status": self.coverage_status.value,
            "gap_count": self.gap_count,
            "dataset_class": self.dataset_class.value,
        }


def build_dataset_identity(
    *,
    dataset_revision: str,
    symbol: str,
    interval: str,
    rows: Sequence[DatasetRow],
    start_ms: int,
    end_ms: int,
    raw_fingerprint: str,
    provenance_fingerprint: str,
    dataset_class: DatasetClass,
) -> DatasetIdentity:
    ordered = sorted(rows, key=lambda row: row.open_time_ms)
    expected = list(range(start_ms, end_ms, _MINUTE_MS))
    actual = [row.open_time_ms for row in ordered]
    gap_count = len(set(expected) - set(actual))
    if len(actual) != len(set(actual)):
        raise ValueError("dataset rows contain duplicate timestamps")
    coverage_status = CoverageStatus.CONTINUOUS if not gap_count and actual == expected else CoverageStatus.GAPPED
    replay = _fingerprint(
        {
            "revision": dataset_revision,
            "rows": [row.__dict__ for row in ordered],
            "start_ms": start_ms,
            "end_ms": end_ms,
        }
    )
    return DatasetIdentity(
        dataset_revision,
        symbol,
        interval,
        start_ms,
        end_ms,
        len(ordered),
        raw_fingerprint,
        provenance_fingerprint,
        replay,
        coverage_status,
        gap_count,
        dataset_class,
    )


@dataclass(frozen=True)
class FeatureRowIdentity:
    dataset_revision: str
    feature_close_time_ms: int
    input_fingerprint: str

    def __post_init__(self) -> None:
        if not self.dataset_revision.strip() or self.feature_close_time_ms < 0 or self.feature_close_time_ms % _MINUTE_MS:
            raise ValueError("feature-row identity is incomplete")
        _digest(self.input_fingerprint, "input_fingerprint")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "FeatureRowIdentity":
        _validate_future_free_mapping(value)
        return cls(
            str(value["dataset_revision"]),
            int(value["feature_close_time_ms"]),
            str(value["input_fingerprint"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_revision": self.dataset_revision,
            "feature_close_time_ms": self.feature_close_time_ms,
            "input_fingerprint": self.input_fingerprint,
        }


_LINEAGE_IDENTITY_FIELDS = frozenset({"target_definition_id", "target_version"})
_FORBIDDEN_FEATURE_FIELD_NAMES = frozenset(
    {
        "realized_label",
        "realized_labels",
        "target_label",
        "target_labels",
        "target_row",
        "target_rows",
        "future_target",
        "future_targets",
        "future_target_row",
        "future_target_rows",
        "future_return",
        "future_returns",
        "target_return",
        "target_returns",
        "target_fingerprint",
        "fills",
        "fill",
        "account",
        "account_state",
        "portfolio",
        "portfolio_state",
        "position",
        "positions",
        "orders",
        "order",
        "trades",
        "trade",
        "execution",
        "executions",
    }
)


def _validate_future_free_mapping(value: Mapping[str, Any]) -> None:
    """Reject outcome, execution, and future-derived fields in feature mappings."""
    for raw_key in value:
        key = str(raw_key).strip().lower()
        if key in _LINEAGE_IDENTITY_FIELDS:
            continue
        if (
            "future" in key
            or "realized" in key
            or "target" in key
            or key in _FORBIDDEN_FEATURE_FIELD_NAMES
            or any(token in key for token in ("fill", "account", "portfolio", "position", "order", "trade", "execution"))
        ):
            raise ValueError(f"future-derived fields are forbidden in feature identity: {raw_key!r}")


@dataclass(frozen=True)
class TargetJoin:
    feature: FeatureRowIdentity
    target_version: str
    status: TargetStatus
    target_return: float | None
    label: str | None
    target_end_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature.__dict__,
            "target_version": self.target_version,
            "status": self.status.value,
            "target_return": self.target_return,
            "label": self.label,
            "target_end_ms": self.target_end_ms,
        }


def join_b2_target(
    feature: FeatureRowIdentity,
    *,
    close: float,
    target_close: float | None,
    target_available: bool,
    target_end_ms: int | None = None,
) -> TargetJoin:
    close_value = _finite(close, "close")
    if close_value <= 0:
        raise ValueError("close must be positive")
    end_ms = feature.feature_close_time_ms + _HORIZON_MS if target_end_ms is None else target_end_ms
    if end_ms != feature.feature_close_time_ms + _HORIZON_MS:
        raise ValueError("B2 target must end exactly five minutes after the feature")
    if not target_available or target_close is None:
        return TargetJoin(feature, B31_TARGET_VERSION, TargetStatus.UNAVAILABLE, None, None, end_ms)
    target_value = _finite(target_close, "target_close")
    if target_value <= 0:
        raise ValueError("target_close must be positive")
    result = math.log(target_value / close_value)
    return TargetJoin(
        feature,
        B31_TARGET_VERSION,
        TargetStatus.AVAILABLE,
        result,
        "positive" if result > 0 else "non_positive",
        end_ms,
    )


@dataclass(frozen=True)
class FoldSpec:
    fold_id: str
    train: tuple[int, int]
    validation: tuple[int, int] | None
    calibration: tuple[int, int]
    test: tuple[int, int]

    def __post_init__(self) -> None:
        if not self.fold_id.strip():
            raise ValueError("fold_id is required")
        ranges = [self.train, *([self.validation] if self.validation else []), self.calibration, self.test]
        previous_end: int | None = None
        for start, end in ranges:
            if start < 0 or end <= start or start % _MINUTE_MS or end % _MINUTE_MS:
                raise ValueError("fold ranges must be aligned UTC intervals")
            if previous_end is not None and start < previous_end:
                raise ValueError("fold ranges must be chronological and non-overlapping")
            previous_end = end


@dataclass(frozen=True)
class FoldAssignment:
    row_fingerprint: str
    split: str
    reason: str


@dataclass(frozen=True)
class FoldResult:
    fold_id: str
    assignments: tuple[FoldAssignment, ...]
    split_fingerprint: str
    status_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fold_id": self.fold_id,
            "assignments": [assignment.__dict__ for assignment in self.assignments],
            "split_fingerprint": self.split_fingerprint,
            "status_counts": dict(self.status_counts),
        }


@dataclass(frozen=True)
class FoldSet:
    folds: tuple[FoldResult, ...]
    split_fingerprint: str
    status_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "folds": [fold.to_dict() for fold in self.folds],
            "split_fingerprint": self.split_fingerprint,
            "status_counts": dict(self.status_counts),
        }


def build_chronological_folds(
    rows: Sequence[DatasetRow],
    specs: Sequence[FoldSpec],
    *,
    purge_ms: int = _HORIZON_MS,
    embargo_ms: int = _HORIZON_MS,
    shuffle: bool = False,
) -> FoldSet:
    if shuffle:
        raise ValueError("random shuffle is forbidden for chronological folds")
    if purge_ms != _HORIZON_MS or embargo_ms != _HORIZON_MS:
        raise ValueError("B3.1 foundation purge and embargo are fixed at five minutes")
    if not specs:
        raise ValueError("at least one FoldSpec is required")
    row_times = [row.open_time_ms for row in rows]
    row_fingerprints = [row.row_fingerprint for row in rows]
    if len(row_times) != len(set(row_times)):
        raise ValueError("fold rows contain duplicate timestamps")
    if len(row_fingerprints) != len(set(row_fingerprints)):
        raise ValueError("fold rows contain duplicate fingerprints")
    configured_ranges = [interval for spec in specs for interval in (
        [spec.train] + ([spec.validation] if spec.validation else []) + [spec.calibration, spec.test]
    )]
    for row in rows:
        if not any(start <= row.open_time_ms < end for start, end in configured_ranges):
            raise ValueError("fold row is outside configured ranges")
    results: list[FoldResult] = []
    for spec in specs:
        assignments: list[FoldAssignment] = []
        ranges: list[tuple[str, tuple[int, int]]] = [("train", spec.train)]
        if spec.validation is not None:
            ranges.append(("validation", spec.validation))
        ranges.extend((("calibration", spec.calibration), ("test", spec.test)))
        boundaries = [start for _name, (start, _end) in ranges[1:]]
        for row in sorted(rows, key=lambda item: item.open_time_ms):
            split = "outside"
            reason = "outside configured fold ranges"
            for name, (start, end) in ranges:
                if start <= row.open_time_ms < end:
                    split, reason = name, f"chronological {name} interval"
                    break
            if split != "outside" and row.target_end_ms is not None:
                if any(row.target_end_ms >= boundary > row.open_time_ms for boundary in boundaries):
                    split, reason = "purged", "target overlaps a split boundary"
                elif any(boundary <= row.open_time_ms < boundary + embargo_ms for boundary in boundaries):
                    split, reason = "embargoed", "five-minute post-boundary embargo"
            assignments.append(FoldAssignment(row.row_fingerprint, split, reason))
        counts: dict[str, int] = {}
        for item in assignments:
            counts[item.split] = counts.get(item.split, 0) + 1
        fingerprint = _fingerprint(
            {
                "fold_id": spec.fold_id,
                "assignments": [item.__dict__ for item in assignments],
                "purge_ms": purge_ms,
                "embargo_ms": embargo_ms,
            }
        )
        results.append(FoldResult(spec.fold_id, tuple(assignments), fingerprint, dict(sorted(counts.items()))))
    aggregate: dict[str, int] = {}
    for fold in results:
        for status, count in fold.status_counts.items():
            aggregate[status] = aggregate.get(status, 0) + count
    return FoldSet(
        tuple(results),
        _fingerprint([fold.to_dict() for fold in results]),
        dict(sorted(aggregate.items())),
    )


@dataclass(frozen=True)
class CalibrationConfig:
    method: CalibrationMethod
    isotonic_min_rows: int | None = None
    isotonic_approved: bool = False

    def __post_init__(self) -> None:
        try:
            method = CalibrationMethod(self.method)
        except ValueError as exc:
            raise ValueError("unsupported calibration method") from exc
        object.__setattr__(self, "method", method)
        if method is CalibrationMethod.ISOTONIC and (
            not self.isotonic_approved or self.isotonic_min_rows is None or self.isotonic_min_rows <= 0
        ):
            raise ValueError("isotonic calibration requires an approved positive threshold")
        if self.isotonic_min_rows is not None and self.isotonic_min_rows <= 0:
            raise ValueError("isotonic_min_rows must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method.value,
            "isotonic_min_rows": self.isotonic_min_rows,
            "isotonic_approved": self.isotonic_approved,
        }


@dataclass(frozen=True)
class CalibrationArtifact:
    config: CalibrationConfig
    status: str
    calibration_row_ids: tuple[str, ...]
    test_row_ids: tuple[str, ...]
    rate: float | None = None
    reason: str | None = None

    def predict(self, score: float) -> float:
        if self.status != "measured" or self.rate is None:
            raise ValueError("calibration is unavailable")
        return self.rate

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": self.config.to_dict(),
            "status": self.status,
            "calibration_row_ids": list(self.calibration_row_ids),
            "test_row_ids": list(self.test_row_ids),
            "rate": self.rate,
            "reason": self.reason,
        }


def fit_calibrator(
    scores: Mapping[str, float],
    labels: Mapping[str, bool],
    config: CalibrationConfig,
    *,
    calibration_row_ids: Sequence[str],
    test_row_ids: Sequence[str],
) -> CalibrationArtifact:
    calibration_ids = tuple(calibration_row_ids)
    test_ids = tuple(test_row_ids)
    if len(calibration_ids) != len(set(calibration_ids)) or len(test_ids) != len(set(test_ids)):
        raise ValueError("calibration and test row IDs must be unique")
    if set(calibration_ids) & set(test_ids):
        raise ValueError("calibration and test rows overlap")
    if config.method is CalibrationMethod.ISOTONIC:
        if len(calibration_ids) < (config.isotonic_min_rows or 0):
            return CalibrationArtifact(config, "unavailable", calibration_ids, test_ids, reason="approved isotonic threshold not met")
    if config.method is CalibrationMethod.PLATT:
        return CalibrationArtifact(config, "unavailable", calibration_ids, test_ids, reason="Platt fitting is deferred in the foundation milestone")
    if not calibration_ids or any(row_id not in scores or row_id not in labels for row_id in calibration_ids):
        return CalibrationArtifact(config, "unavailable", calibration_ids, test_ids, reason="calibration rows are incomplete")
    rate = sum(bool(labels[row_id]) for row_id in calibration_ids) / len(calibration_ids)
    return CalibrationArtifact(config, "measured", calibration_ids, test_ids, rate)


@dataclass(frozen=True)
class FusionInput:
    name: str
    family: str
    value: float | None
    state: EvidenceState | str
    dimensions: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.family.strip():
            raise ValueError("fusion input name and family are required")
        try:
            state = EvidenceState(self.state)
        except ValueError as exc:
            raise ValueError("unsupported fusion input state") from exc
        object.__setattr__(self, "state", state)
        if state is not EvidenceState.USABLE and (self.value is not None or self.dimensions):
            raise ValueError("non-usable fusion input cannot carry numeric values or dimensions")
        if self.value is not None:
            _finite(self.value, f"{self.name}.value")
        for key, value in self.dimensions.items():
            _finite(value, f"{self.name}.{key}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "family": self.family,
            "value": self.value,
            "state": self.state.value,
            "dimensions": dict(sorted(self.dimensions.items())),
        }


@dataclass(frozen=True)
class EncodedFusionInputs:
    values: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {"values": dict(self.values)}


def encode_fusion_inputs(inputs: Iterable[FusionInput]) -> EncodedFusionInputs:
    values: dict[str, float] = {}
    for item in inputs:
        item_keys = {item.name, f"{item.name}__missing", *(f"{item.name}__{key}" for key in item.dimensions)}
        if len(item_keys) != len(item.dimensions) + 2 or item_keys & values.keys():
            raise ValueError("fusion input encoded names must be unique")
        if item.value is not None:
            values[item.name] = float(item.value)
        else:
            values[item.name] = 0.0
        values[f"{item.name}__missing"] = 0.0 if item.state is EvidenceState.USABLE else 1.0
        for key, value in sorted(item.dimensions.items()):
            values[f"{item.name}__{key}"] = float(value)
    return EncodedFusionInputs(dict(sorted(values.items())))


@dataclass(frozen=True)
class RegularizedLogisticFusionConfig:
    l2_lambda: float | None = None
    feature_families: tuple[str, ...] = ()
    interactions: bool = False

    def __post_init__(self) -> None:
        if self.l2_lambda is not None and (not math.isfinite(self.l2_lambda) or self.l2_lambda < 0):
            raise ValueError("l2_lambda must be non-negative when supplied")

    def to_dict(self) -> dict[str, Any]:
        return {
            "l2_lambda": self.l2_lambda,
            "feature_families": list(self.feature_families),
            "interactions": self.interactions,
        }


@dataclass(frozen=True)
class FusionFitArtifact:
    config: RegularizedLogisticFusionConfig
    status: str
    train_row_ids: tuple[str, ...]
    validation_row_ids: tuple[str, ...]
    test_row_ids: tuple[str, ...]
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": self.config.to_dict(),
            "status": self.status,
            "train_row_ids": list(self.train_row_ids),
            "validation_row_ids": list(self.validation_row_ids),
            "test_row_ids": list(self.test_row_ids),
            "reason": self.reason,
        }


def fit_regularized_logistic_fusion(
    config: RegularizedLogisticFusionConfig,
    *,
    train_row_ids: Sequence[str],
    validation_row_ids: Sequence[str] = (),
    test_row_ids: Sequence[str] = (),
) -> FusionFitArtifact:
    train_ids = tuple(train_row_ids)
    validation_ids = tuple(validation_row_ids)
    test_ids = tuple(test_row_ids)
    if any(len(ids) != len(set(ids)) for ids in (train_ids, validation_ids, test_ids)):
        raise ValueError("fusion row IDs must be unique within each split")
    if set(train_ids) & (set(validation_ids) | set(test_ids)) or set(validation_ids) & set(test_ids):
        raise ValueError("fusion fit and evaluation rows overlap")
    return FusionFitArtifact(
        config,
        "unavailable",
        train_ids,
        validation_ids,
        test_ids,
        "fusion fitting is deferred in the foundation milestone",
    )


@dataclass(frozen=True)
class MetricResult:
    name: str
    status: str
    value: float | None
    n: int
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status, "value": self.value, "n": self.n, "reason": self.reason}


@dataclass(frozen=True)
class OfflineRuntimeAssumptions:
    latency: str = UNKNOWN_NOT_OBSERVED_OFFLINE
    usage: str = UNKNOWN_NOT_OBSERVED_OFFLINE
    cost: str = UNKNOWN_NOT_OBSERVED_OFFLINE

    def to_dict(self) -> dict[str, str]:
        return {"latency": self.latency, "usage": self.usage, "cost": self.cost}


def _metric_inputs(
    probabilities: Sequence[float],
    labels: Sequence[bool],
    *,
    minimum: int = 2,
) -> tuple[list[float], list[bool]] | MetricResult:
    if len(probabilities) != len(labels):
        raise ValueError("probabilities and labels must have equal length")
    if any(type(label) is not bool for label in labels):
        raise ValueError("labels must be bool")
    values = [_finite(value, "probability") for value in probabilities]
    if any(value < 0.0 or value > 1.0 for value in values):
        raise ValueError("probabilities must be within [0, 1]")
    if len(probabilities) < minimum or len(set(labels)) < 2:
        return MetricResult("metric", "unavailable", None, len(labels), "insufficient rows or label support")
    return values, list(labels)


def log_loss(probabilities: Sequence[float], labels: Sequence[bool]) -> MetricResult:
    prepared = _metric_inputs(probabilities, labels)
    if isinstance(prepared, MetricResult):
        return MetricResult("log_loss", prepared.status, prepared.value, prepared.n, prepared.reason)
    values, truth = prepared
    safe = [min(1.0 - 1e-15, max(1e-15, p)) for p in values]
    value = sum(-math.log(p if actual else 1.0 - p) for p, actual in zip(safe, truth)) / len(truth)
    return MetricResult("log_loss", "measured", value, len(truth))


def brier_score(probabilities: Sequence[float], labels: Sequence[bool]) -> MetricResult:
    prepared = _metric_inputs(probabilities, labels)
    if isinstance(prepared, MetricResult):
        return MetricResult("brier", prepared.status, prepared.value, prepared.n, prepared.reason)
    values, truth = prepared
    value = sum((p - float(actual)) ** 2 for p, actual in zip(values, truth)) / len(truth)
    return MetricResult("brier", "measured", value, len(truth))


def balanced_accuracy(probabilities: Sequence[float], labels: Sequence[bool]) -> MetricResult:
    prepared = _metric_inputs(probabilities, labels)
    if isinstance(prepared, MetricResult):
        return MetricResult("balanced_accuracy", prepared.status, prepared.value, prepared.n, prepared.reason)
    values, truth = prepared
    predicted = [p >= 0.5 for p in values]
    recalls = []
    for category in (False, True):
        relevant = [prediction == actual for prediction, actual in zip(predicted, truth) if actual is category]
        recalls.append(sum(relevant) / len(relevant))
    return MetricResult("balanced_accuracy", "measured", sum(recalls) / 2.0, len(truth))


def calibration_bins(probabilities: Sequence[float], labels: Sequence[bool], *, bin_count: int = 10) -> MetricResult:
    if bin_count <= 0:
        raise ValueError("bin_count must be positive")
    prepared = _metric_inputs(probabilities, labels)
    if isinstance(prepared, MetricResult):
        return MetricResult("calibration_bins", prepared.status, prepared.value, prepared.n, prepared.reason)
    values, truth = prepared
    error = 0.0
    for index in range(bin_count):
        members = [
            (probability, actual)
            for probability, actual in zip(values, truth)
            if min(bin_count - 1, int(probability * bin_count)) == index
        ]
        if members:
            mean_probability = sum(probability for probability, _ in members) / len(members)
            mean_label = sum(actual for _, actual in members) / len(members)
            error += len(members) / len(truth) * abs(mean_probability - mean_label)
    return MetricResult("calibration_bins", "measured", error, len(truth))


def expected_calibration_error(probabilities: Sequence[float], labels: Sequence[bool], *, bin_count: int = 10) -> MetricResult:
    result = calibration_bins(probabilities, labels, bin_count=bin_count)
    return MetricResult("ece", result.status, result.value, result.n, result.reason)


def coverage_status_counts(statuses: Iterable[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for status in statuses:
        result[status] = result.get(status, 0) + 1
    return dict(sorted(result.items()))


def fold_variance(values: Sequence[float]) -> MetricResult:
    if len(values) < 2:
        return MetricResult("fold_variance", "unavailable", None, len(values), "at least two folds are required")
    mean = sum(values) / len(values)
    return MetricResult("fold_variance", "measured", sum((value - mean) ** 2 for value in values) / len(values), len(values))


@dataclass(frozen=True)
class MatchedRowAccounting:
    left_count: int
    right_count: int
    intersection_count: int


def matched_row_accounting(left_ids: Iterable[str], right_ids: Iterable[str]) -> MatchedRowAccounting:
    left, right = set(left_ids), set(right_ids)
    return MatchedRowAccounting(len(left), len(right), len(left & right))


def replay_fingerprint(*artifacts: Mapping[str, Any]) -> str:
    canonical_artifacts = [dict(sorted(artifact.items())) for artifact in artifacts]
    return _fingerprint({"artifacts": sorted(canonical_artifacts, key=_canonical)})
