"""Offline, leakage-safe Jev-shaped incremental-value benchmark.

This module deliberately has no provider SDK, credentials, socket, or HTTP
transport.  Recorded responses are typed at the boundary and every failure
becomes an explicit unavailable, rejected, late, or abstained assessment.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .btc_b2 import (
    B2Config,
    B2_FEATURE_VERSION,
    B2_TARGET_VERSION,
    _sample_rows,
    build_splits,
    evaluate_baselines,
    materialize_rows,
)
from .btc_history import HistoryStore

B3_API_VERSION = "market-os.btc-b3.v1"
B3_RUN_SCHEMA = "market-os.u3-b3.jev-benchmark.v1"
B3_FIXTURE_SCHEMA = "market-os.btc-b3-recorded-responses.v1"
B3_ADAPTER_VERSION = "market-os.btc-b3.recorded-adapter.v1"
B3_EXPERIMENT_VERSION = "btc.b3.jev-incremental.v1"
B3_PROVIDER = "typesafe"
B3_MODEL = "jev"
B3_MODEL_VERSION = "jev-1.14.0"
B3_QUESTION_ID = "btc_5m_market_assessment"
B3_DECISION_QUESTION = (
    "Using only this point-in-time BTCUSDT one-minute feature snapshot, "
    "classify the observed market state as bullish, bearish, or indeterminate. "
    "This is a semantic assessment, not a probability of a future BTC return."
)
B3_ANSWER_SCHEMA = {
    "type": "choice",
    "options": ["bullish", "bearish", "indeterminate"],
    "returns": ["choice", "probabilities", "confidence"],
}
B3_CASE_KINDS = {
    "valid",
    "unavailable",
    "malformed",
    "late",
    "abstaining",
    "inconsistent",
    "hostile",
}
B3_OUTCOMES = {"usable", "unavailable", "rejected", "late", "abstained"}
_UTC = timezone.utc
_HORIZON_MS = 5 * 60_000
_DIGEST_RE = 64


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != _DIGEST_RE or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field} must be a lowercase SHA-256 fingerprint")
    return value


def _timestamp(value: str, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be an ISO-8601 UTC timestamp")
    return parsed


def _iso(value: datetime) -> str:
    return value.astimezone(_UTC).isoformat(timespec="milliseconds")


def _finite_probability(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite probability")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a finite probability") from exc
    if not math.isfinite(result) or not 0 <= result <= 1:
        raise ValueError(f"{field} must be a finite probability")
    return result


def _answer(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"choice", "probabilities", "confidence"}:
        raise ValueError("recorded Jev answer must contain exactly choice, probabilities, and confidence")
    choice = payload["choice"]
    if choice not in B3_ANSWER_SCHEMA["options"]:
        raise ValueError("recorded Jev choice is outside the versioned answer schema")
    probabilities = payload["probabilities"]
    if not isinstance(probabilities, dict) or set(probabilities) != set(B3_ANSWER_SCHEMA["options"]):
        raise ValueError("recorded Jev probabilities must cover every answer option")
    probabilities = {key: _finite_probability(probabilities[key], f"probabilities.{key}") for key in B3_ANSWER_SCHEMA["options"]}
    if not math.isclose(sum(probabilities.values()), 1.0, abs_tol=1e-9):
        raise ValueError("recorded Jev probabilities must sum to one")
    if choice != max(probabilities, key=probabilities.get):
        raise ValueError("recorded Jev choice is inconsistent with its probability distribution")
    confidence = _finite_probability(payload["confidence"], "confidence")
    return {"choice": choice, "probabilities": probabilities, "confidence": confidence}


def parse_recorded_response(payload: Any) -> dict[str, Any]:
    """Strictly parse one recorded response; no transport is reachable here."""
    if not isinstance(payload, dict) or set(payload) != {"model", "answer"}:
        raise ValueError("recorded Jev response must contain exactly model and answer")
    model = payload["model"]
    if model != B3_MODEL_VERSION:
        raise ValueError(f"unsupported recorded Jev model version: {model}")
    return {"model": model, "answer": _answer(payload["answer"])}


@dataclass(frozen=True)
class ExperimentRequest:
    dataset_revision: str
    feature_fingerprint: str
    input_feature_fingerprint: str
    decision_eligible_at: str
    decision_question: str = B3_DECISION_QUESTION
    answer_schema: dict[str, Any] | None = None
    request_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if not self.dataset_revision.strip():
            raise ValueError("dataset_revision is required")
        _digest(self.feature_fingerprint, "feature_fingerprint")
        _digest(self.input_feature_fingerprint, "input_feature_fingerprint")
        _timestamp(self.decision_eligible_at, "decision_eligible_at")
        if self.decision_question != B3_DECISION_QUESTION:
            raise ValueError("unsupported Jev decision question")
        if self.answer_schema is not None and self.answer_schema != B3_ANSWER_SCHEMA:
            raise ValueError("unsupported Jev answer schema")
        if self.request_fingerprint is not None:
            _digest(self.request_fingerprint, "request_fingerprint")
            if self.request_fingerprint != _sha(self.payload()):
                raise ValueError("request_fingerprint does not match the canonical request payload")

    def payload(self) -> dict[str, Any]:
        return {
            "dataset_revision": self.dataset_revision,
            "feature_fingerprint": self.feature_fingerprint,
            "input_feature_fingerprint": self.input_feature_fingerprint,
            "decision_eligible_at": self.decision_eligible_at,
            "question_id": B3_QUESTION_ID,
            "decision_question": self.decision_question,
            "answer_schema": self.answer_schema or B3_ANSWER_SCHEMA,
            "provider": B3_PROVIDER,
            "model": B3_MODEL,
            "model_version": B3_MODEL_VERSION,
        }

    def fingerprint(self) -> str:
        return self.request_fingerprint or _sha(self.payload())


@dataclass(frozen=True)
class B3Config:
    experiment_id: str
    dataset_revision: str
    feature_fingerprint: str
    fixture_id: str
    response_deadline_ms: int = 30_000
    train_fraction: float = 0.6
    calibration_fraction: float = 0.2
    test_fraction: float = 0.2
    feature_version: str = B2_FEATURE_VERSION
    target_version: str = B2_TARGET_VERSION
    calibration_method: str = "one-bin empirical calibration"
    calibration_range: str = "calibration"
    context_mode: str = "none"
    execution_mode: str = "paper"
    transport_mode: str = "offline-recorded-only"
    provider: str = B3_PROVIDER
    model: str = B3_MODEL
    model_version: str = B3_MODEL_VERSION
    decision_question: str = B3_DECISION_QUESTION
    answer_schema: dict[str, Any] | None = None
    api_version: str = B3_API_VERSION

    def __post_init__(self) -> None:
        if not self.experiment_id.strip() or not self.dataset_revision.strip() or not self.fixture_id.strip():
            raise ValueError("experiment_id, dataset_revision, and fixture_id are required")
        _digest(self.feature_fingerprint, "feature_fingerprint")
        if self.response_deadline_ms <= 0:
            raise ValueError("response_deadline_ms must be positive")
        if any(value <= 0 for value in (self.train_fraction, self.calibration_fraction, self.test_fraction)):
            raise ValueError("split fractions must be positive")
        if not math.isclose(self.train_fraction + self.calibration_fraction + self.test_fraction, 1.0):
            raise ValueError("split fractions must sum to one")
        if self.feature_version != B2_FEATURE_VERSION or self.target_version != B2_TARGET_VERSION:
            raise ValueError("B3 must use the frozen B2 feature and target versions")
        if self.calibration_range != "calibration" or self.calibration_method != "one-bin empirical calibration":
            raise ValueError("B3 calibration identity is fixed and leakage-safe")
        if self.context_mode != "none" or self.execution_mode != "paper":
            raise ValueError("B3 has no context-input or execution authority")
        if self.transport_mode != "offline-recorded-only":
            raise ValueError("B3 transport is permanently offline-recorded-only")
        if (self.provider, self.model, self.model_version) != (B3_PROVIDER, B3_MODEL, B3_MODEL_VERSION):
            raise ValueError("unsupported recorded provider identity")
        if self.decision_question != B3_DECISION_QUESTION or (self.answer_schema not in (None, B3_ANSWER_SCHEMA)):
            raise ValueError("unsupported Jev question or answer schema")
        if self.api_version != B3_API_VERSION:
            raise ValueError("unsupported B3 API version")


@dataclass(frozen=True)
class JevResponseRecord:
    case_id: str
    case_kind: str
    outcome: str
    dataset_revision: str
    feature_fingerprint: str
    input_feature_fingerprint: str
    request_fingerprint: str
    response_fingerprint: str | None
    provider: str
    model: str
    model_version: str
    adapter_version: str
    decision_question: str
    answer_schema: dict[str, Any]
    decision_eligible_at: str
    request_started_at: str
    response_received_at: str | None
    available_at: str | None
    latency_ms: None
    latency_status: str
    usage: None
    cost_usd: None
    failure: dict[str, str] | None
    abstention: bool
    abstention_reason: str | None
    cache: dict[str, Any]
    answer: dict[str, Any] | None

    def __post_init__(self) -> None:
        if not self.case_id.strip() or self.case_kind not in B3_CASE_KINDS or self.outcome not in B3_OUTCOMES:
            raise ValueError("invalid Jev recorded response identity or outcome")
        _digest(self.feature_fingerprint, "feature_fingerprint")
        _digest(self.input_feature_fingerprint, "input_feature_fingerprint")
        _digest(self.request_fingerprint, "request_fingerprint")
        if self.response_fingerprint is not None:
            _digest(self.response_fingerprint, "response_fingerprint")
        if self.provider != B3_PROVIDER or self.model != B3_MODEL or self.model_version != B3_MODEL_VERSION or self.adapter_version != B3_ADAPTER_VERSION:
            raise ValueError("unsupported Jev provider identity")
        if self.decision_question != B3_DECISION_QUESTION or self.answer_schema != B3_ANSWER_SCHEMA:
            raise ValueError("recorded response question/schema mismatch")
        decision = _timestamp(self.decision_eligible_at, "decision_eligible_at")
        started = _timestamp(self.request_started_at, "request_started_at")
        if started < decision:
            raise ValueError("request cannot start before input eligibility")
        if self.response_received_at is not None:
            received = _timestamp(self.response_received_at, "response_received_at")
            if received < started:
                raise ValueError("response cannot arrive before request start")
        if self.available_at != self.response_received_at:
            raise ValueError("available_at must equal response_received_at for recorded responses")
        if self.latency_ms is not None or self.usage is not None or self.cost_usd is not None:
            raise ValueError("offline fixture cannot claim observed latency, usage, or cost")
        if self.outcome == "usable" and self.answer is None:
            raise ValueError("usable Jev response requires a typed answer")
        if self.outcome != "usable" and not self.abstention:
            raise ValueError("non-usable Jev response must abstain")


class RecordedJevAdapter:
    """A fixture-only adapter; it contains no network or provider client."""

    def __init__(self, fixture: dict[str, Any]) -> None:
        if fixture.get("schema") != B3_FIXTURE_SCHEMA:
            raise ValueError(f"expected fixture schema {B3_FIXTURE_SCHEMA}")
        self.fixture_id = str(fixture.get("fixture_id", ""))
        if not self.fixture_id.strip():
            raise ValueError("fixture_id is required")
        cases = fixture.get("cases")
        if not isinstance(cases, list):
            raise ValueError("recorded Jev fixture cases must be an array")
        self.fixture_fingerprint = _sha({"schema": fixture["schema"], "fixture_id": self.fixture_id, "cases": cases})
        declared = fixture.get("fixture_fingerprint")
        if declared is not None and declared != self.fixture_fingerprint:
            raise ValueError("recorded Jev fixture fingerprint mismatch")
        self._cases: dict[str, dict[str, Any]] = {}
        for case in cases:
            if not isinstance(case, dict) or set(case) != {"case_id", "kind", "input_feature_fingerprint", "response_delay_ms", "response"}:
                raise ValueError("recorded Jev fixture case has an invalid shape")
            case_id = case["case_id"]
            kind = case["kind"]
            input_fp = _digest(case["input_feature_fingerprint"], "input_feature_fingerprint")
            if not isinstance(case_id, str) or not case_id.strip() or kind not in B3_CASE_KINDS:
                raise ValueError("recorded Jev fixture case identity is invalid")
            if input_fp in self._cases:
                raise ValueError("recorded Jev fixture has duplicate input fingerprints")
            delay = case["response_delay_ms"]
            if isinstance(delay, bool) or not isinstance(delay, int) or delay < 0:
                raise ValueError("response_delay_ms must be a non-negative integer")
            if kind == "unavailable" and case["response"] is not None:
                raise ValueError("unavailable fixture case cannot contain a response")
            self._cases[input_fp] = dict(case)

    @classmethod
    def from_path(cls, path: str | Path) -> "RecordedJevAdapter":
        try:
            fixture = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read Jev recorded fixture: {exc}") from exc
        return cls(fixture)

    def inspect_cases(self) -> list[dict[str, Any]]:
        return [{key: value for key, value in item.items() if key != "response"} for item in sorted(self._cases.values(), key=lambda item: item["case_id"])]

    def evaluate(self, request: ExperimentRequest, *, deadline_ms: int) -> JevResponseRecord:
        request_fp = request.fingerprint()
        case = self._cases.get(request.input_feature_fingerprint)
        base = {
            "case_id": case["case_id"] if case else "missing-case",
            "case_kind": case["kind"] if case else "unavailable",
            "dataset_revision": request.dataset_revision,
            "feature_fingerprint": request.feature_fingerprint,
            "input_feature_fingerprint": request.input_feature_fingerprint,
            "request_fingerprint": request_fp,
            "provider": B3_PROVIDER,
            "model": B3_MODEL,
            "model_version": B3_MODEL_VERSION,
            "adapter_version": B3_ADAPTER_VERSION,
            "decision_question": request.decision_question,
            "answer_schema": request.answer_schema or B3_ANSWER_SCHEMA,
            "decision_eligible_at": request.decision_eligible_at,
            "request_started_at": request.decision_eligible_at,
            "latency_ms": None,
            "latency_status": "unknown-not-observed-offline",
            "usage": None,
            "cost_usd": None,
            "cache": {"mode": "fixture", "hit": bool(case), "fixture_id": self.fixture_id},
        }
        if case is None or case["kind"] == "unavailable":
            return JevResponseRecord(
                **base,
                outcome="unavailable",
                response_fingerprint=None,
                response_received_at=None,
                available_at=None,
                failure={"code": "provider_unavailable", "reason": "no deterministic recorded response is available"},
                abstention=True,
                abstention_reason="provider unavailable in offline fixture",
                answer=None,
            )
        raw_response = case["response"]
        response_fp = _sha(raw_response)
        delay = case["response_delay_ms"]
        received = _timestamp(request.decision_eligible_at, "decision_eligible_at") + timedelta(milliseconds=delay)
        try:
            parsed = parse_recorded_response(raw_response)
        except ValueError as exc:
            return JevResponseRecord(
                **base,
                outcome="rejected",
                response_fingerprint=response_fp,
                response_received_at=_iso(received),
                available_at=_iso(received),
                failure={"code": f"{case['kind']}_response_rejected", "reason": str(exc)},
                abstention=True,
                abstention_reason=f"{case['kind']} recorded response rejected",
                answer=None,
            )
        if delay > deadline_ms or case["kind"] == "late":
            return JevResponseRecord(
                **base,
                outcome="late",
                response_fingerprint=response_fp,
                response_received_at=_iso(received),
                available_at=_iso(received),
                failure={"code": "response_late", "reason": "recorded response exceeded the frozen response deadline"},
                abstention=True,
                abstention_reason="late provider response",
                answer=parsed["answer"],
            )
        if case["kind"] == "abstaining" or parsed["answer"]["choice"] == "indeterminate":
            return JevResponseRecord(
                **base,
                outcome="abstained",
                response_fingerprint=response_fp,
                response_received_at=_iso(received),
                available_at=_iso(received),
                failure=None,
                abstention=True,
                abstention_reason="recorded Jev answer is indeterminate",
                answer=parsed["answer"],
            )
        return JevResponseRecord(
            **base,
            outcome="usable",
            response_fingerprint=response_fp,
            response_received_at=_iso(received),
            available_at=_iso(received),
            failure=None,
            abstention=False,
            abstention_reason=None,
            answer=parsed["answer"],
        )


def _group(feature_values: dict[str, float]) -> str:
    value = feature_values["log_return_1m"]
    return "up" if value > 0 else "down" if value < 0 else "flat"


def _e2_group(sample: dict[str, Any], response: JevResponseRecord) -> str:
    return f"{_group(sample['feature_values'])}:{response.answer['choice']}"


def _rates(train: list[dict[str, Any]], keyer) -> tuple[dict[str, float], float]:
    fallback = sum(item["direction"] == "up" for item in train) / len(train) if train else 0.5
    groups: dict[str, list[bool]] = {}
    for item in train:
        groups.setdefault(keyer(item), []).append(item["direction"] == "up")
    return {key: sum(values) / len(values) for key, values in groups.items()}, fallback


def _score(predictions: list[tuple[str, float]], samples: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not predictions:
        return {"status": "unavailable", "n": 0, "log_loss": None, "brier": None, "accuracy": None}
    log_loss = 0.0
    brier = 0.0
    correct = 0
    for feature_fp, probability in predictions:
        sample = samples[feature_fp]
        truth = sample["direction"] == "up"
        bounded = min(1 - 1e-15, max(1e-15, probability))
        log_loss += -math.log(bounded if truth else 1 - bounded)
        brier += (probability - truth) ** 2
        correct += (probability >= 0.5) == truth
    count = len(predictions)
    return {"status": "measured", "n": count, "log_loss": log_loss / count, "brier": brier / count, "accuracy": correct / count}


def _calibration(raw: list[tuple[str, float]], calibration_samples: dict[str, dict[str, Any]], target: list[tuple[str, float]]) -> tuple[list[tuple[str, float]], dict[str, Any]]:
    if not raw:
        return target, {"status": "unavailable", "method": "one-bin empirical calibration", "n": 0, "reason": "no leakage-safe calibration predictions"}
    rate = sum(calibration_samples[feature_fp]["direction"] == "up" for feature_fp, _ in raw) / len(raw)
    fit_fingerprint = _sha([feature_fp for feature_fp, _ in raw])
    return [(feature_fp, rate) for feature_fp, _ in target], {
        "status": "measured",
        "method": "one-bin empirical calibration",
        "range": "calibration",
        "n": len(raw),
        "calibration_rate": rate,
        "fit_input_fingerprint": fit_fingerprint,
    }


def _calibrated_score(predictions: list[tuple[str, float]], samples: dict[str, dict[str, Any]], calibration: dict[str, Any]) -> dict[str, Any]:
    if calibration.get("status") != "measured":
        return {"status": "unavailable", "n": 0, "log_loss": None, "brier": None, "accuracy": None}
    return _score(predictions, samples)


def _feature_by_time(materialized: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {item["close_time_ms"]: item for item in materialized["features"] if item["status"] == "eligible"}


def _request_for(feature: dict[str, Any], config: B3Config) -> ExperimentRequest:
    if feature.get("status") != "eligible" or not feature.get("input_fingerprint"):
        raise ValueError("only eligible B2 features can be sent to a recorded Jev adapter")
    decision = _timestamp(feature["decision_eligible_at"], "decision_eligible_at")
    for ref in feature.get("input_refs", []):
        if ref["open_time_ms"] > feature["close_time_ms"]:
            raise ValueError("feature input references a future candle")
        if _timestamp(ref["availability_timestamp"], "availability_timestamp") > decision:
            raise ValueError("feature input was unavailable at prediction time")
    return ExperimentRequest(config.dataset_revision, config.feature_fingerprint, feature["input_fingerprint"], feature["decision_eligible_at"], answer_schema=config.answer_schema or B3_ANSWER_SCHEMA)


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _coverage(test: list[dict[str, Any]], records: dict[str, JevResponseRecord] | None, predicted: list[tuple[str, float]]) -> dict[str, Any]:
    total = len(test)
    predicted_count = len(predicted)
    return {
        "status": "measured" if total else "unavailable",
        "candidate_n": total,
        "predicted_n": predicted_count,
        "abstention_n": total - predicted_count,
        "coverage": predicted_count / total if total else None,
        "abstention_rate": (total - predicted_count) / total if total else None,
        "outcomes": _counts([records[item["input_fingerprint"]].outcome for item in test]) if records is not None else {"available": total},
    }


def evaluate_b3(materialized: dict[str, Any], adapter: RecordedJevAdapter, config: B3Config) -> dict[str, Any]:
    samples = _sample_rows(materialized)
    b2_config = B2Config(
        "b3-split",
        train_fraction=config.train_fraction,
        calibration_fraction=config.calibration_fraction,
        test_fraction=config.test_fraction,
    )
    splits = build_splits(samples, b2_config)
    control_baselines = evaluate_baselines(materialized, b2_config)
    split_by_time = {item["feature_close_time_ms"]: item["split"] for item in splits["rows"]}
    features = _feature_by_time(materialized)
    records: dict[str, JevResponseRecord] = {}
    for feature in features.values():
        records[feature["input_fingerprint"]] = adapter.evaluate(_request_for(feature, config), deadline_ms=config.response_deadline_ms)
    normalized_samples: list[dict[str, Any]] = []
    for item in samples:
        feature = features[item["feature_close_time_ms"]]
        normalized_samples.append({**item, "input_fingerprint": feature["input_fingerprint"], "split": split_by_time.get(item["feature_close_time_ms"], "purged")})
    train = [item for item in normalized_samples if item["split"] == "train"]
    calibration = [item for item in normalized_samples if item["split"] == "calibration"]
    test = [item for item in normalized_samples if item["split"] == "test"]
    train_rates, train_fallback = _rates(train, lambda item: _group(item["feature_values"]))
    e1_raw = [(item["input_fingerprint"], train_rates.get(_group(item["feature_values"]), train_fallback)) for item in test]
    usable_train = [item for item in train if records[item["input_fingerprint"]].outcome == "usable"]
    e2_rates, e2_fallback = _rates(usable_train, lambda item: _e2_group(item, records[item["input_fingerprint"]]))
    e2_raw = []
    for item in test:
        record = records[item["input_fingerprint"]]
        if record.outcome == "usable":
            e2_raw.append((item["input_fingerprint"], e2_rates.get(_e2_group(item, record), train_rates.get(_group(item["feature_values"]), e2_fallback))))
    calibration_samples = {item["input_fingerprint"]: item for item in calibration}
    e1_calibration = [(item["input_fingerprint"], train_rates.get(_group(item["feature_values"]), train_fallback)) for item in calibration]
    e2_calibration = []
    for item in calibration:
        record = records[item["input_fingerprint"]]
        if record.outcome == "usable":
            e2_calibration.append((item["input_fingerprint"], e2_rates.get(_e2_group(item, record), train_rates.get(_group(item["feature_values"]), e2_fallback))))
    e1_calibrated, e1_calibration_meta = _calibration(e1_calibration, calibration_samples, e1_raw)
    e2_calibrated, e2_calibration_meta = _calibration(e2_calibration, calibration_samples, e2_raw)
    test_map = {item["input_fingerprint"]: item for item in test}
    metrics = {
        "E1_numerical_only": {
            "coverage": _coverage(test, None, e1_raw),
            "raw": _score(e1_raw, test_map),
            "calibrated": _calibrated_score(e1_calibrated, test_map, e1_calibration_meta),
        },
        "E2_numerical_plus_jev": {
            "coverage": _coverage(test, records, e2_raw),
            "raw": _score(e2_raw, test_map),
            "calibrated": _calibrated_score(e2_calibrated, test_map, e2_calibration_meta),
        },
    }
    matched = sorted(set(fp for fp, _ in e1_raw) & set(fp for fp, _ in e2_raw))
    e1_matched = [(fp, dict(e1_raw)[fp]) for fp in matched]
    e2_matched = [(fp, dict(e2_raw)[fp]) for fp in matched]
    e1_matched_score = _score(e1_matched, test_map)
    e2_matched_score = _score(e2_matched, test_map)
    deltas = {
        metric: e2_matched_score[metric] - e1_matched_score[metric]
        for metric in ("log_loss", "brier", "accuracy")
        if e1_matched_score[metric] is not None and e2_matched_score[metric] is not None
    }
    matched_controls = {
        "status": "measured" if matched else "unavailable",
        "n": len(matched),
        "same_inputs": True,
        "control": "E1_numerical_only",
        "candidate": "E2_numerical_plus_jev",
        "control_metrics": e1_matched_score,
        "candidate_metrics": e2_matched_score,
        "deltas_candidate_minus_control": deltas,
        "uncertainty": {"status": "not_estimated", "reason": "B3 records point estimates only; confidence intervals require a larger approved dataset"},
    }
    predictions = []
    for item in test:
        fp = item["input_fingerprint"]
        record = records[fp]
        e1 = dict(e1_raw)[fp]
        e2 = dict(e2_raw).get(fp)
        predictions.append({
            "input_feature_fingerprint": fp,
            "feature_close_time_ms": item["feature_close_time_ms"],
            "target_end_ms": item["target_end_ms"],
            "split": "test",
            "e1_probability_up": e1,
            "e2_probability_up": e2,
            "jev_outcome": record.outcome,
            "jev_response_fingerprint": record.response_fingerprint,
            "actual_direction": item["direction"],
        })
    response_dicts = [asdict(records[fp]) for fp in sorted(records)]
    return {
        "splits": splits,
        "responses": response_dicts,
        "predictions": predictions,
        "metrics": metrics,
        "calibration": {"E1_numerical_only": e1_calibration_meta, "E2_numerical_plus_jev": e2_calibration_meta},
        "control_baselines": control_baselines,
        "split_fingerprint": _sha(splits),
        "calibration_fingerprint": _sha({"E1_numerical_only": e1_calibration_meta, "E2_numerical_plus_jev": e2_calibration_meta}),
        "matched_controls": matched_controls,
        "failure_counts": _counts([record.case_kind for record in records.values() if record.outcome != "usable"]),
        "sample_count": len(samples),
    }


class B3Store:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.runs = self.root / "runs"
        self.runs.mkdir(exist_ok=True)

    def _run_dir(self, run_id: str) -> Path:
        path = (self.runs / run_id).resolve()
        if not path.is_relative_to(self.runs.resolve()):
            raise ValueError("invalid B3 run ID")
        return path

    def _write(self, path: Path, value: Any) -> dict[str, Any]:
        raw = _json(value).encode("utf-8")
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"immutable B3 artifact collision: {path.name}")
        if not path.exists():
            path.write_bytes(raw)
        return {"path": path.resolve().relative_to(self.root.resolve()).as_posix(), "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}

    def persist(self, run: dict[str, Any]) -> dict[str, Any]:
        directory = self._run_dir(run["run_id"])
        directory.mkdir(parents=True, exist_ok=True)
        artifacts = []
        for kind in ("config", "fixture_cases", "responses", "splits", "predictions", "metrics", "calibration", "control_baselines", "matched_controls", "report"):
            artifact = self._write(directory / f"{kind}.json", run[kind])
            artifacts.append({"kind": kind, **artifact, "lineage": [run["dataset_revision"], run["feature_fingerprint"], run["fixture_fingerprint"]]})
        lineage = {"dataset_revision": run["dataset_revision"], "feature_fingerprint": run["feature_fingerprint"], "fixture_fingerprint": run["fixture_fingerprint"], "artifact_lineage": artifacts}
        lineage_artifact = self._write(directory / "lineage.json", lineage)
        artifacts.append({"kind": "lineage", **lineage_artifact, "lineage": [item["sha256"] for item in artifacts]})
        manifest = {key: run[key] for key in ("schema", "api_version", "run_id", "experiment_version", "dataset_revision", "feature_fingerprint", "fixture_fingerprint", "request_fingerprint", "response_fingerprint", "split_fingerprint", "calibration_fingerprint", "sample_count", "promotion_decision")}
        manifest.update({"artifacts": artifacts, "replay_fingerprint": _sha({"run": run, "artifacts": artifacts}), "lineage": lineage})
        self._write(directory / "manifest.json", manifest)
        return manifest

    def _manifest(self, run_id: str) -> dict[str, Any]:
        directory = self._run_dir(run_id)
        path = directory / "manifest.json"
        if not path.is_file():
            raise KeyError(run_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def _artifact(self, manifest: dict[str, Any], kind: str) -> tuple[Path, dict[str, Any]]:
        artifact = next((item for item in manifest["artifacts"] if item["kind"] == kind), None)
        if artifact is None:
            raise KeyError(kind)
        path = (self.root / artifact["path"]).resolve()
        if not path.is_relative_to(self.root.resolve()) or not path.is_file():
            raise ValueError(f"B3 artifact path is missing or outside storage: {kind}")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != artifact["sha256"]:
            raise ValueError(f"B3 artifact hash mismatch: {kind}")
        return path, json.loads(raw)

    def inspect(self, run_id: str, resource: str = "manifest", item_id: str | None = None) -> Any:
        manifest = self._manifest(run_id)
        if resource == "manifest":
            return manifest
        if resource == "replay":
            return self.replay(run_id)
        if resource == "fingerprints":
            return {key: manifest[key] for key in ("dataset_revision", "feature_fingerprint", "fixture_fingerprint", "request_fingerprint", "response_fingerprint", "replay_fingerprint")}
        if resource == "abstentions":
            value = self._artifact(manifest, "responses")[1]
            return {"run_id": run_id, "resource": resource, "value": [item for item in value if item["abstention"]]}
        if resource == "artifacts":
            return manifest["artifacts"]
        value = self._artifact(manifest, resource)[1]
        if item_id is None:
            return {"run_id": run_id, "resource": resource, "value": value}
        if isinstance(value, list):
            return [item for item in value if str(item.get("case_id", item.get("input_feature_fingerprint", item.get("model", "")))) == item_id]
        raise KeyError(item_id)

    def replay(self, run_id: str) -> dict[str, Any]:
        manifest = self._manifest(run_id)
        if manifest.get("schema") != B3_RUN_SCHEMA or manifest.get("api_version") != B3_API_VERSION:
            raise ValueError("unsupported B3 run manifest")
        for artifact in manifest["artifacts"]:
            self._artifact(manifest, artifact["kind"])
        directory = self._run_dir(run_id)
        run = {key: json.loads((directory / f"{key}.json").read_text(encoding="utf-8")) for key in ("config", "fixture_cases", "responses", "splits", "predictions", "metrics", "calibration", "control_baselines", "matched_controls", "report")}
        run["failure_counts"] = run["report"].get("failure_counts", {})
        run.update({key: manifest[key] for key in ("schema", "api_version", "run_id", "experiment_version", "dataset_revision", "feature_fingerprint", "fixture_fingerprint", "request_fingerprint", "response_fingerprint", "split_fingerprint", "calibration_fingerprint", "sample_count", "promotion_decision")})
        expected = _sha({"run": run, "artifacts": manifest["artifacts"]})
        if expected != manifest["replay_fingerprint"]:
            raise ValueError("B3 replay fingerprint mismatch")
        return {"run_id": run_id, "replayed": True, "replay_fingerprint": manifest["replay_fingerprint"], "network_requests": 0, "provider_requests": 0}


def _promotion(evaluation: dict[str, Any]) -> dict[str, Any]:
    matched = evaluation["matched_controls"]
    return {
        "decision": "not-promoted",
        "reason": "B3 is an offline benchmark; promotion requires stable out-of-sample value, calibrated semantics, post-cost evidence, and prospective verification",
        "matched_control_status": matched["status"],
        "required_next_evidence": ["larger continuous local dataset", "confidence or uncertainty analysis", "cost-aware paper evaluation", "prospective shadow verification"],
    }


def run_b3(history: HistoryStore, dataset_revision: str, fixture: RecordedJevAdapter, store: B3Store, config: B3Config | None = None, *, experiment_id: str = "btc-b3-jev-offline") -> dict[str, Any]:
    manifest = history.inspect_manifest(dataset_revision)
    b2_config = B2Config(experiment_id, manifest["availability_timestamp_max"])
    materialized = materialize_rows(history.inspect_candles(dataset_revision), b2_config, dataset_revision=dataset_revision)
    if config is None:
        config = B3Config(experiment_id, dataset_revision, materialized["feature_fingerprint"], fixture.fixture_id)
    elif config.dataset_revision != dataset_revision or config.feature_fingerprint != materialized["feature_fingerprint"]:
        raise ValueError("B3 config does not match the frozen B2 dataset or feature fingerprint")
    evaluation = evaluate_b3(materialized, fixture, config)
    response_fingerprint = _sha(evaluation["responses"])
    request_fingerprint = _sha([item["request_fingerprint"] for item in evaluation["responses"]])
    identity = {"config": asdict(config), "fixture_fingerprint": fixture.fixture_fingerprint, "dataset_revision": dataset_revision, "feature_fingerprint": materialized["feature_fingerprint"]}
    run_id = f"btc-b3-{_sha(identity)[:20]}"
    report = {
        "schema": "market-os.u3-b3.report.v1",
        "status": "implemented-and-verified-offline",
        "experiment": {"version": B3_EXPERIMENT_VERSION, "question_id": B3_QUESTION_ID, "decision_question": B3_DECISION_QUESTION, "answer_schema": B3_ANSWER_SCHEMA},
        "source_boundary": {"dataset_revision": dataset_revision, "feature_fingerprint": materialized["feature_fingerprint"], "fixture_id": fixture.fixture_id, "fixture_fingerprint": fixture.fixture_fingerprint, "network_requests": 0, "provider_requests": 0},
        "coverage": {name: value["coverage"] for name, value in evaluation["metrics"].items()},
        "failures": evaluation["failure_counts"],
        "fixture_case_kinds": _counts([item["kind"] for item in fixture.inspect_cases()]),
        "failure_counts": evaluation["failure_counts"],
        "latency_usage_cost": {"latency": "unknown-not-observed-offline", "usage": "unknown-not-observed-offline", "cost": "unknown-not-observed-offline"},
        "matched_controls": evaluation["matched_controls"],
        "promotion": _promotion(evaluation),
        "scientific_boundary": "Jev is an experimental typed assessment; it is not BUY, SELL, an order, a risk override, execution authority, or a calibrated five-minute BTC return probability.",
    }
    run = {
        "schema": B3_RUN_SCHEMA,
        "api_version": B3_API_VERSION,
        "run_id": run_id,
        "experiment_version": B3_EXPERIMENT_VERSION,
        "dataset_revision": dataset_revision,
        "feature_fingerprint": materialized["feature_fingerprint"],
        "fixture_fingerprint": fixture.fixture_fingerprint,
        "request_fingerprint": request_fingerprint,
        "response_fingerprint": response_fingerprint,
        "split_fingerprint": evaluation["split_fingerprint"],
        "calibration_fingerprint": evaluation["calibration_fingerprint"],
        "sample_count": evaluation["sample_count"],
        "promotion_decision": "not-promoted",
        "config": asdict(config),
        "fixture_cases": fixture.inspect_cases(),
        **evaluation,
        "report": report,
    }
    persisted = store.persist(run)
    return {**run, "artifacts": persisted["artifacts"], "replay_fingerprint": persisted["replay_fingerprint"]}
