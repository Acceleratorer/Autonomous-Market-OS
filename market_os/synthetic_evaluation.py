"""Pure, deterministic synthetic-only B3.1 evaluation runner.

The module consumes only the frozen offline plan, its synthetic compilation and
materialization, immutable synthetic rows, and separately supplied outcomes.
It contains no transport, provider, credential, execution, or research fitting
path. Jev assessment fields are coverage diagnostics only.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass, replace
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence
from types import MappingProxyType

from .evaluation_protocol import (
    B31_TARGET_VERSION,
    CalibrationConfig,
    CalibrationMethod,
    DatasetClass,
    DatasetRow,
    EvaluationPlanStatus,
    FeatureRowIdentity,
    MetricResult,
    OfflineEvaluationPlan,
    balanced_accuracy,
    brier_score,
    compile_synthetic_evaluation_plan,
    expected_calibration_error,
    fit_calibrator,
    log_loss,
    matched_row_accounting,
    materialize_synthetic_evaluation_plan,
    recommended_evaluation_folds,
    SyntheticMaterialization,
    SyntheticPlanCompilation,
    TargetStatus,
)
from .btc_question_evaluation import STATUS_PRECEDENCE


RUNNER_SCHEMA = "market-os.b3-1.synthetic-evaluation-run@v1"
RUNNER_VERSION = "v1"
_PURGE_EMBARGO_MS = 300_000
_MINUTE_MS = 60_000
_BLOCK_IDS = frozenset(range(1, 11))
_ASSESSMENT_STATUSES = tuple(STATUS_PRECEDENCE) + ("missing",)
_FORBIDDEN_SYNTHETIC_IDENTITIES = ("binance", "provider", "endpoint", "openai", "typesafe")


def _canonical(value: Any) -> str:
    def plain(item: Any) -> Any:
        if isinstance(item, Enum):
            return item.value
        if is_dataclass(item):
            return {field.name: plain(getattr(item, field.name)) for field in fields(item)}
        if isinstance(item, Mapping):
            return {str(key): plain(item[key]) for key in sorted(item, key=str)}
        if isinstance(item, (set, frozenset)):
            return sorted((plain(child) for child in item), key=lambda child: json.dumps(child, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
        if isinstance(item, (list, tuple)):
            return [plain(child) for child in item]
        return item

    return json.dumps(plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _fingerprinted_fold(artifact: "SyntheticFoldArtifact") -> "SyntheticFoldArtifact":
    return replace(artifact, fingerprint=_sha({**artifact.to_dict(), "fingerprint": None}))


def _nonempty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")
    if "://" in value or "\\" in value:
        raise ValueError(f"{field_name} cannot contain a URL or path")
    return value


def _stable_reference(value: str, field_name: str) -> str:
    value = _nonempty(value, field_name)
    if re.fullmatch(r"synthetic-[A-Za-z0-9._-]{1,120}", value) is None:
        raise ValueError(f"{field_name} must be a bounded synthetic reference")
    if any(token in value.lower() for token in _FORBIDDEN_SYNTHETIC_IDENTITIES):
        raise ValueError(f"{field_name} contains a forbidden external identity")
    return value


def _bounded_token(value: str, field_name: str) -> str:
    """Validate a display-only synthetic token without admitting free context."""
    value = _nonempty(value, field_name)
    lowered = value.lower()
    if len(value) > 120 or re.fullmatch(r"[A-Za-z0-9._:-]+", value) is None:
        raise ValueError(f"{field_name} must be a bounded synthetic token")
    if any(token in lowered for token in _FORBIDDEN_SYNTHETIC_IDENTITIES):
        raise ValueError(f"{field_name} contains a forbidden external identity")
    return value


def _synthetic_token(value: str, field_name: str) -> str:
    value = _bounded_token(value, field_name)
    if not value.startswith("synthetic-"):
        raise ValueError(f"{field_name} must be a synthetic reference")
    return value


def _fingerprint_reference(value: str, field_name: str) -> str:
    if isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value):
        return value
    return _synthetic_token(value, field_name)


def _digest(value: str, field_name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 fingerprint")
    return value


def _finite(value: float, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{field_name} must be finite")
    return float(value)


class SyntheticArmId(str, Enum):
    NUMERICAL_CONTROL = "synthetic_numerical_control"
    JEV_COVERAGE = "synthetic_jev_coverage"
    FUSION_PLACEHOLDER = "synthetic_fusion_placeholder"


class SyntheticArmStatus(str, Enum):
    MEASURED = "measured"
    UNAVAILABLE = "unavailable"
    UNAVAILABLE_DEFERRED = "unavailable_deferred"


@dataclass(frozen=True)
class SyntheticTargetJoin:
    """B2 identity only; a realized label is held by SyntheticOutcome."""

    feature_identity: str
    target_version: str = B31_TARGET_VERSION
    status: TargetStatus | str = TargetStatus.UNAVAILABLE
    target_end_ms: int = 0

    def __post_init__(self) -> None:
        _digest(self.feature_identity, "target feature identity")
        if self.target_version != B31_TARGET_VERSION:
            raise ValueError("synthetic target must use the B2 five-minute identity")
        try:
            status = TargetStatus(self.status)
        except ValueError as exc:
            raise ValueError("unsupported synthetic target status") from exc
        object.__setattr__(self, "status", status)
        if isinstance(self.target_end_ms, bool) or self.target_end_ms < 0 or self.target_end_ms % _MINUTE_MS:
            raise ValueError("target_end_ms must be a minute-aligned timestamp")


@dataclass(frozen=True)
class SyntheticAssessmentSummary:
    """Immutable coverage diagnostics; semantic distributions are omitted."""

    status: str
    response_fingerprints: tuple[str, ...] = ()
    evidence_disagreement: bool = False
    concentration_max: float | None = None
    diagnostic_ranking: tuple[str, ...] = ()
    provenance: str = "synthetic_only"

    def __post_init__(self) -> None:
        object.__setattr__(self, "response_fingerprints", tuple(self.response_fingerprints))
        object.__setattr__(self, "diagnostic_ranking", tuple(self.diagnostic_ranking))
        if self.provenance != "synthetic_only":
            raise ValueError("synthetic assessment provenance marker is required")
        if type(self.evidence_disagreement) is not bool:
            raise ValueError("evidence_disagreement must be bool")
        if self.status not in _ASSESSMENT_STATUSES[:-1]:
            raise ValueError("unsupported B3.1 assessment status")
        if len(self.response_fingerprints) > 64 or len(self.diagnostic_ranking) > 64:
            raise ValueError("assessment diagnostics are bounded")
        for fingerprint in self.response_fingerprints:
            _fingerprint_reference(fingerprint, "response_fingerprint")
        if self.concentration_max is not None:
            value = _finite(self.concentration_max, "concentration_max")
            if not 0.0 <= value <= 1.0:
                raise ValueError("concentration_max must be within [0, 1]")
        for item in self.diagnostic_ranking:
            _synthetic_token(item, "diagnostic_ranking entry")


@dataclass(frozen=True)
class SyntheticEvaluationRow:
    """Feature and recorded-assessment input; no realized outcome is stored."""

    row_id: str
    feature_identity: Any
    timestamp_ms: int
    target: SyntheticTargetJoin
    numerical_score: float | None
    source_fingerprint: str
    fixture_fingerprint: str
    assessment: SyntheticAssessmentSummary | None = None
    assessment_reference: str | None = None
    assessment_status: str | None = None
    provenance: str = "synthetic_only"

    def __post_init__(self) -> None:
        _stable_reference(self.row_id, "synthetic row_id")
        if not isinstance(self.target, SyntheticTargetJoin):
            raise ValueError("target must be a synthetic B2 target join")
        if self.assessment is not None and not isinstance(self.assessment, SyntheticAssessmentSummary):
            raise ValueError("assessment must be an immutable normalized diagnostic summary")
        if isinstance(self.timestamp_ms, bool) or self.timestamp_ms < 0 or self.timestamp_ms % _MINUTE_MS:
            raise ValueError("synthetic timestamp must be minute-aligned")
        if not isinstance(self.feature_identity, FeatureRowIdentity):
            raise ValueError("feature_identity must be a stable synthetic feature identity")
        dataset_revision = self.feature_identity.dataset_revision.lower()
        if re.fullmatch(r"synthetic-[A-Za-z0-9._-]{1,120}", dataset_revision) is None or any(token in dataset_revision for token in _FORBIDDEN_SYNTHETIC_IDENTITIES):
            raise ValueError("non-synthetic dataset revisions are forbidden")
        if self.provenance != "synthetic_only":
            raise ValueError("synthetic-only provenance marker is required")
        if self.feature_identity.feature_close_time_ms != self.timestamp_ms:
            raise ValueError("feature identity timestamp must match row timestamp")
        if self.target.feature_identity != self.feature_identity.input_fingerprint:
            raise ValueError("target join must use the feature identity")
        if self.target.status is TargetStatus.AVAILABLE and self.target.target_end_ms != self.timestamp_ms + _PURGE_EMBARGO_MS:
            raise ValueError("synthetic target must end five minutes after the feature")
        if self.target.status is TargetStatus.UNAVAILABLE and self.target.target_end_ms not in {0, self.timestamp_ms + _PURGE_EMBARGO_MS}:
            raise ValueError("unavailable synthetic target cannot carry another target end")
        _digest(self.source_fingerprint, "source_fingerprint")
        if self.source_fingerprint != self.feature_identity.input_fingerprint:
            raise ValueError("source fingerprint must match the synthetic feature fingerprint")
        _digest(self.fixture_fingerprint, "fixture_fingerprint")
        if self.numerical_score is not None:
            _finite(self.numerical_score, "numerical_score")
        status = self.assessment.status if self.assessment is not None else (self.assessment_status or "missing")
        if status not in _ASSESSMENT_STATUSES:
            raise ValueError("unsupported B3.1 assessment status")
        if self.assessment is not None:
            if not isinstance(self.assessment, SyntheticAssessmentSummary):
                raise ValueError("assessment must be an immutable normalized diagnostic summary")
            if self.assessment_reference is None or not self.assessment_reference.strip():
                raise ValueError("assessment_reference is required with a normalized assessment")
            _stable_reference(self.assessment_reference, "assessment_reference")
            if self.assessment_status is not None and self.assessment_status != self.assessment.status:
                raise ValueError("assessment_status disagrees with normalized assessment")
        elif status == "usable":
            raise ValueError("usable assessment status requires a normalized assessment and reference")
        elif self.assessment_reference is not None:
            raise ValueError("assessment_reference requires a normalized synthetic assessment")
        object.__setattr__(self, "assessment_status", status)

    @property
    def feature_fingerprint(self) -> str:
        return self.feature_identity.input_fingerprint

    @property
    def block_status(self) -> str:
        return "target_eligible" if self.target.status is TargetStatus.AVAILABLE else "target_unavailable"


@dataclass(frozen=True)
class SyntheticOutcome:
    """The only input record allowed to carry a realized synthetic label."""

    row_id: str
    label: bool

    def __post_init__(self) -> None:
        _stable_reference(self.row_id, "outcome row_id")
        if type(self.label) is not bool:
            raise ValueError("synthetic outcome label must be bool")


@dataclass(frozen=True)
class SyntheticMetric:
    name: str
    status: str
    value: float | None
    n: int
    reason: str | None = None

    def __post_init__(self) -> None:
        _bounded_token(self.name, "metric name")
        if self.status not in {"measured", "unavailable"}:
            raise ValueError("unsupported synthetic metric status")
        if isinstance(self.n, bool) or self.n < 0:
            raise ValueError("metric n must be non-negative")
        if self.value is not None:
            _finite(self.value, "metric value")
        if self.status == "measured" and self.value is None:
            raise ValueError("measured metric requires a value")
        if self.status == "unavailable" and not self.reason:
            raise ValueError("unavailable metric requires a reason")

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "market-os.b3-1.synthetic-metric@v1", "name": self.name, "status": self.status, "value": self.value, "n": self.n, "reason": self.reason}


@dataclass(frozen=True)
class SyntheticRowArtifact:
    row_id: str
    feature_fingerprint: str
    fold_id: str
    split: str
    target_status: str
    numerical_score_status: str
    assessment_status: str
    assessment_reference: str | None
    source_fingerprint: str
    fixture_fingerprint: str
    response_fingerprints: tuple[str, ...]
    disagreement: bool
    concentrated_valid: bool
    diagnostic_ranking: tuple[str, ...]
    probability: float | None = None
    assignment_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "market-os.b3-1.synthetic-row-artifact@v1",
            "synthetic_only": True,
            "row_id": self.row_id,
            "feature_fingerprint": self.feature_fingerprint,
            "fold_id": self.fold_id,
            "split": self.split,
            "target_status": self.target_status,
            "numerical_score_status": self.numerical_score_status,
            "assessment_status": self.assessment_status,
            "assessment_reference": self.assessment_reference,
            "source_fingerprint": self.source_fingerprint,
            "fixture_fingerprint": self.fixture_fingerprint,
            "response_fingerprints": list(self.response_fingerprints),
            "disagreement": self.disagreement,
            "concentrated_valid": self.concentrated_valid,
            "diagnostic_ranking": list(self.diagnostic_ranking),
            "probability": self.probability,
            "assignment_reason": self.assignment_reason,
        }


@dataclass(frozen=True)
class SyntheticFoldArtifact:
    fold_id: str
    status: str
    row_artifacts: tuple[SyntheticRowArtifact, ...]
    assessment_status_counts: Mapping[str, int]
    calibration_row_ids: tuple[str, ...]
    test_row_ids: tuple[str, ...]
    calibration_status: str
    calibration_method: str
    calibration_rate: float | None
    calibration_fingerprint: str
    metrics: tuple[SyntheticMetric, ...]
    unavailable_reasons: tuple[str, ...]
    fingerprint: str
    matched_row_accounting: Mapping[str, int] = field(default_factory=dict)
    row_count: int = 0
    target_eligible_row_count: int = 0
    numerical_score_eligible_row_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "row_artifacts", tuple(self.row_artifacts))
        object.__setattr__(self, "assessment_status_counts", MappingProxyType(dict(self.assessment_status_counts)))
        object.__setattr__(self, "calibration_row_ids", tuple(self.calibration_row_ids))
        object.__setattr__(self, "test_row_ids", tuple(self.test_row_ids))
        object.__setattr__(self, "metrics", tuple(self.metrics))
        object.__setattr__(self, "unavailable_reasons", tuple(self.unavailable_reasons))
        object.__setattr__(self, "matched_row_accounting", MappingProxyType(dict(self.matched_row_accounting)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "market-os.b3-1.synthetic-fold-artifact@v1",
            "synthetic_only": True,
            "fold_id": self.fold_id,
            "status": self.status,
            "row_count": self.row_count,
            "target_eligible_row_count": self.target_eligible_row_count,
            "numerical_score_eligible_row_count": self.numerical_score_eligible_row_count,
            "row_artifacts": [item.to_dict() for item in self.row_artifacts],
            "assessment_status_counts": dict(sorted(self.assessment_status_counts.items())),
            "calibration_row_ids": list(self.calibration_row_ids),
            "test_row_ids": list(self.test_row_ids),
            "calibration": {
                "status": self.calibration_status,
                "method": self.calibration_method,
                "rate": self.calibration_rate,
                "fingerprint": self.calibration_fingerprint,
            },
            "metrics": [item.to_dict() for item in self.metrics],
            "unavailable_reasons": list(self.unavailable_reasons),
            "matched_row_accounting": dict(sorted(self.matched_row_accounting.items())),
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True)
class SyntheticArmArtifact:
    arm_id: SyntheticArmId | str
    status: SyntheticArmStatus | str
    fold_results: tuple[SyntheticFoldArtifact, ...]
    row_count: int
    target_eligible_row_count: int
    numerical_score_eligible_row_count: int
    assessment_status_counts: Mapping[str, int]
    matched_row_ids: tuple[str, ...]
    metrics: tuple[SyntheticMetric, ...]
    unavailable_reasons: tuple[str, ...]
    fingerprint: str
    matched_row_accounting: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "arm_id", SyntheticArmId(self.arm_id))
        object.__setattr__(self, "status", SyntheticArmStatus(self.status))
        object.__setattr__(self, "fold_results", tuple(self.fold_results))
        object.__setattr__(self, "assessment_status_counts", MappingProxyType(dict(self.assessment_status_counts)))
        object.__setattr__(self, "matched_row_ids", tuple(self.matched_row_ids))
        object.__setattr__(self, "metrics", tuple(self.metrics))
        object.__setattr__(self, "unavailable_reasons", tuple(self.unavailable_reasons))
        object.__setattr__(self, "matched_row_accounting", MappingProxyType(dict(self.matched_row_accounting)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "market-os.b3-1.synthetic-arm-artifact@v1",
            "synthetic_only": True,
            "arm_id": self.arm_id.value,
            "status": self.status.value,
            "fold_results": [item.to_dict() for item in self.fold_results],
            "row_count": self.row_count,
            "target_eligible_row_count": self.target_eligible_row_count,
            "numerical_score_eligible_row_count": self.numerical_score_eligible_row_count,
            "assessment_status_counts": dict(sorted(self.assessment_status_counts.items())),
            "matched_row_ids": list(self.matched_row_ids),
            "matched_row_accounting": dict(sorted(self.matched_row_accounting.items())),
            "metrics": [item.to_dict() for item in self.metrics],
            "unavailable_reasons": list(self.unavailable_reasons),
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True)
class SyntheticEvaluationReport:
    rows: tuple[SyntheticRowArtifact, ...]
    outcomes: tuple[SyntheticOutcome, ...]
    arms: tuple[SyntheticArmArtifact, ...]
    plan_fingerprint: str
    compilation_fingerprint: str
    materialization_fingerprint: str
    synthetic_only: bool
    interpretation: str
    runtime_assumptions: Mapping[str, str]
    fingerprint: str
    matched_row_accounting: Mapping[str, int] = field(default_factory=dict)
    row_count: int = 0
    target_eligible_row_count: int = 0
    numerical_score_eligible_row_count: int = 0
    assessment_status_counts: Mapping[str, int] = field(default_factory=dict)
    unavailable_reasons: tuple[str, ...] = ()
    materialization_status: str = "materialized"

    def __post_init__(self) -> None:
        object.__setattr__(self, "rows", tuple(self.rows))
        object.__setattr__(self, "outcomes", tuple(self.outcomes))
        object.__setattr__(self, "arms", tuple(self.arms))
        object.__setattr__(self, "runtime_assumptions", MappingProxyType(dict(self.runtime_assumptions)))
        object.__setattr__(self, "matched_row_accounting", MappingProxyType(dict(self.matched_row_accounting)))
        object.__setattr__(self, "assessment_status_counts", MappingProxyType(dict(self.assessment_status_counts)))
        object.__setattr__(self, "unavailable_reasons", tuple(self.unavailable_reasons))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": RUNNER_SCHEMA,
            "version": RUNNER_VERSION,
            "status": "synthetic_only",
            "synthetic_only": self.synthetic_only,
            "interpretation": self.interpretation,
            "plan_fingerprint": self.plan_fingerprint,
            "compilation_fingerprint": self.compilation_fingerprint,
            "materialization_fingerprint": self.materialization_fingerprint,
            "materialization_status": self.materialization_status,
            "rows": [item.to_dict() for item in self.rows],
            "outcomes": [{"row_id": item.row_id, "label": item.label} for item in self.outcomes],
            "arms": [item.to_dict() for item in self.arms],
            "runtime_assumptions": dict(sorted(self.runtime_assumptions.items())),
            "matched_row_accounting": dict(sorted(self.matched_row_accounting.items())),
            "row_counts": {
                "rows": self.row_count,
                "evaluation_rows": self.row_count - sum(1 for row in self.rows if row.fold_id == "B10"),
                "untouched": sum(1 for row in self.rows if row.fold_id == "B10"),
                "target_eligible": self.target_eligible_row_count,
                "numerical_score_eligible": self.numerical_score_eligible_row_count,
            },
            "assessment_status_counts": dict(sorted(self.assessment_status_counts.items())),
            "unavailable_reasons": list(self.unavailable_reasons),
            "economic_results": "not_applicable_synthetic_only",
            "fingerprint": self.fingerprint,
        }

    def verify_replay(self, other: "SyntheticEvaluationReport") -> bool:
        return self.fingerprint == other.fingerprint and self.to_dict() == other.to_dict()


def build_synthetic_row(
    *,
    row_id: str,
    timestamp_ms: int,
    feature_fingerprint: str,
    numerical_score: float | None,
    target_available: bool = True,
    assessment: SyntheticAssessmentSummary | None = None,
    assessment_reference: str | None = None,
    assessment_status: str | None = None,
    dataset_revision: str = "synthetic-fixture-v1",
    fixture_fingerprint: str | None = None,
) -> SyntheticEvaluationRow:
    feature = FeatureRowIdentity(dataset_revision, timestamp_ms, feature_fingerprint)
    fixture = fixture_fingerprint or _sha({"row_id": row_id, "feature_fingerprint": feature_fingerprint})
    target = SyntheticTargetJoin(
        feature_fingerprint,
        status=TargetStatus.AVAILABLE if target_available else TargetStatus.UNAVAILABLE,
        target_end_ms=timestamp_ms + _PURGE_EMBARGO_MS if target_available else 0,
    )
    return SyntheticEvaluationRow(
        row_id=row_id,
        feature_identity=feature,
        timestamp_ms=timestamp_ms,
        target=target,
        numerical_score=numerical_score,
        source_fingerprint=feature_fingerprint,
        fixture_fingerprint=fixture,
        assessment=assessment,
        assessment_reference=assessment_reference,
        assessment_status=assessment_status,
    )


def build_synthetic_outcome(row_id: str, label: bool) -> SyntheticOutcome:
    return SyntheticOutcome(row_id, label)


def _status_counts(rows: Sequence[SyntheticEvaluationRow]) -> dict[str, int]:
    counts = {status: 0 for status in _ASSESSMENT_STATUSES}
    for row in rows:
        counts[row.assessment_status or "missing"] += 1
    return counts


def _assessment_diagnostics(row: SyntheticEvaluationRow) -> tuple[bool, bool, tuple[str, ...]]:
    assessment = row.assessment
    if assessment is None or assessment.status != "usable":
        return False, False, ()
    concentrated = assessment.concentration_max is not None and assessment.concentration_max >= 0.8
    return assessment.evidence_disagreement, concentrated, assessment.diagnostic_ranking


def _metric(name: str, result: MetricResult) -> SyntheticMetric:
    return SyntheticMetric(name, result.status, result.value, result.n, result.reason)


def _unavailable_metric(name: str, reason: str, n: int = 0) -> SyntheticMetric:
    return SyntheticMetric(name, "unavailable", None, n, reason)


def _materialization_map(materialization: SyntheticMaterialization) -> dict[str, dict[str, tuple[str, str]]]:
    result: dict[str, dict[str, tuple[str, str]]] = {}
    for fold in materialization.fold_set.folds:
        for assignment in fold.assignments:
            per_fold = result.setdefault(assignment.row_fingerprint, {})
            if fold.fold_id in per_fold:
                raise ValueError("duplicate synthetic fold assignment")
            per_fold[fold.fold_id] = (assignment.split, assignment.reason)
    return result


def _find_block(compilation: SyntheticPlanCompilation, timestamp_ms: int) -> int:
    for block in compilation.blocks:
        if block.start_ms <= timestamp_ms < block.end_ms:
            return block.block_id
    raise ValueError("synthetic row timestamp is outside B1-B10")


def _validate_inputs(
    plan: OfflineEvaluationPlan,
    compilation: SyntheticPlanCompilation,
    materialization: SyntheticMaterialization,
    rows: Sequence[SyntheticEvaluationRow],
    outcomes: Sequence[SyntheticOutcome],
) -> tuple[dict[str, SyntheticEvaluationRow], dict[str, SyntheticOutcome], dict[str, dict[str, tuple[str, str]]]]:
    if plan.status is not EvaluationPlanStatus.DATASET_UNBOUND or plan.dataset_class is not DatasetClass.SMOKE:
        raise ValueError("runner requires a dataset-unbound synthetic-only plan")
    if plan.folds != recommended_evaluation_folds():
        raise ValueError("runner requires the frozen F1-F3 mapping")
    if len(compilation.blocks) != 10 or {block.block_id for block in compilation.blocks} != _BLOCK_IDS:
        raise ValueError("runner requires exactly synthetic blocks B1-B10")
    if len(compilation.fold_specs) != 3:
        raise ValueError("runner requires exactly three frozen folds")
    if compilation.plan_fingerprint != plan.fingerprint:
        raise ValueError("compilation does not match the frozen plan")
    if materialization.compilation_fingerprint != compilation.fingerprint:
        raise ValueError("materialization does not match the compilation")
    if materialization.status not in {"materialized", "unavailable_insufficient_label_support"}:
        raise ValueError("unsupported synthetic materialization status")
    if plan.purge_ms != _PURGE_EMBARGO_MS or plan.embargo_ms != _PURGE_EMBARGO_MS:
        raise ValueError("runner requires the frozen five-minute purge and embargo")
    expected_compilation = compile_synthetic_evaluation_plan(
        plan,
        synthetic_start_ms=compilation.synthetic_start_ms,
        block_duration_ms=compilation.block_duration_ms,
    )
    if compilation.to_dict() != expected_compilation.to_dict():
        raise ValueError("compilation does not match the frozen F1-F3/B1-B10 mapping")
    row_map: dict[str, SyntheticEvaluationRow] = {}
    feature_ids: set[str] = set()
    assessment_refs: set[str] = set()
    for row in rows:
        if row.row_id in row_map:
            raise ValueError("duplicate synthetic row ID")
        if row.feature_fingerprint in feature_ids:
            raise ValueError("duplicate synthetic feature identity")
        feature_ids.add(row.feature_fingerprint)
        if row.assessment_reference is not None and row.assessment_reference in assessment_refs:
            raise ValueError("duplicate synthetic assessment reference")
        if row.assessment_reference is not None:
            assessment_refs.add(row.assessment_reference)
        _find_block(compilation, row.timestamp_ms)
        row_map[row.row_id] = row
    outcome_map: dict[str, SyntheticOutcome] = {}
    for outcome in outcomes:
        if outcome.row_id in outcome_map:
            raise ValueError("duplicate synthetic outcome row ID")
        if outcome.row_id not in row_map:
            raise ValueError("outcome references an unknown synthetic row")
        if _find_block(compilation, row_map[outcome.row_id].timestamp_ms) == 10:
            raise ValueError("B10 outcomes are prohibited because B10 is untouched")
        outcome_map[outcome.row_id] = outcome
    for row in rows:
        block_id = _find_block(compilation, row.timestamp_ms)
        if block_id != 10 and row.target.status is TargetStatus.AVAILABLE and row.row_id not in outcome_map:
            raise ValueError("available synthetic target has no separate outcome")
        if block_id != 10 and row.target.status is TargetStatus.UNAVAILABLE and row.row_id in outcome_map:
            raise ValueError("unavailable synthetic target cannot carry an outcome")
    assignment_map = _materialization_map(materialization)
    identity = {
        "compilation_fingerprint": materialization.compilation_fingerprint,
        "fold_set": materialization.fold_set.to_dict(),
        "exclusions": [item.to_dict() for item in materialization.exclusions],
        "fold_label_counts": materialization.fold_label_counts,
        "status_counts": dict(sorted(materialization.status_counts.items())),
        "status": materialization.status,
    }
    if _sha(identity) != materialization.replay_fingerprint:
        raise ValueError("materialization replay fingerprint is inconsistent")
    expected_rows = []
    for row in rows:
        block_id = _find_block(compilation, row.timestamp_ms)
        if block_id != 10 and row.target.status is TargetStatus.AVAILABLE:
            expected_rows.append(DatasetRow(row.timestamp_ms, row.feature_fingerprint, row.target.target_end_ms, outcome_map[row.row_id].label))
        else:
            expected_rows.append(DatasetRow(row.timestamp_ms, row.feature_fingerprint))
    expected_materialization = materialize_synthetic_evaluation_plan(compilation, expected_rows)
    if materialization.to_dict() != expected_materialization.to_dict():
        raise ValueError("materialization does not match synthetic rows and labels")
    exclusions = {item.row_fingerprint: item.status for item in materialization.exclusions}
    for row in rows:
        block_id = _find_block(compilation, row.timestamp_ms)
        if block_id == 10 and exclusions.get(row.feature_fingerprint) != "untouched":
            raise ValueError("B10 row must be recorded as untouched")
        if block_id != 10 and row.target.status is TargetStatus.UNAVAILABLE and exclusions.get(row.feature_fingerprint) != "target_unavailable":
            raise ValueError("unavailable target row must be recorded in materialization")
        if block_id != 10 and row.target.status is TargetStatus.AVAILABLE and row.feature_fingerprint not in assignment_map:
            raise ValueError("eligible synthetic row is missing from materialization")
        if row.feature_fingerprint not in assignment_map and block_id != 10 and row.target.status is TargetStatus.UNAVAILABLE and exclusions.get(row.feature_fingerprint) != "target_unavailable":
            raise ValueError("synthetic row is missing from materialization accounting")
    return row_map, outcome_map, assignment_map


def _fold_rows(
    rows: Sequence[SyntheticEvaluationRow],
    assignment_map: Mapping[str, Mapping[str, tuple[str, str]]],
    fold_id: str,
    split: str,
) -> list[SyntheticEvaluationRow]:
    return sorted(
        (row for row in rows if assignment_map.get(row.feature_fingerprint, {}).get(fold_id, (None, None))[0] == split),
        key=lambda item: item.row_id,
    )


def _numerical_fold(
    fold_id: str,
    rows: Sequence[SyntheticEvaluationRow],
    assignment_map: Mapping[str, Mapping[str, tuple[str, str]]],
    outcomes: Mapping[str, SyntheticOutcome],
) -> SyntheticFoldArtifact:
    fold_rows = sorted(
        (row for row in rows if assignment_map.get(row.feature_fingerprint, {}).get(fold_id, (None, None))[0] in {"train", "validation", "calibration", "test", "purged", "embargoed", "outside"}),
        key=lambda item: item.row_id,
    )
    calibration = [row for row in _fold_rows(rows, assignment_map, fold_id, "calibration") if row.target.status is TargetStatus.AVAILABLE and row.numerical_score is not None]
    test_candidates = _fold_rows(rows, assignment_map, fold_id, "test")
    test = [row for row in test_candidates if row.target.status is TargetStatus.AVAILABLE and row.numerical_score is not None]
    calibration_ids = tuple(row.row_id for row in calibration)
    test_ids = tuple(row.row_id for row in test)
    reasons: list[str] = []
    status = "measured"
    probabilities: dict[str, float] = {}
    calibration_status = "unavailable"
    calibration_rate: float | None = None
    calibration_fingerprint = ""
    labels = [outcomes[row.row_id].label for row in calibration]
    if not calibration:
        status, reasons = "unavailable", ["no eligible numerical calibration rows"]
    elif len(set(labels)) < 2:
        status, reasons = "unavailable", ["calibration labels are single-class"]
    elif not test:
        status, reasons = "unavailable", ["no eligible numerical test rows"]
    else:
        artifact = fit_calibrator(
            {row.row_id: float(row.numerical_score) for row in calibration},
            {row.row_id: outcomes[row.row_id].label for row in calibration},
            CalibrationConfig(CalibrationMethod.ONE_BIN),
            calibration_row_ids=calibration_ids,
            test_row_ids=test_ids,
        )
        calibration_status = artifact.status
        calibration_rate = artifact.rate
        calibration_fingerprint = _sha(artifact.to_dict())
        if artifact.status != "measured":
            status, reasons = "unavailable", [artifact.reason or "one-bin calibration unavailable"]
        else:
            probabilities = {row.row_id: artifact.predict(float(row.numerical_score)) for row in test}
    metrics: list[SyntheticMetric]
    if status != "measured":
        metrics = [_unavailable_metric(name, reasons[0], len(test)) for name in ("log_loss", "brier", "balanced_accuracy", "ece")]
    else:
        test_labels = [outcomes[row.row_id].label for row in test]
        values = [probabilities[row.row_id] for row in test]
        metrics = [
            _metric("log_loss", log_loss(values, test_labels)),
            _metric("brier", brier_score(values, test_labels)),
            _metric("balanced_accuracy", balanced_accuracy(values, test_labels)),
            _metric("ece", expected_calibration_error(values, test_labels)),
        ]
    metrics.append(SyntheticMetric("coverage", "measured" if test_candidates else "unavailable", len(test) / len(test_candidates) if test_candidates else None, len(test_candidates), None if test_candidates else "no synthetic test candidates"))
    row_artifacts: list[SyntheticRowArtifact] = []
    for row in fold_rows:
        disagreement, concentrated, ranking = _assessment_diagnostics(row)
        split, reason = assignment_map[row.feature_fingerprint][fold_id]
        row_artifacts.append(SyntheticRowArtifact(
            row.row_id,
            row.feature_fingerprint,
            fold_id,
            split,
            row.target.status.value,
            "eligible" if row.numerical_score is not None else "unavailable",
            row.assessment_status or "missing",
            row.assessment_reference,
            row.source_fingerprint,
            row.fixture_fingerprint,
            row.assessment.response_fingerprints if row.assessment else (),
            disagreement,
            concentrated,
            ranking,
            probabilities.get(row.row_id),
            reason,
        ))
    counts = _status_counts(fold_rows)
    for item in ("purged", "embargoed", "outside"):
        counts[item] = sum(1 for row in fold_rows if assignment_map[row.feature_fingerprint][fold_id][0] == item)
    canonical = {
        "fold_id": fold_id,
        "status": status,
        "row_artifacts": [item.to_dict() for item in row_artifacts],
        "calibration_row_ids": calibration_ids,
        "test_row_ids": test_ids,
        "calibration": {"status": calibration_status, "method": "one_bin", "rate": calibration_rate, "fingerprint": calibration_fingerprint},
        "metrics": [item.to_dict() for item in metrics],
        "reasons": reasons,
        "row_count": len(row_artifacts),
        "target_eligible_row_count": sum(row.target.status is TargetStatus.AVAILABLE for row in fold_rows),
        "numerical_score_eligible_row_count": sum(row.target.status is TargetStatus.AVAILABLE and row.numerical_score is not None for row in fold_rows),
    }
    return SyntheticFoldArtifact(fold_id, status, tuple(row_artifacts), counts, calibration_ids, test_ids, calibration_status, "one_bin", calibration_rate, calibration_fingerprint, tuple(metrics), tuple(reasons), _sha(canonical), {}, len(fold_rows), sum(row.target.status is TargetStatus.AVAILABLE for row in fold_rows), sum(row.target.status is TargetStatus.AVAILABLE and row.numerical_score is not None for row in fold_rows))


def _jev_fold(fold_id: str, rows: Sequence[SyntheticEvaluationRow], assignment_map: Mapping[str, Mapping[str, tuple[str, str]]]) -> SyntheticFoldArtifact:
    fold_rows = sorted(
        (row for row in rows if assignment_map.get(row.feature_fingerprint, {}).get(fold_id, (None, None))[0] in {"train", "validation", "calibration", "test", "purged", "embargoed", "outside"}),
        key=lambda item: item.row_id,
    )
    test_rows = _fold_rows(rows, assignment_map, fold_id, "test")
    artifacts: list[SyntheticRowArtifact] = []
    disagreement = sum(1 for row in fold_rows if _assessment_diagnostics(row)[0])
    concentrated = sum(1 for row in fold_rows if _assessment_diagnostics(row)[1])
    for row in fold_rows:
        d, c, ranking = _assessment_diagnostics(row)
        split, reason = assignment_map[row.feature_fingerprint][fold_id]
        artifacts.append(SyntheticRowArtifact(row.row_id, row.feature_fingerprint, fold_id, split, row.target.status.value, "eligible" if row.numerical_score is not None else "unavailable", row.assessment_status or "missing", row.assessment_reference, row.source_fingerprint, row.fixture_fingerprint, row.assessment.response_fingerprints if row.assessment else (), d, c, ranking, None, reason))
    usable = sum(1 for row in test_rows if row.assessment_status == "usable")
    metrics = (SyntheticMetric("coverage", "measured" if test_rows else "unavailable", usable / len(test_rows) if test_rows else None, len(test_rows), None if test_rows else "no synthetic test rows"),)
    reasons = (f"valid_disagreement={disagreement}", f"concentrated_valid={concentrated}")
    counts = _status_counts(fold_rows)
    for item in ("purged", "embargoed", "outside"):
        counts[item] = sum(1 for row in fold_rows if assignment_map[row.feature_fingerprint][fold_id][0] == item)
    canonical = {"fold_id": fold_id, "rows": [item.to_dict() for item in artifacts], "metrics": [item.to_dict() for item in metrics], "reasons": reasons, "assessment_status_counts": counts, "row_count": len(artifacts), "target_eligible_row_count": sum(row.target.status is TargetStatus.AVAILABLE for row in fold_rows), "numerical_score_eligible_row_count": sum(row.target.status is TargetStatus.AVAILABLE and row.numerical_score is not None for row in fold_rows)}
    return SyntheticFoldArtifact(fold_id, "measured" if test_rows else "unavailable", tuple(artifacts), counts, (), tuple(row.row_id for row in test_rows), "unavailable", "none", None, "", metrics, reasons, _sha(canonical), {}, len(fold_rows), sum(row.target.status is TargetStatus.AVAILABLE for row in fold_rows), sum(row.target.status is TargetStatus.AVAILABLE and row.numerical_score is not None for row in fold_rows))


def _arm_variance(folds: Sequence[SyntheticFoldArtifact], metric_name: str) -> SyntheticMetric:
    values = [next((item.value for item in fold.metrics if item.name == metric_name and item.status == "measured"), None) for fold in folds]
    measured = [value for value in values if value is not None]
    if len(measured) < 2:
        return SyntheticMetric("fold_variance", "unavailable", None, len(measured), f"metric={metric_name}; at least two measured folds are required")
    mean = sum(measured) / len(measured)
    return SyntheticMetric("fold_variance", "measured", sum((value - mean) ** 2 for value in measured) / len(measured), len(measured), f"metric={metric_name}")


def run_synthetic_evaluation(
    plan: OfflineEvaluationPlan,
    compilation: SyntheticPlanCompilation,
    materialization: SyntheticMaterialization,
    rows: Sequence[SyntheticEvaluationRow],
    outcomes: Sequence[SyntheticOutcome],
) -> SyntheticEvaluationReport:
    row_map, outcome_map, assignment_map = _validate_inputs(plan, compilation, materialization, rows, outcomes)
    ordered_rows = tuple(sorted(row_map.values(), key=lambda row: row.row_id))
    ordered_outcomes = tuple(sorted(outcome_map.values(), key=lambda item: item.row_id))
    folds = tuple(fold.fold_id for fold in materialization.fold_set.folds)
    numerical_folds = tuple(_numerical_fold(fold_id, ordered_rows, assignment_map, outcome_map) for fold_id in folds)
    jev_folds = tuple(_jev_fold(fold_id, ordered_rows, assignment_map) for fold_id in folds)
    numerical_status = SyntheticArmStatus.MEASURED if any(fold.status == "measured" for fold in numerical_folds) else SyntheticArmStatus.UNAVAILABLE
    measured_rows = tuple(row for row in ordered_rows if _find_block(compilation, row.timestamp_ms) != 10)
    eligible_rows = tuple(row for row in measured_rows if row.target.status is TargetStatus.AVAILABLE)
    score_rows = tuple(row for row in eligible_rows if row.numerical_score is not None)
    numerical_counts = _status_counts(measured_rows)
    all_status_counts = _status_counts(ordered_rows)
    numerical_metrics = tuple(
        [metric for name in ("log_loss", "brier", "balanced_accuracy", "ece", "coverage") for metric in (_aggregate_metric(numerical_folds, name),)]
        + [_arm_variance(numerical_folds, name) for name in ("log_loss", "brier", "balanced_accuracy", "ece", "coverage")]
    )
    numerical_arm = SyntheticArmArtifact(
        SyntheticArmId.NUMERICAL_CONTROL,
        numerical_status,
        numerical_folds,
        len(measured_rows),
        len(eligible_rows),
        len(score_rows),
        numerical_counts,
        tuple(sorted({row_id for fold in numerical_folds for row_id in fold.test_row_ids})),
        numerical_metrics,
        tuple(sorted({reason for fold in numerical_folds for reason in fold.unavailable_reasons})),
        "",
    )
    jev_counts = _status_counts(measured_rows)
    jev_metrics = (
        _aggregate_metric(jev_folds, "coverage"),
        SyntheticMetric("valid_disagreement", "measured", sum(1 for row in measured_rows if _assessment_diagnostics(row)[0]), len(measured_rows)),
        SyntheticMetric("concentrated_valid", "measured", sum(1 for row in measured_rows if _assessment_diagnostics(row)[1]), len(measured_rows)),
    )
    jev_arm = SyntheticArmArtifact(
        SyntheticArmId.JEV_COVERAGE,
        SyntheticArmStatus.MEASURED if any(fold.status == "measured" for fold in jev_folds) else SyntheticArmStatus.UNAVAILABLE,
        jev_folds,
        len(measured_rows),
        len(eligible_rows),
        len(score_rows),
        jev_counts,
        tuple(sorted({row_id for fold in jev_folds for row_id in fold.test_row_ids})),
        jev_metrics,
        (),
        "",
    )
    matched = matched_row_accounting(numerical_arm.matched_row_ids, jev_arm.matched_row_ids)
    matched_dict = {
        "numerical_row_count": matched.left_count,
        "jev_coverage_row_count": matched.right_count,
        "intersection_count": matched.intersection_count,
    }
    numerical_arm = SyntheticArmArtifact(
        numerical_arm.arm_id, numerical_arm.status, numerical_arm.fold_results, numerical_arm.row_count,
        numerical_arm.target_eligible_row_count, numerical_arm.numerical_score_eligible_row_count,
        numerical_arm.assessment_status_counts, numerical_arm.matched_row_ids, numerical_arm.metrics,
        numerical_arm.unavailable_reasons, "", matched_dict,
    )
    jev_arm = SyntheticArmArtifact(
        jev_arm.arm_id, jev_arm.status, jev_arm.fold_results, jev_arm.row_count,
        jev_arm.target_eligible_row_count, jev_arm.numerical_score_eligible_row_count,
        jev_arm.assessment_status_counts, jev_arm.matched_row_ids, jev_arm.metrics,
        jev_arm.unavailable_reasons, "", matched_dict,
    )
    fusion_rows = tuple(SyntheticRowArtifact(row.row_id, row.feature_fingerprint, "all", "candidate", row.target.status.value, "eligible" if row.numerical_score is not None else "unavailable", row.assessment_status or "missing", row.assessment_reference, row.source_fingerprint, row.fixture_fingerprint, row.assessment.response_fingerprints if row.assessment else (), *_assessment_diagnostics(row), None, "fusion fitting deferred") for row in measured_rows)
    fusion_metrics = (_unavailable_metric("coverage", "fusion fitting is deferred"),)
    fusion_canonical = {"fold_id": "all", "status": "unavailable_deferred", "rows": [item.to_dict() for item in fusion_rows], "metrics": [item.to_dict() for item in fusion_metrics], "reasons": ["fusion fitting is deferred"], "row_count": len(measured_rows), "target_eligible_row_count": len(eligible_rows), "numerical_score_eligible_row_count": len(score_rows)}
    fusion_fold = SyntheticFoldArtifact("all", "unavailable_deferred", fusion_rows, numerical_counts, (), (), "unavailable_deferred", "none", None, "", fusion_metrics, ("fusion fitting is deferred",), _sha(fusion_canonical), {}, len(measured_rows), len(eligible_rows), len(score_rows))
    fusion_arm = SyntheticArmArtifact(SyntheticArmId.FUSION_PLACEHOLDER, SyntheticArmStatus.UNAVAILABLE_DEFERRED, (fusion_fold,), len(measured_rows), len(eligible_rows), len(score_rows), numerical_counts, (), fusion_metrics, ("fusion fitting is deferred",), "")
    arms = (numerical_arm, jev_arm, fusion_arm)
    row_artifacts_list: list[SyntheticRowArtifact] = []
    for row in ordered_rows:
        block_id = _find_block(compilation, row.timestamp_ms)
        assignments = assignment_map.get(row.feature_fingerprint, {})
        if assignments:
            fold_id, (split, reason) = sorted(assignments.items())[0]
        else:
            fold_id = "B10" if block_id == 10 else "unassigned"
            split = "untouched" if fold_id == "B10" else "target_unavailable"
            reason = "B10 is reserved and untouched" if fold_id == "B10" else "realized target label is unavailable"
        disagreement, concentrated, ranking = _assessment_diagnostics(row) if block_id != 10 else (False, False, ())
        assessment_status = row.assessment_status or "missing" if block_id != 10 else "missing"
        row_artifacts_list.append(SyntheticRowArtifact(
            row.row_id,
            row.feature_fingerprint,
            fold_id,
            split,
            row.target.status.value,
            "untouched" if block_id == 10 else ("eligible" if row.numerical_score is not None else "unavailable"),
            assessment_status,
            row.assessment_reference if block_id != 10 else None,
            row.source_fingerprint,
            row.fixture_fingerprint,
            row.assessment.response_fingerprints if row.assessment and block_id != 10 else (),
            disagreement,
            concentrated,
            ranking,
            None,
            reason,
        ))
    row_artifacts = tuple(row_artifacts_list)
    report_base = {
        "schema": RUNNER_SCHEMA,
        "synthetic_only": True,
        "interpretation": "synthetic-only; numerical output is a synthetic one-bin baseline, not an actual calibrated market probability; no predictive-evidence or economic interpretation",
        "plan_fingerprint": plan.fingerprint,
        "compilation_fingerprint": compilation.fingerprint,
        "materialization_fingerprint": materialization.replay_fingerprint,
        "materialization_status": materialization.status,
        "rows": [item.to_dict() for item in row_artifacts],
        "outcomes": [{"row_id": item.row_id, "label": item.label} for item in ordered_outcomes],
        "arms": [item.to_dict() for item in arms],
        "matched_row_accounting": matched_dict,
        "row_counts": {"rows": len(ordered_rows), "evaluation_rows": len(measured_rows), "target_eligible": len(eligible_rows), "numerical_score_eligible": len(score_rows)},
        "assessment_status_counts": dict(sorted(all_status_counts.items())),
        "runtime_assumptions": {"latency": "unknown_not_observed_offline", "usage": "unknown_not_observed_offline", "cost": "unknown_not_observed_offline"},
        "unavailable_reasons": sorted({reason for arm in arms for reason in arm.unavailable_reasons}),
        "economic_results": "not_applicable_synthetic_only",
    }
    arms = tuple(SyntheticArmArtifact(item.arm_id, item.status, tuple(_fingerprinted_fold(fold) for fold in item.fold_results), item.row_count, item.target_eligible_row_count, item.numerical_score_eligible_row_count, item.assessment_status_counts, item.matched_row_ids, item.metrics, item.unavailable_reasons, _sha({**item.to_dict(), "fingerprint": None}), item.matched_row_accounting) for item in arms)
    report_base["arms"] = [item.to_dict() for item in arms]
    report_fingerprint = _sha(report_base)
    return SyntheticEvaluationReport(
        row_artifacts,
        ordered_outcomes,
        arms,
        plan.fingerprint,
        compilation.fingerprint,
        materialization.replay_fingerprint,
        True,
        "synthetic-only; numerical output is a synthetic one-bin baseline, not an actual calibrated market probability; no predictive-evidence or economic interpretation",
        {"latency": "unknown_not_observed_offline", "usage": "unknown_not_observed_offline", "cost": "unknown_not_observed_offline"},
        report_fingerprint,
        matched_dict,
        len(ordered_rows),
        len(eligible_rows),
        len(score_rows),
        all_status_counts,
        tuple(sorted({reason for arm in arms for reason in arm.unavailable_reasons})),
        materialization.status,
    )


def _aggregate_metric(folds: Sequence[SyntheticFoldArtifact], name: str) -> SyntheticMetric:
    values = [item for fold in folds for item in fold.metrics if item.name == name and item.status == "measured" and item.value is not None]
    if not values:
        return _unavailable_metric(name, "no measured synthetic fold")
    total_n = sum(item.n for item in values)
    return SyntheticMetric(name, "measured", sum(item.value * item.n for item in values) / total_n if total_n else 0.0, total_n)


def deterministic_report_fingerprint(report: SyntheticEvaluationReport) -> str:
    return report.fingerprint


def verify_deterministic_replay(first: SyntheticEvaluationReport, second: SyntheticEvaluationReport) -> bool:
    return first.verify_replay(second)


__all__ = [
    "RUNNER_SCHEMA", "SyntheticArmId", "SyntheticArmStatus", "SyntheticTargetJoin",
    "SyntheticAssessmentSummary", "SyntheticEvaluationRow", "SyntheticOutcome", "SyntheticMetric", "SyntheticRowArtifact",
    "SyntheticFoldArtifact", "SyntheticArmArtifact", "SyntheticEvaluationReport",
    "build_synthetic_row", "build_synthetic_outcome", "run_synthetic_evaluation",
    "deterministic_report_fingerprint", "verify_deterministic_replay",
]
