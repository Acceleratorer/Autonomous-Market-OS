"""Deterministic, synthetic-only readiness auditing for B3.1 bundles.

This module only inspects an already validated local artifact bundle.  It does
not fit models, contact providers, bind a dataset, or authorize execution.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from .synthetic_artifacts import (
    SyntheticArtifactBundle,
    _validate_bundle,
)


AUDIT_SCHEMA = "market-os.b3-1.synthetic-readiness-audit@v1"
AUDIT_VERSION = "v1"
CHECK_PASS = "pass"
CHECK_BLOCKED = "blocked"
CHECK_FAIL = "fail"
CHECK_STATUSES = frozenset({CHECK_PASS, CHECK_BLOCKED, CHECK_FAIL})

GATE_SYNTHETIC_IMPLEMENTATION = "synthetic_implementation"
GATE_OFFLINE_RESEARCH_EVALUATION = "offline_research_evaluation"
GATE_REAL_DATASET_BINDING = "real_dataset_binding"
GATE_PROVIDER_INTEGRATION = "provider_integration"
GATE_SHADOW_STUDY = "shadow_study"
GATE_IDS = (
    GATE_SYNTHETIC_IMPLEMENTATION,
    GATE_OFFLINE_RESEARCH_EVALUATION,
    GATE_REAL_DATASET_BINDING,
    GATE_PROVIDER_INTEGRATION,
    GATE_SHADOW_STUDY,
)

EXPECTED_ARMS = frozenset(
    {
        "synthetic_numerical_control",
        "synthetic_jev_coverage",
        "synthetic_fusion_placeholder",
    }
)
PREDICTIVE_METRICS = frozenset({"log_loss", "brier", "balanced_accuracy", "ece"})
ASSESSMENT_STATUSES = frozenset(
    {"schema_invalid", "unsupported", "internally_inconsistent", "stale", "unavailable", "abstained", "usable", "missing"}
)
EXCLUDED_SPLITS = frozenset({"purged", "embargoed", "outside", "untouched"})
RUNTIME_KEYS = frozenset({"latency", "usage", "cost"})
UNKNOWN_OFFLINE = "unknown_not_observed_offline"
FORBIDDEN_TEXT = ("http://", "https://", "binance", "openai", "typesafe", "provider", "credential")
SELF_REFERENCE_KEYS = frozenset({"audit", "audit_fingerprint", "readiness_audit", "readiness_audit_fingerprint"})


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(item) for item in value]
    return value


def _canonical(value: Any) -> str:
    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _contains_self_reference(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(str(key).lower() in SELF_REFERENCE_KEYS or _contains_self_reference(child) for key, child in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_self_reference(child) for child in value)
    return False


def _external_identity(value: Any) -> bool:
    if isinstance(value, str):
        lowered = value.lower()
        return "://" in lowered or "\\" in lowered or any(token in lowered for token in FORBIDDEN_TEXT)
    if isinstance(value, Mapping):
        return any(_external_identity(key) or _external_identity(child) for key, child in value.items())
    if isinstance(value, (list, tuple)):
        return any(_external_identity(child) for child in value)
    return False


def _has_real_dataset_identity(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            if key_text in {"dataset_id", "dataset_revision", "dataset_identity", "real_dataset_id", "real_dataset_revision"}:
                if not isinstance(child, str) or not child.startswith("synthetic-"):
                    return True
            if _has_real_dataset_identity(child):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_has_real_dataset_identity(child) for child in value)
    return False


def _contains_label_field(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any("label" in str(key).lower() or _contains_label_field(child) for key, child in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_label_field(child) for child in value)
    return False


@dataclass(frozen=True)
class SyntheticAuditCheck:
    check_id: str
    status: str
    detail: str

    def __post_init__(self) -> None:
        if not self.check_id or self.status not in CHECK_STATUSES or not self.detail:
            raise ValueError("audit check requires an ID, explicit status, and detail")

    def to_dict(self) -> dict[str, str]:
        return {"check_id": self.check_id, "status": self.status, "detail": self.detail}


@dataclass(frozen=True)
class SyntheticAuditGate:
    gate_id: str
    status: str
    detail: str
    check_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.gate_id not in GATE_IDS or self.status not in CHECK_STATUSES or not self.detail:
            raise ValueError("audit gate requires a known ID, explicit status, and detail")
        object.__setattr__(self, "check_ids", tuple(self.check_ids))

    def to_dict(self) -> dict[str, Any]:
        return {"gate_id": self.gate_id, "status": self.status, "detail": self.detail, "check_ids": list(self.check_ids)}


@dataclass(frozen=True)
class SyntheticReadinessAudit:
    schema: str
    version: str
    source_bundle_fingerprint: str
    checks: tuple[SyntheticAuditCheck, ...]
    gates: tuple[SyntheticAuditGate, ...]
    overall_status: str
    interpretation: str
    audit_fingerprint: str

    def __post_init__(self) -> None:
        if self.schema != AUDIT_SCHEMA or self.version != AUDIT_VERSION:
            raise ValueError("unsupported synthetic readiness audit schema")
        if not _is_digest(self.source_bundle_fingerprint) or not _is_digest(self.audit_fingerprint):
            raise ValueError("audit fingerprints must be lowercase SHA-256 values")
        if self.overall_status not in {CHECK_PASS, CHECK_FAIL}:
            raise ValueError("overall audit status must be pass or fail")
        if "contract/replay readiness only" not in self.interpretation or "never predictive evidence" not in self.interpretation:
            raise ValueError("audit interpretation must preserve the non-predictive boundary")
        object.__setattr__(self, "checks", tuple(self.checks))
        object.__setattr__(self, "gates", tuple(self.gates))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "version": self.version,
            "source_bundle_fingerprint": self.source_bundle_fingerprint,
            "checks": [check.to_dict() for check in self.checks],
            "gates": [gate.to_dict() for gate in self.gates],
            "overall_status": self.overall_status,
            "interpretation": self.interpretation,
            "audit_fingerprint": self.audit_fingerprint,
        }

    def verify_replay(self, other: "SyntheticReadinessAudit") -> bool:
        return self.audit_fingerprint == other.audit_fingerprint and self.to_dict() == other.to_dict()


def _check_bundle_shape(bundle: dict[str, Any]) -> dict[str, Any]:
    artifacts = bundle.get("artifacts")
    report = artifacts.get("evaluation_report", {}) if isinstance(artifacts, Mapping) else {}
    stability = artifacts.get("stability_report", {}) if isinstance(artifacts, Mapping) else {}
    return {"artifacts": artifacts, "report": report, "stability": stability}


def _semantic_checks(bundle: dict[str, Any]) -> list[SyntheticAuditCheck]:
    shape = _check_bundle_shape(bundle)
    artifacts, report, stability = shape["artifacts"], shape["report"], shape["stability"]
    checks: list[SyntheticAuditCheck] = []

    checks.append(SyntheticAuditCheck("bundle_schema_and_fingerprint", CHECK_PASS, "bundle schema, bundle fingerprint, and source artifact fingerprints validated"))
    checks.append(SyntheticAuditCheck("artifact_fingerprints", CHECK_PASS, "evaluation and stability report fingerprints validated"))
    checks.append(SyntheticAuditCheck("stability_source_fingerprint", CHECK_PASS if stability.get("source_fingerprint") == report.get("fingerprint") else CHECK_FAIL, "stability source fingerprint matches evaluation report" if stability.get("source_fingerprint") == report.get("fingerprint") else "stability source fingerprint differs from evaluation report"))
    exact_artifacts = isinstance(artifacts, Mapping) and set(artifacts) == {"evaluation_report", "stability_report"}
    checks.append(SyntheticAuditCheck("expected_artifacts", CHECK_PASS if exact_artifacts else CHECK_FAIL, "bundle contains exactly evaluation_report and stability_report" if exact_artifacts else "bundle artifact set is not exactly evaluation_report and stability_report"))
    nested_runner_artifacts = [report, *report.get("rows", []), *report.get("arms", [])]
    nested_runner_artifacts.extend(fold for arm in report.get("arms", []) if isinstance(arm, Mapping) for fold in arm.get("fold_results", []))
    synthetic = report.get("synthetic_only") is True and stability.get("schema") == "market-os.b3-1.synthetic-stability-report@v1" and stability.get("synthetic_only", True) is True and all(item.get("synthetic_only") is True for item in nested_runner_artifacts if isinstance(item, Mapping))
    checks.append(SyntheticAuditCheck("synthetic_only_artifacts", CHECK_PASS if synthetic and not _external_identity(bundle) else CHECK_FAIL, "all artifacts are synthetic-only and contain no external identity" if synthetic and not _external_identity(bundle) else "artifact is not synthetic-only or contains an external identity"))

    arms = report.get("arms", []) if isinstance(report, Mapping) else []
    arm_ids = [arm.get("arm_id") for arm in arms if isinstance(arm, Mapping)]
    arm_set_ok = len(arm_ids) == len(set(arm_ids)) == len(EXPECTED_ARMS) and set(arm_ids) == EXPECTED_ARMS
    checks.append(SyntheticAuditCheck("expected_arm_set", CHECK_PASS if arm_set_ok else CHECK_FAIL, "expected three synthetic arms are present exactly once" if arm_set_ok else "expected arm set is missing, duplicated, or contains an unexpected arm"))

    rows = report.get("rows", []) if isinstance(report, Mapping) else []
    b10 = [row for row in rows if isinstance(row, Mapping) and row.get("fold_id") == "B10"]
    b10_ok = bool(b10) and all(row.get("split") == "untouched" and row.get("numerical_score_status") == "untouched" and row.get("target_status") == "unavailable" and row.get("assessment_status") == "missing" and row.get("probability") is None for row in b10) and all(row.get("split") != "untouched" for row in rows if row.get("fold_id") != "B10")
    checks.append(SyntheticAuditCheck("b10_untouched", CHECK_PASS if b10_ok else CHECK_FAIL, "B10 rows are present only as untouched rows" if b10_ok else "B10 contains evaluated fields or an untouched row is outside B10"))
    outcome_ids = {outcome.get("row_id") for outcome in report.get("outcomes", []) if isinstance(outcome, Mapping)}
    b10_ids = {row.get("row_id") for row in b10}
    no_b10_outcomes = not (outcome_ids & b10_ids)
    checks.append(SyntheticAuditCheck("no_b10_realized_outcomes", CHECK_PASS if no_b10_outcomes else CHECK_FAIL, "no realized outcomes are attached to B10" if no_b10_outcomes else "B10 contains realized outcome records"))

    predictive_ok = True
    jev_ok = True
    for arm in arms:
        if not isinstance(arm, Mapping):
            predictive_ok = jev_ok = False
            continue
        arm_id = arm.get("arm_id")
        all_metrics = list(arm.get("metrics", []))
        all_metrics.extend(metric for fold in arm.get("fold_results", []) if isinstance(fold, Mapping) for metric in fold.get("metrics", []))
        for metric in all_metrics:
            if isinstance(metric, Mapping) and metric.get("name") in PREDICTIVE_METRICS and metric.get("status") == "measured" and arm_id != "synthetic_numerical_control":
                predictive_ok = False
        for fold in arm.get("fold_results", []):
            for row in fold.get("row_artifacts", []) if isinstance(fold, Mapping) else []:
                if arm_id != "synthetic_numerical_control" and isinstance(row, Mapping) and row.get("probability") is not None:
                    predictive_ok = False
                if arm_id == "synthetic_jev_coverage" and isinstance(row, Mapping) and row.get("probability") is not None:
                    jev_ok = False
    checks.append(SyntheticAuditCheck("numerical_metrics_only_control", CHECK_PASS if predictive_ok else CHECK_FAIL, "predictive metrics and probabilities are confined to numerical control" if predictive_ok else "non-control arm contains predictive metrics or probabilities"))
    checks.append(SyntheticAuditCheck("jev_no_market_probabilities", CHECK_PASS if jev_ok else CHECK_FAIL, "Jev coverage arm has no market-outcome predictive probabilities" if jev_ok else "Jev coverage arm contains market-outcome predictive probabilities"))

    fusion = next((arm for arm in arms if isinstance(arm, Mapping) and arm.get("arm_id") == "synthetic_fusion_placeholder"), None)
    fusion_ok = isinstance(fusion, Mapping) and fusion.get("status") == "unavailable_deferred" and all(metric.get("status") == "unavailable" for metric in fusion.get("metrics", []) if isinstance(metric, Mapping))
    checks.append(SyntheticAuditCheck("fusion_unavailable_deferred", CHECK_PASS if fusion_ok else CHECK_FAIL, "fusion remains explicitly unavailable_deferred" if fusion_ok else "fusion is measured or otherwise not explicitly deferred"))

    overlap_ok = True
    calibration_shape_ok = True
    for arm in arms:
        for fold in arm.get("fold_results", []) if isinstance(arm, Mapping) else []:
            if not isinstance(fold, Mapping):
                overlap_ok = calibration_shape_ok = False
                continue
            calibration = set(fold.get("calibration_row_ids", []))
            test = set(fold.get("test_row_ids", []))
            if len(fold.get("calibration_row_ids", [])) != len(calibration) or len(fold.get("test_row_ids", [])) != len(test) or calibration & test:
                overlap_ok = False
            row_map = {row.get("row_id"): row for row in fold.get("row_artifacts", []) if isinstance(row, Mapping)}
            if any(row_id not in row_map or row_map[row_id].get("split") != "calibration" for row_id in calibration):
                calibration_shape_ok = False
            if any(row_id not in row_map or row_map[row_id].get("split") != "test" for row_id in test):
                calibration_shape_ok = False
            calibration_payload = fold.get("calibration", {})
            calibration_rows = [row_map[row_id] for row_id in calibration if row_id in row_map]
            if _contains_label_field({"calibration": calibration_payload, "calibration_rows": calibration_rows}):
                calibration_shape_ok = False
    checks.append(SyntheticAuditCheck("calibration_test_disjoint", CHECK_PASS if overlap_ok else CHECK_FAIL, "calibration and test rows are disjoint for every fold" if overlap_ok else "calibration and test rows overlap or are duplicated"))
    checks.append(SyntheticAuditCheck("calibration_has_no_test_labels", CHECK_PASS if calibration_shape_ok else CHECK_FAIL, "calibration artifacts contain row identities only and no test labels" if calibration_shape_ok else "calibration artifacts contain test labels or invalid split identities"))

    statuses_ok = True
    for row in rows:
        if not isinstance(row, Mapping) or not {"assessment_status", "target_status", "numerical_score_status", "split"}.issubset(row):
            statuses_ok = False
        elif row.get("assessment_status") not in ASSESSMENT_STATUSES or row.get("target_status") not in {"available", "unavailable"} or row.get("numerical_score_status") not in {"eligible", "unavailable", "untouched"} or type(row.get("disagreement")) is not bool:
            statuses_ok = False
    for arm in arms:
        if not isinstance(arm, Mapping) or arm.get("status") not in {"measured", "unavailable", "unavailable_deferred"}:
            statuses_ok = False
        for fold in arm.get("fold_results", []) if isinstance(arm, Mapping) else []:
            if not isinstance(fold, Mapping):
                statuses_ok = False
                continue
            if fold.get("status") not in {"measured", "unavailable", "unavailable_deferred"}:
                statuses_ok = False
            expected_status_counts: dict[str, int] = {}
            for row in fold.get("row_artifacts", []):
                if not isinstance(row, Mapping) or row.get("assessment_status") not in ASSESSMENT_STATUSES:
                    statuses_ok = False
                    continue
                status = row["assessment_status"]
                expected_status_counts[status] = expected_status_counts.get(status, 0) + 1
            actual_status_counts = {key: count for key, count in fold.get("assessment_status_counts", {}).items() if count and key not in EXCLUDED_SPLITS}
            if actual_status_counts != expected_status_counts:
                statuses_ok = False
    stability_statuses = stability.get("status_counts_by_arm", {})
    if isinstance(stability_statuses, Mapping):
        for counts in stability_statuses.values():
            if not isinstance(counts, Mapping) or any(status not in ASSESSMENT_STATUSES for status in counts):
                statuses_ok = False
    checks.append(SyntheticAuditCheck("explicit_status_inventory", CHECK_PASS if statuses_ok else CHECK_FAIL, "unavailable, abstained, stale, contradictory, and invalid statuses remain explicit" if statuses_ok else "an artifact omits or normalizes an explicit status"))

    coverage_ok = True
    coverage_groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for cell in stability.get("coverage", []) if isinstance(stability, Mapping) else []:
        if not isinstance(cell, Mapping) or cell.get("status") not in ASSESSMENT_STATUSES or not isinstance(cell.get("count"), int) or not isinstance(cell.get("denominator"), int) or cell["count"] < 0 or cell["denominator"] < 0 or cell["count"] > cell["denominator"]:
            coverage_ok = False
        elif isinstance(cell, Mapping):
            coverage_groups.setdefault((cell.get("arm_id"), cell.get("fold_id")), []).append(cell)
    expected_fold_sizes = {
        (arm.get("arm_id"), fold.get("fold_id")): len(fold.get("row_artifacts", []))
        for arm in arms if isinstance(arm, Mapping)
        for fold in arm.get("fold_results", []) if isinstance(fold, Mapping)
    }
    for key, cells in coverage_groups.items():
        denominators = {cell["denominator"] for cell in cells}
        seen = {(cell.get("split"), cell.get("status")) for cell in cells}
        if len(denominators) != 1 or len(seen) != len(cells) or sum(cell["count"] for cell in cells) != next(iter(denominators), -1) or next(iter(denominators), -1) != expected_fold_sizes.get(key):
            coverage_ok = False
    if set(coverage_groups) != set(expected_fold_sizes):
        coverage_ok = False
    for arm in arms:
        for fold in arm.get("fold_results", []) if isinstance(arm, Mapping) else []:
            if isinstance(fold, Mapping):
                expected = len(fold.get("row_artifacts", []))
                if fold.get("row_count") not in {0, expected}:
                    coverage_ok = False
    checks.append(SyntheticAuditCheck("coverage_denominators", CHECK_PASS if coverage_ok else CHECK_FAIL, "coverage counts and denominators are internally consistent" if coverage_ok else "coverage counts or denominators are inconsistent"))

    expected_excluded: dict[str, int] = {}
    for row in rows:
        if isinstance(row, Mapping) and row.get("split") in EXCLUDED_SPLITS:
            key = f"{row['split']}:{row.get('target_status')}"
            expected_excluded[key] = expected_excluded.get(key, 0) + 1
    excluded_ok = stability.get("excluded_counts") == expected_excluded
    checks.append(SyntheticAuditCheck("excluded_split_counts", CHECK_PASS if excluded_ok else CHECK_FAIL, "excluded split counts are explicit and match row artifacts" if excluded_ok else "excluded split counts are missing or inconsistent"))

    runtime = stability.get("runtime_assumptions", {})
    report_runtime = report.get("runtime_assumptions", {})
    runtime_ok = (
        isinstance(runtime, Mapping)
        and isinstance(report_runtime, Mapping)
        and all(runtime.get(key) == UNKNOWN_OFFLINE for key in RUNTIME_KEYS)
        and all(report_runtime.get(key) == UNKNOWN_OFFLINE for key in RUNTIME_KEYS)
    )
    checks.append(SyntheticAuditCheck("offline_runtime_unknown", CHECK_PASS if runtime_ok else CHECK_FAIL, "latency, usage, and cost remain unknown_not_observed_offline" if runtime_ok else "offline runtime assumptions are not explicitly unknown_not_observed_offline"))
    has_external = _external_identity(bundle) or _has_real_dataset_identity(bundle)
    checks.append(SyntheticAuditCheck("no_external_identity", CHECK_PASS if not has_external else CHECK_FAIL, "bundle contains no external provider, URL, credential, or real-dataset identity" if not has_external else "bundle contains an external provider, URL, credential, or real-dataset identity"))
    checks.append(SyntheticAuditCheck("audit_replay_deterministic", CHECK_PASS, "audit check projection is identical when rebuilt from the same bundle"))
    checks.append(SyntheticAuditCheck("audit_not_self_referential", CHECK_PASS if not _contains_self_reference(bundle) else CHECK_FAIL, "audit fingerprint is not an input to the source bundle" if not _contains_self_reference(bundle) else "source bundle contains a self-referential audit fingerprint"))
    return checks


def _gate(checks: tuple[SyntheticAuditCheck, ...], gate_id: str, status: str, detail: str, check_ids: tuple[str, ...] = ()) -> SyntheticAuditGate:
    return SyntheticAuditGate(gate_id, status, detail, check_ids)


def audit_synthetic_artifact_bundle(bundle: SyntheticArtifactBundle) -> SyntheticReadinessAudit:
    """Build a deterministic readiness audit from a validated bundle.

    Bundle integrity errors raise ``ValueError``.  Semantic violations are
    retained as failed checks and therefore fail only the synthetic gate.
    """
    if not isinstance(bundle, SyntheticArtifactBundle):
        raise ValueError("audit requires a SyntheticArtifactBundle")
    validated = _validate_bundle(bundle.to_dict())
    source = validated.fingerprint
    payload = validated.to_dict()
    if _contains_self_reference(payload):
        raise ValueError("bundle contains a self-referential audit fingerprint")
    first_checks = _semantic_checks(payload)
    checks = tuple(first_checks)
    replay_checks = _semantic_checks(payload)
    replay_status = CHECK_PASS if [item.to_dict() for item in first_checks] == [item.to_dict() for item in replay_checks] else CHECK_FAIL
    checks = tuple(
        SyntheticAuditCheck(item.check_id, replay_status if item.check_id == "audit_replay_deterministic" else item.status, item.detail)
        for item in checks
    )
    synthetic_check_ids = tuple(check.check_id for check in checks if check.status != CHECK_BLOCKED)
    synthetic_status = CHECK_PASS if all(check.status == CHECK_PASS for check in checks) else CHECK_FAIL
    gates = (
        _gate(checks, GATE_SYNTHETIC_IMPLEMENTATION, synthetic_status, "synthetic contract/replay checks pass" if synthetic_status == CHECK_PASS else "one or more synthetic contract/replay checks failed", synthetic_check_ids),
        _gate(checks, GATE_OFFLINE_RESEARCH_EVALUATION, CHECK_BLOCKED, "blocked: current bundle is synthetic-only and dataset-unbound"),
        _gate(checks, GATE_REAL_DATASET_BINDING, CHECK_BLOCKED, "blocked: no human-approved dataset revision or range exists"),
        _gate(checks, GATE_PROVIDER_INTEGRATION, CHECK_BLOCKED, "blocked: provider integration is outside the approved milestone"),
        _gate(checks, GATE_SHADOW_STUDY, CHECK_BLOCKED, "blocked: no prospective shadow approval exists"),
    )
    check_payload = [check.to_dict() for check in checks]
    gate_payload = [gate.to_dict() for gate in gates]
    base = {
        "schema": AUDIT_SCHEMA,
        "version": AUDIT_VERSION,
        "source_bundle_fingerprint": source,
        "checks": check_payload,
        "gates": gate_payload,
        "overall_status": synthetic_status,
        "interpretation": "contract/replay readiness only; never predictive evidence or a promotion decision",
    }
    return SyntheticReadinessAudit(source_bundle_fingerprint=source, checks=checks, gates=gates, overall_status=synthetic_status, interpretation=base["interpretation"], schema=AUDIT_SCHEMA, version=AUDIT_VERSION, audit_fingerprint=_fingerprint(base))


def verify_synthetic_audit_replay(first: SyntheticReadinessAudit, second: SyntheticReadinessAudit) -> bool:
    return first.verify_replay(second)


build_synthetic_readiness_audit = audit_synthetic_artifact_bundle


__all__ = [
    "AUDIT_SCHEMA",
    "AUDIT_VERSION",
    "CHECK_PASS",
    "CHECK_BLOCKED",
    "CHECK_FAIL",
    "GATE_IDS",
    "SyntheticAuditCheck",
    "SyntheticAuditGate",
    "SyntheticReadinessAudit",
    "audit_synthetic_artifact_bundle",
    "build_synthetic_readiness_audit",
    "verify_synthetic_audit_replay",
]
