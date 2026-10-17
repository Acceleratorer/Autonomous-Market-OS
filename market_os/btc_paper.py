"""Offline BTCUSDT Spot experiment contracts and deterministic fixture replay."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import hashlib
import json
import math
import re
from typing import Any, Literal

from .contracts import ContractError, _timestamp

BTC_API_VERSION = "market-os.btc-paper.v1"
BTC_SYMBOL = "BTCUSDT"
FEATURE_VERSION = "btc.features.v1"
TARGET_VERSION = "btc.close-return-5m.v1"
_DIGEST_RE = re.compile(r"[0-9a-f]{64}")


def _fingerprint(value: Any) -> str:
    def normalize(item: Any) -> Any:
        if isinstance(item, float) and not math.isfinite(item):
            return {"__nonfinite_float__": "nan" if math.isnan(item) else "inf" if item > 0 else "-inf"}
        if isinstance(item, dict):
            return {key: normalize(child) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [normalize(child) for child in item]
        return item

    raw = json.dumps(normalize(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _check_timestamp_order(earlier: str, later: str, field: str) -> None:
    left = datetime.fromisoformat(earlier.replace("Z", "+00:00"))
    right = datetime.fromisoformat(later.replace("Z", "+00:00"))
    if right < left:
        raise ContractError("invalid_timestamp_order", f"{field} must not precede its source timestamp", field=field)


def _check_digest(value: str, field: str) -> None:
    if not isinstance(value, str) or not _DIGEST_RE.fullmatch(value):
        raise ContractError("invalid_digest", f"{field} must be a lowercase SHA-256 digest", field=field)


def _check_text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractError("required", f"{field} must not be empty", field=field)


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass(frozen=True)
class RawMarketEvent:
    event_id: str
    symbol: str
    source: str
    source_timestamp: str
    received_at: str
    availability_timestamp: str
    payload_fingerprint: str
    api_version: str = BTC_API_VERSION

    def __post_init__(self) -> None:
        _check_text(self.event_id, "event_id")
        _check_text(self.source, "source")
        if self.symbol != BTC_SYMBOL:
            raise ContractError("invalid_symbol", "B0 supports BTCUSDT only", field="symbol")
        for field in ("source_timestamp", "received_at", "availability_timestamp"):
            _timestamp(getattr(self, field), field)
        _check_timestamp_order(self.source_timestamp, self.received_at, "received_at")
        _check_timestamp_order(self.received_at, self.availability_timestamp, "availability_timestamp")
        _check_digest(self.payload_fingerprint, "payload_fingerprint")
        if self.api_version != BTC_API_VERSION:
            raise ContractError("unsupported_version", f"unsupported BTC contract version: {self.api_version}")


@dataclass(frozen=True)
class ClosedCandle:
    symbol: str
    interval: Literal["1m"]
    open_time: str
    close_time: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    source_timestamp: str
    received_at: str
    availability_timestamp: str
    provenance_id: str
    candle_fingerprint: str
    api_version: str = BTC_API_VERSION

    def __post_init__(self) -> None:
        if self.symbol != BTC_SYMBOL or self.interval != "1m":
            raise ContractError("invalid_instrument", "B0 supports BTCUSDT one-minute candles")
        for field in ("open_time", "close_time", "source_timestamp", "received_at", "availability_timestamp"):
            _timestamp(getattr(self, field), field)
        start = datetime.fromisoformat(self.open_time.replace("Z", "+00:00"))
        end = datetime.fromisoformat(self.close_time.replace("Z", "+00:00"))
        if end - start != timedelta(minutes=1):
            raise ContractError("invalid_candle_interval", "one-minute candle must span exactly 60 seconds")
        if start.second or start.microsecond:
            raise ContractError("invalid_candle_interval", "one-minute candle open_time must be minute-aligned")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in (self.open, self.high, self.low, self.close, self.volume)):
            raise ContractError("invalid_ohlcv", "OHLCV values must be finite numbers")
        if min(self.open, self.high, self.low, self.close) <= 0 or self.volume < 0:
            raise ContractError("invalid_ohlcv", "prices must be positive and volume non-negative")
        if self.high < max(self.open, self.close, self.low) or self.low > min(self.open, self.close, self.high):
            raise ContractError("invalid_ohlc_range", "high/low do not contain open and close")
        if datetime.fromisoformat(self.availability_timestamp.replace("Z", "+00:00")) < end:
            raise ContractError("candle_not_available", "closed candle cannot be available before close_time")
        _check_timestamp_order(self.close_time, self.source_timestamp, "source_timestamp")
        _check_timestamp_order(self.source_timestamp, self.received_at, "received_at")
        _check_timestamp_order(self.received_at, self.availability_timestamp, "availability_timestamp")
        _check_text(self.provenance_id, "provenance_id")
        _check_digest(self.candle_fingerprint, "candle_fingerprint")
        if self.api_version != BTC_API_VERSION:
            raise ContractError("unsupported_version", f"unsupported BTC contract version: {self.api_version}")


@dataclass(frozen=True)
class DatasetManifest:
    symbol: str
    interval: str
    candle_count: int
    first_open_time: str | None
    last_close_time: str | None
    input_fingerprint: str
    dataset_revision: str
    gaps: tuple[tuple[str, str], ...]
    api_version: str = BTC_API_VERSION

    def __post_init__(self) -> None:
        if self.symbol != BTC_SYMBOL or self.interval != "1m" or isinstance(self.candle_count, bool) or not isinstance(self.candle_count, int) or self.candle_count < 0:
            raise ContractError("invalid_manifest", "manifest requires BTCUSDT 1m candles")
        if self.candle_count == 0:
            if self.first_open_time is not None or self.last_close_time is not None:
                raise ContractError("invalid_manifest", "empty manifest time bounds must be null")
        else:
            _timestamp(self.first_open_time, "first_open_time")
            _timestamp(self.last_close_time, "last_close_time")
            if _datetime(self.last_close_time) <= _datetime(self.first_open_time):
                raise ContractError("invalid_manifest", "last_close_time must follow first_open_time")
        _check_digest(self.input_fingerprint, "input_fingerprint")
        if self.dataset_revision != f"btc-dataset-{self.input_fingerprint[:16]}":
            raise ContractError("invalid_revision", "dataset_revision must be derived from input_fingerprint")
        for start, end in self.gaps:
            _timestamp(start, "gap_start")
            _timestamp(end, "gap_end")
            if _datetime(end) <= _datetime(start):
                raise ContractError("invalid_gap", "gap end must follow gap start")
        if self.api_version != BTC_API_VERSION:
            raise ContractError("unsupported_version", f"unsupported BTC contract version: {self.api_version}")


@dataclass(frozen=True)
class FeatureRow:
    symbol: str
    feature_version: str
    candle_close_time: str
    source_timestamp: str
    received_at: str
    availability_timestamp: str
    decision_eligible_at: str
    observable_fields: tuple[str, ...]
    values: tuple[tuple[str, float], ...]
    dataset_revision: str
    input_fingerprint: str
    input_refs: tuple[str, ...]
    api_version: str = BTC_API_VERSION

    def __post_init__(self) -> None:
        if self.symbol != BTC_SYMBOL or self.feature_version != FEATURE_VERSION:
            raise ContractError("unsupported_feature", "feature row has unsupported symbol or version")
        for field in ("candle_close_time", "source_timestamp", "received_at", "availability_timestamp", "decision_eligible_at"):
            _timestamp(getattr(self, field), field)
        _check_timestamp_order(self.candle_close_time, self.source_timestamp, "source_timestamp")
        _check_timestamp_order(self.source_timestamp, self.received_at, "received_at")
        _check_timestamp_order(self.received_at, self.availability_timestamp, "availability_timestamp")
        _check_timestamp_order(self.availability_timestamp, self.decision_eligible_at, "decision_eligible_at")
        _check_text(self.dataset_revision, "dataset_revision")
        _check_digest(self.input_fingerprint, "input_fingerprint")
        if self.dataset_revision != f"btc-dataset-{self.input_fingerprint[:16]}":
            raise ContractError("invalid_revision", "feature dataset revision must derive from its input fingerprint")
        if not self.input_refs or any(not value.strip() for value in self.input_refs):
            raise ContractError("invalid_feature_lineage", "feature row requires provenance input references")
        if set(self.observable_fields) != {"open", "high", "low", "close", "volume"}:
            raise ContractError("invalid_feature_lineage", "observable fields must be exactly the closed-candle OHLCV inputs")
        if any(not name or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for name, value in self.values):
            raise ContractError("invalid_feature", "feature values must be finite")
        if any(name.startswith("target") or name.startswith("label") for name, _ in self.values):
            raise ContractError("label_leakage", "labels cannot be observable feature values")
        if any(name not in {"close", "log_return_1m"} for name, _ in self.values):
            raise ContractError("unsupported_feature", "feature value name is not defined by the B0 feature version")
        if len({name for name, _ in self.values}) != len(self.values) or len(set(self.input_refs)) != len(self.input_refs):
            raise ContractError("invalid_feature_lineage", "feature names and input references must be unique")
        if any(name.startswith("target") or name.startswith("label") for name in self.observable_fields):
            raise ContractError("label_leakage", "labels cannot be observable feature inputs")
        if self.api_version != BTC_API_VERSION:
            raise ContractError("unsupported_version", f"unsupported BTC contract version: {self.api_version}")


@dataclass(frozen=True)
class LabelRow:
    symbol: str
    target_version: str
    feature_candle_close_time: str
    target_end: str
    target_return: float
    direction: Literal["up", "flat", "down"]
    feature_input_fingerprint: str
    target_fingerprint: str
    target_refs: tuple[str, ...]
    api_version: str = BTC_API_VERSION

    def __post_init__(self) -> None:
        if self.symbol != BTC_SYMBOL or self.target_version != TARGET_VERSION:
            raise ContractError("unsupported_target", "label row has unsupported symbol or target version")
        _timestamp(self.feature_candle_close_time, "feature_candle_close_time")
        _timestamp(self.target_end, "target_end")
        if _datetime(self.target_end) - _datetime(self.feature_candle_close_time) != timedelta(minutes=5):
            raise ContractError("invalid_target_horizon", "label target_end must be five minutes after feature close")
        if isinstance(self.target_return, bool) or not isinstance(self.target_return, (int, float)) or not math.isfinite(self.target_return):
            raise ContractError("invalid_target", "target return must be finite")
        expected = "up" if self.target_return > 0 else "down" if self.target_return < 0 else "flat"
        if self.direction not in {"up", "flat", "down"} or self.direction != expected:
            raise ContractError("invalid_target", "direction must match target_return")
        _check_digest(self.feature_input_fingerprint, "feature_input_fingerprint")
        _check_digest(self.target_fingerprint, "target_fingerprint")
        if not self.target_refs or any(not value.strip() for value in self.target_refs):
            raise ContractError("invalid_target_lineage", "label requires target source references")
        if self.api_version != BTC_API_VERSION:
            raise ContractError("unsupported_version", f"unsupported BTC contract version: {self.api_version}")


@dataclass(frozen=True)
class PredictionRequest:
    experiment_id: str
    decision_eligible_at: str
    dataset_revision: str
    input_fingerprint: str
    feature_version: str
    api_version: str = BTC_API_VERSION

    def __post_init__(self) -> None:
        _check_text(self.experiment_id, "experiment_id")
        _timestamp(self.decision_eligible_at, "decision_eligible_at")
        _check_digest(self.input_fingerprint, "input_fingerprint")
        if self.dataset_revision != f"btc-dataset-{self.input_fingerprint[:16]}":
            raise ContractError("invalid_revision", "request dataset revision must match its point-in-time input fingerprint")
        if self.feature_version != FEATURE_VERSION:
            raise ContractError("unsupported_feature", "prediction request feature version is unsupported")
        if self.api_version != BTC_API_VERSION:
            raise ContractError("unsupported_version", f"unsupported BTC contract version: {self.api_version}")


@dataclass(frozen=True)
class PredictionResult:
    experiment_id: str
    decision_eligible_at: str
    dataset_revision: str
    input_fingerprint: str
    result_fingerprint: str
    status: Literal["fixture-only", "abstain"] = "fixture-only"
    action: Literal["none"] = "none"
    api_version: str = BTC_API_VERSION

    def __post_init__(self) -> None:
        _check_text(self.experiment_id, "experiment_id")
        _timestamp(self.decision_eligible_at, "decision_eligible_at")
        _check_digest(self.input_fingerprint, "input_fingerprint")
        if self.dataset_revision != f"btc-dataset-{self.input_fingerprint[:16]}":
            raise ContractError("invalid_revision", "result dataset revision must match its input fingerprint")
        _check_digest(self.result_fingerprint, "result_fingerprint")
        if self.status not in {"fixture-only", "abstain"} or self.action != "none":
            raise ContractError("invalid_status", "B0 prediction results cannot contain a model or action")
        if self.api_version != BTC_API_VERSION:
            raise ContractError("unsupported_version", f"unsupported BTC contract version: {self.api_version}")


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_id: str
    symbol: str = BTC_SYMBOL
    interval: str = "1m"
    horizon_minutes: int = 5
    max_staleness_seconds: int = 1800
    execution_mode: Literal["paper"] = "paper"
    api_version: str = BTC_API_VERSION

    def __post_init__(self) -> None:
        _check_text(self.experiment_id, "experiment_id")
        if self.symbol != BTC_SYMBOL or self.interval != "1m" or self.horizon_minutes != 5:
            raise ContractError("invalid_experiment_config", "B0 is BTCUSDT one-minute input with five-minute horizon")
        if isinstance(self.max_staleness_seconds, bool) or not isinstance(self.max_staleness_seconds, int) or self.max_staleness_seconds <= 0:
            raise ContractError("invalid_experiment_config", "max_staleness_seconds must be a positive integer")
        if self.execution_mode != "paper":
            raise ContractError("live_disabled", "BTC experiment is strictly paper-only", field="execution_mode")
        if self.api_version != BTC_API_VERSION:
            raise ContractError("unsupported_version", f"unsupported BTC contract version: {self.api_version}")


@dataclass(frozen=True)
class ReplayOutcome:
    event_id: str
    status: Literal["accepted", "duplicate", "conflict", "open", "invalid", "stale", "not_yet_available", "out_of_order"]
    reason: str | None = None


@dataclass(frozen=True)
class ReplayResult:
    provenance: tuple[RawMarketEvent, ...]
    candles: tuple[ClosedCandle, ...]
    manifest: DatasetManifest
    features: tuple[FeatureRow, ...]
    labels: tuple[LabelRow, ...]
    outcomes: tuple[ReplayOutcome, ...]


def replay_fixture(fixture: dict[str, Any]) -> ReplayResult:
    """Canonicalize synthetic events without clock, filesystem, or network input."""
    if not isinstance(fixture, dict) or fixture.get("schema") != "market-os.btc-paper-fixture.v1":
        raise ContractError("unsupported_fixture", "fixture schema must be market-os.btc-paper-fixture.v1")
    try:
        as_of = fixture["as_of"]
        fixture_config = fixture["config"]
    except KeyError as exc:
        raise ContractError("invalid_fixture", f"fixture is missing required field: {exc.args[0]}", field=exc.args[0]) from exc
    _timestamp(as_of, "as_of")
    as_of_time = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    config = btc_contract_from_json(json.dumps(fixture_config), ExperimentConfig)
    max_age = timedelta(seconds=config.max_staleness_seconds)
    if not isinstance(fixture.get("events"), list):
        raise ContractError("invalid_fixture", "fixture events must be an array", field="events")
    outcomes: list[ReplayOutcome] = []
    provenance: list[RawMarketEvent] = []
    seen: dict[str, str] = {}
    accepted: dict[str, ClosedCandle] = {}
    accepted_provenance: dict[str, RawMarketEvent] = {}
    accepted_outcome_index: dict[str, int] = {}
    for event_index, event in enumerate(fixture["events"]):
        event_id = event.get("event_id", f"event-{event_index}") if isinstance(event, dict) else f"event-{event_index}"
        if not isinstance(event_id, str) or not event_id.strip():
            event_id = f"event-{event_index}"
        if not isinstance(event, dict) or not isinstance(event.get("payload"), dict):
            outcomes.append(ReplayOutcome(event_id, "invalid", "event and payload must be objects"))
            continue
        payload = event["payload"]
        open_time = payload.get("open_time", "")
        try:
            fingerprint = _fingerprint(payload)
            event_fingerprint = _fingerprint({key: event[key] for key in event if key != "event_id"})
        except (TypeError, ValueError):
            outcomes.append(ReplayOutcome(event_id, "invalid", "event payload is not deterministically serializable"))
            continue
        raw_provenance = None
        try:
            raw_provenance = RawMarketEvent(
                event["event_id"], event["symbol"], event["source"], event["source_timestamp"],
                event["received_at"], event["availability_timestamp"], fingerprint,
            )
        except (ContractError, KeyError, TypeError, ValueError):
            pass
        if raw_provenance is not None:
            provenance.append(raw_provenance)
        if event_id in seen:
            same_payload = seen[event_id] == event_fingerprint
            outcomes.append(ReplayOutcome(event_id, "duplicate" if same_payload else "conflict", "event_id already observed" if same_payload else "event_id was reused with a different event"))
            continue
        seen[event_id] = event_fingerprint
        try:
            if event["symbol"] != BTC_SYMBOL or payload.get("interval") != "1m":
                raise ContractError("invalid_instrument", "expected BTCUSDT 1m candle")
            if payload.get("is_closed") is not True:
                raise ContractError("open_candle", "partial or open candle is not eligible")
            candle = ClosedCandle(
                event["symbol"], payload["interval"], open_time, payload["close_time"],
                payload["open"], payload["high"], payload["low"], payload["close"], payload["volume"],
                event["source_timestamp"], event["received_at"], event["availability_timestamp"], event_id,
                _fingerprint({key: payload[key] for key in ("open_time", "close_time", "open", "high", "low", "close", "volume")}),
            )
            available = datetime.fromisoformat(candle.availability_timestamp.replace("Z", "+00:00"))
            if available > as_of_time:
                outcomes.append(ReplayOutcome(event_id, "not_yet_available", "event availability is after replay as_of"))
                continue
            if as_of_time - available > max_age:
                outcomes.append(ReplayOutcome(event_id, "stale", "availability exceeds max_staleness_seconds"))
                continue
            if open_time in accepted:
                previous = accepted[open_time]
                if previous.candle_fingerprint != candle.candle_fingerprint:
                    conflict_reason = "different candle payloads share an open_time"
                    if candle.candle_fingerprint < previous.candle_fingerprint:
                        outcomes[accepted_outcome_index[open_time]] = ReplayOutcome(previous.provenance_id, "conflict", conflict_reason)
                        accepted[open_time] = candle
                        if raw_provenance is not None:
                            accepted_provenance[event_id] = raw_provenance
                        accepted_outcome_index[open_time] = len(outcomes)
                        outcomes.append(ReplayOutcome(event_id, "accepted"))
                    else:
                        outcomes.append(ReplayOutcome(event_id, "conflict", conflict_reason))
                elif candle.provenance_id < previous.provenance_id:
                    outcomes[accepted_outcome_index[open_time]] = ReplayOutcome(
                        previous.provenance_id, "duplicate", "identical candle canonicalized to stable event_id"
                    )
                    accepted[open_time] = candle
                    if raw_provenance is not None:
                        accepted_provenance[event_id] = raw_provenance
                    accepted_outcome_index[open_time] = len(outcomes)
                    outcomes.append(ReplayOutcome(event_id, "accepted"))
                else:
                    outcomes.append(ReplayOutcome(event_id, "duplicate", "identical candle already canonicalized"))
                continue
            accepted[open_time] = candle
            if raw_provenance is not None:
                accepted_provenance[event_id] = raw_provenance
            accepted_outcome_index[open_time] = len(outcomes)
            outcomes.append(ReplayOutcome(event_id, "accepted"))
        except (ContractError, KeyError, TypeError, ValueError) as exc:
            status = "open" if isinstance(exc, ContractError) and exc.code == "open_candle" else "invalid"
            outcomes.append(ReplayOutcome(event_id, status, str(exc)))

    ordered = tuple(accepted[key] for key in sorted(accepted))
    # Classify wire-order inversions while retaining canonical sorted output.
    accepted_ids = {item.provenance_id for item in ordered}
    event_positions: dict[str, int] = {}
    for index, event in enumerate(fixture["events"]):
        if isinstance(event, dict):
            event_id = event.get("event_id")
            event_positions.setdefault(event_id if isinstance(event_id, str) else f"event-{index}", index)
    arrival_sorted = sorted((candle for candle in ordered if candle.provenance_id in accepted_ids), key=lambda item: event_positions[item.provenance_id])
    prior_time: str | None = None
    for candle in arrival_sorted:
        if prior_time is not None and candle.open_time < prior_time:
            for index, outcome in enumerate(outcomes):
                if outcome.event_id == candle.provenance_id and outcome.status == "accepted":
                    outcomes[index] = ReplayOutcome(outcome.event_id, "out_of_order", "source event arrived out of chronological order")
        prior_time = candle.open_time

    opens = [datetime.fromisoformat(item.open_time.replace("Z", "+00:00")) for item in ordered]
    gaps: list[tuple[str, str]] = []
    for previous, current in zip(opens, opens[1:]):
        expected = previous + timedelta(minutes=1)
        if current > expected:
            gaps.append((expected.isoformat(), current.isoformat()))
    provenance_by_id = accepted_provenance
    if not ordered:
        empty_fingerprint = _fingerprint([])
        manifest = DatasetManifest(BTC_SYMBOL, "1m", 0, None, None, empty_fingerprint, f"btc-dataset-{empty_fingerprint[:16]}", ())
        return ReplayResult(tuple(provenance), (), manifest, (), (), tuple(outcomes))
    data_fingerprint = _fingerprint([
        {"candle": {key: value for key, value in asdict(item).items() if key != "provenance_id"},
         "provenance": {key: value for key, value in asdict(provenance_by_id[item.provenance_id]).items() if key != "event_id"}}
        for item in ordered
    ])
    revision = f"btc-dataset-{data_fingerprint[:16]}"
    manifest = DatasetManifest(BTC_SYMBOL, "1m", len(ordered), ordered[0].open_time, ordered[-1].close_time, data_fingerprint, revision, tuple(gaps))
    features: list[FeatureRow] = []
    labels: list[LabelRow] = []
    close_times = {_datetime(item.close_time): index for index, item in enumerate(ordered)}
    for index, candle in enumerate(ordered):
        decision_time = max(_datetime(candle.close_time), _datetime(candle.availability_timestamp))
        visible = [
            item for item in ordered
            if _datetime(item.close_time) <= decision_time
            and _datetime(item.close_time) <= _datetime(candle.close_time)
            and _datetime(item.availability_timestamp) <= decision_time
        ]
        input_records = [
            {"candle": {key: value for key, value in asdict(item).items() if key != "provenance_id"},
             "provenance": {key: value for key, value in asdict(provenance_by_id[item.provenance_id]).items() if key != "event_id"}}
            for item in visible
        ]
        input_fingerprint = _fingerprint(input_records)
        feature_revision = f"btc-dataset-{input_fingerprint[:16]}"
        prior = next((item for item in reversed(visible) if item.close_time < candle.close_time), None)
        log_return = math.log(candle.close / prior.close) if prior else 0.0
        feature = FeatureRow(BTC_SYMBOL, FEATURE_VERSION, candle.close_time, candle.source_timestamp, candle.received_at, candle.availability_timestamp, decision_time.isoformat(), ("open", "high", "low", "close", "volume"), (("close", candle.close), ("log_return_1m", log_return)), feature_revision, input_fingerprint, tuple(item.provenance_id for item in visible))
        features.append(feature)
        target_time = _datetime(candle.close_time) + timedelta(minutes=5)
        target_index = close_times.get(target_time)
        if target_index is not None and _datetime(ordered[target_index].availability_timestamp) <= as_of_time and all(
            _datetime(ordered[position].close_time) - _datetime(ordered[position - 1].close_time) == timedelta(minutes=1)
            for position in range(index + 1, target_index + 1)
        ):
            future = ordered[target_index]
            value = math.log(future.close / candle.close)
            target_fingerprint = _fingerprint({"feature_input_fingerprint": input_fingerprint, "future_candle": {key: value for key, value in asdict(future).items() if key != "provenance_id"}, "future_provenance": {key: value for key, value in asdict(provenance_by_id[future.provenance_id]).items() if key != "event_id"}})
            labels.append(LabelRow(BTC_SYMBOL, TARGET_VERSION, candle.close_time, future.close_time, value, "up" if value > 0 else "down" if value < 0 else "flat", input_fingerprint, target_fingerprint, (future.provenance_id,)))
    return ReplayResult(tuple(provenance), ordered, manifest, tuple(features), tuple(labels), tuple(outcomes))


_BTC_READERS: dict[type[Any], Any] = {
    RawMarketEvent: RawMarketEvent,
    ClosedCandle: ClosedCandle,
    DatasetManifest: DatasetManifest,
    FeatureRow: FeatureRow,
    LabelRow: LabelRow,
    PredictionRequest: PredictionRequest,
    PredictionResult: PredictionResult,
    ExperimentConfig: ExperimentConfig,
}
_JSON_CONSTANT_ERROR = object()


def _reject_json_constant(value: str) -> Any:
    return _JSON_CONSTANT_ERROR


def _contains_json_constant(value: Any) -> bool:
    if value is _JSON_CONSTANT_ERROR:
        return True
    if isinstance(value, dict):
        return any(_contains_json_constant(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_json_constant(item) for item in value)
    return False


def btc_contract_from_json(payload: str | bytes, contract_type: type[Any]) -> Any:
    """Decode one B0 contract and normalize JSON arrays to immutable tuples."""
    reader = _BTC_READERS.get(contract_type)
    if reader is None:
        raise TypeError(f"unsupported BTC contract type: {contract_type!r}")
    try:
        values = json.loads(payload, parse_constant=_reject_json_constant)
        if not isinstance(values, dict):
            raise ContractError("invalid_payload", "BTC contract payload must be an object")
        if _contains_json_constant(values):
            raise ContractError("invalid_json", "BTC contract payload contains a non-finite JSON number")
        expected = set(reader.__dataclass_fields__)
        unknown = sorted(set(values) - expected)
        if unknown:
            raise ContractError("unknown_field", f"unknown BTC contract field: {unknown[0]}", field=unknown[0])
        values.setdefault("api_version", BTC_API_VERSION)
        tuple_fields = {
            DatasetManifest: ("gaps",),
            FeatureRow: ("observable_fields", "values", "input_refs"),
            LabelRow: ("target_refs",),
        }.get(contract_type, ())
        for name in tuple_fields:
            if name in values:
                values[name] = tuple(tuple(item) if isinstance(item, list) else item for item in values[name])
        return reader(**values)
    except json.JSONDecodeError as exc:
        raise ContractError("invalid_json", "BTC contract payload is not valid JSON") from exc
    except (UnicodeDecodeError, AttributeError) as exc:
        raise ContractError("invalid_json", "BTC contract payload must be UTF-8 JSON") from exc
    except TypeError as exc:
        raise ContractError("missing_field", f"BTC contract payload is missing a required field: {exc}") from exc


def btc_contract_to_json(value: Any) -> str:
    if type(value) not in _BTC_READERS:
        raise TypeError("value must be a supported B0 BTC contract")
    return json.dumps(asdict(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
