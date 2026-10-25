"""Synthetic-only normalized-signal strategy boundary for B3.4."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Mapping

from .paper_venue import BUY, MARKET, SELL, SYMBOL, SyntheticMarketEvent, VenueSnapshot, VirtualOrder

STRATEGY_SCHEMA = "market-os.b3-4.synthetic-strategy@v1"
STRATEGY_VERSION = "v1"
SIGNAL_STATUSES = frozenset({"usable", "unavailable", "stale", "abstained", "contradictory", "schema_invalid", "unsupported"})
VALUE_KINDS = frozenset({"calibrated_probability", "uncalibrated_score"})
ACTIONS = frozenset({"buy", "sell", "hold", "abstain", "reject"})
_FORBIDDEN = ("http://", "https://", "\\", "binance", "provider", "credential", "openai", "typesafe", "jev")

class StrategyError(ValueError):
    pass

def _plain(value: Any) -> Any:
    if isinstance(value, Mapping): return {str(k): _plain(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, (list, tuple)): return [_plain(v) for v in value]
    return value

def _canonical(value: Any) -> str:
    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)

def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()

def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 160 or any(t in value.lower() for t in _FORBIDDEN) or re.search(r"[\x00-\x1f]", value): raise StrategyError(f"{field} must be a bounded synthetic value")
    return value

def _time(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0: raise StrategyError(f"{field} must be a non-negative integer timestamp")
    return value

def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)): raise StrategyError(f"{field} must be finite")
    return float(value)

def _digest(value: Any, field: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value): raise StrategyError(f"{field} must be a SHA-256 fingerprint")

@dataclass(frozen=True)
class NormalizedNumericalSignal:
    signal_id: str
    symbol: str
    event_time_ms: int
    value_kind: str
    value: float
    status: str
    source_fingerprint: str
    horizon_ms: int = 300_000
    synthetic_only: bool = True
    fingerprint: str = ""
    def __post_init__(self) -> None:
        _text(self.signal_id, "signal_id")
        if self.symbol != SYMBOL: raise StrategyError("signal is restricted to BTCUSDT Spot")
        _time(self.event_time_ms, "event_time_ms"); _time(self.horizon_ms, "horizon_ms")
        if self.value_kind not in VALUE_KINDS: raise StrategyError("unsupported signal value kind")
        value = _finite(self.value, "value")
        if self.value_kind == "calibrated_probability" and not 0 <= value <= 1: raise StrategyError("probability must be within [0, 1]")
        if self.status not in SIGNAL_STATUSES: raise StrategyError("unsupported signal status")
        if self.synthetic_only is not True: raise StrategyError("signal must be synthetic-only")
        _digest(self.source_fingerprint, "source_fingerprint")
        object.__setattr__(self, "value", value)
        projection = self.to_dict(include_fingerprint=False)
        if self.fingerprint:
            _digest(self.fingerprint, "signal fingerprint")
            if self.fingerprint != _fp(projection): raise StrategyError("signal fingerprint mismatch")
        else: object.__setattr__(self, "fingerprint", _fp(projection))
    @property
    def probability(self) -> float | None: return self.value if self.value_kind == "calibrated_probability" else None
    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        result = {"schema": "market-os.b3-4.normalized-numerical-signal@v1", "signal_id": self.signal_id, "symbol": self.symbol, "event_time_ms": self.event_time_ms, "horizon_ms": self.horizon_ms, "value_kind": self.value_kind, "value": self.value, "status": self.status, "source_fingerprint": self.source_fingerprint, "synthetic_only": self.synthetic_only}
        if include_fingerprint: result["fingerprint"] = self.fingerprint
        return result

@dataclass(frozen=True)
class StrategyConfig:
    buy_threshold: float = 0.55
    sell_threshold: float = 0.45
    allocation_fraction: float = 1.0
    max_order_notional_usdt: float = 1_000.0
    freshness_window_ms: int = 300_000
    strategy_version: str = STRATEGY_VERSION
    fingerprint: str = ""
    def __post_init__(self) -> None:
        buy, sell = _finite(self.buy_threshold, "buy_threshold"), _finite(self.sell_threshold, "sell_threshold")
        allocation = _finite(self.allocation_fraction, "allocation_fraction")
        if not 0 <= sell < buy <= 1: raise StrategyError("thresholds must satisfy 0 <= sell < buy <= 1")
        if not 0 < allocation <= 1: raise StrategyError("allocation_fraction must be within (0, 1]")
        max_order = _finite(self.max_order_notional_usdt, "max_order_notional_usdt")
        if max_order <= 0: raise StrategyError("max_order_notional_usdt must be positive")
        _time(self.freshness_window_ms, "freshness_window_ms")
        if self.strategy_version != STRATEGY_VERSION: raise StrategyError("unsupported strategy version")
        projection = self.to_dict(include_fingerprint=False)
        if self.fingerprint:
            _digest(self.fingerprint, "strategy fingerprint")
            if self.fingerprint != _fp(projection): raise StrategyError("strategy fingerprint mismatch")
        else: object.__setattr__(self, "fingerprint", _fp(projection))
    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        result = {"schema": STRATEGY_SCHEMA, "strategy_version": self.strategy_version, "buy_threshold": self.buy_threshold, "sell_threshold": self.sell_threshold, "allocation_fraction": self.allocation_fraction, "max_order_notional_usdt": self.max_order_notional_usdt, "freshness_window_ms": self.freshness_window_ms}
        if include_fingerprint: result["fingerprint"] = self.fingerprint
        return result

@dataclass(frozen=True)
class StrategyDecision:
    decision_id: str
    action: str
    reason: str
    signal_fingerprint: str
    event_id: str
    event_time_ms: int
    order: VirtualOrder | None = None
    synthetic_only: bool = True
    fingerprint: str = ""
    def __post_init__(self) -> None:
        _text(self.decision_id, "decision_id"); _text(self.reason, "reason")
        if self.action not in ACTIONS: raise StrategyError("unsupported decision action")
        _digest(self.signal_fingerprint, "signal_fingerprint"); _text(self.event_id, "event_id"); _time(self.event_time_ms, "event_time_ms")
        if self.synthetic_only is not True: raise StrategyError("decision must be synthetic-only")
        if self.action in {"buy", "sell"} and not isinstance(self.order, VirtualOrder): raise StrategyError("trade decision requires an order")
        if self.action not in {"buy", "sell"} and self.order is not None: raise StrategyError("non-trade decision cannot carry an order")
        projection = self.to_dict(include_fingerprint=False)
        if self.fingerprint:
            _digest(self.fingerprint, "decision fingerprint")
            if self.fingerprint != _fp(projection): raise StrategyError("decision fingerprint mismatch")
        else: object.__setattr__(self, "fingerprint", _fp(projection))
    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        result = {"schema": "market-os.b3-4.strategy-decision@v1", "decision_id": self.decision_id, "action": self.action, "reason": self.reason, "signal_fingerprint": self.signal_fingerprint, "event_id": self.event_id, "event_time_ms": self.event_time_ms, "order": self.order.to_dict() if self.order else None, "synthetic_only": self.synthetic_only}
        if include_fingerprint: result["fingerprint"] = self.fingerprint
        return result

def decide(signal: NormalizedNumericalSignal, event: SyntheticMarketEvent, snapshot: VenueSnapshot, config: StrategyConfig | None = None) -> StrategyDecision:
    if not isinstance(signal, NormalizedNumericalSignal) or not isinstance(event, SyntheticMarketEvent) or not isinstance(snapshot, VenueSnapshot): raise StrategyError("decide requires typed synthetic contracts")
    config = config or StrategyConfig()
    if event.event_time_ms < signal.event_time_ms: return _decision(signal, event, "reject", "event precedes signal", None)
    if event.event_time_ms - signal.event_time_ms > config.freshness_window_ms: return _decision(signal, event, "abstain", "signal is stale", None)
    if signal.status != "usable": return _decision(signal, event, "abstain", f"signal status is {signal.status}", None)
    if signal.probability is None: return _decision(signal, event, "abstain", "uncalibrated score cannot drive an order", None)
    probability, position = signal.probability, snapshot.position
    if snapshot.last_event_time_ms is not None and snapshot.last_event_time_ms > event.event_time_ms:
        return _decision(signal, event, "reject", "snapshot is from a future event", None)
    if snapshot.open_orders:
        return _decision(signal, event, "hold", "open orders must settle before another strategy order", None)
    if probability >= config.buy_threshold:
        if position.btc_quantity > 0: return _decision(signal, event, "hold", "buy threshold met but inventory is already positive", None)
        quantity = min(config.max_order_notional_usdt * config.allocation_fraction / event.ask, position.cash_usdt * config.allocation_fraction / event.ask)
        if quantity <= 0: return _decision(signal, event, "reject", "insufficient cash for a positive order", None)
        order = VirtualOrder("synthetic-order-" + signal.signal_id, SYMBOL, BUY, MARKET, quantity, None, event.event_time_ms + 1, "synthetic-b34-strategy")
        return _decision(signal, event, "buy", "probability meets buy threshold", order)
    if probability <= config.sell_threshold:
        if position.btc_quantity <= 0: return _decision(signal, event, "hold", "sell threshold met with no inventory", None)
        if position.btc_quantity * event.bid > config.max_order_notional_usdt:
            return _decision(signal, event, "reject", "sell-to-flat exceeds maximum order notional", None)
        order = VirtualOrder("synthetic-order-" + signal.signal_id, SYMBOL, SELL, MARKET, position.btc_quantity, None, event.event_time_ms + 1, "synthetic-b34-strategy")
        return _decision(signal, event, "sell", "probability meets sell threshold", order)
    return _decision(signal, event, "hold", "probability is inside hold band", None)

def _decision(signal: NormalizedNumericalSignal, event: SyntheticMarketEvent, action: str, reason: str, order: VirtualOrder | None) -> StrategyDecision:
    return StrategyDecision("synthetic-decision-" + signal.signal_id + "-" + event.event_id, action, reason, signal.fingerprint, event.event_id, event.event_time_ms, order)

class SyntheticStrategyAdapter:
    """One-pass signal consumer; positions remain owned by the caller's venue."""

    def __init__(self, config: StrategyConfig | None = None) -> None:
        self.config = config or StrategyConfig()
        self._signals: set[str] = set()
        self._events: set[str] = set()
        self._last_event_time_ms: int | None = None

    def decide(self, signal: NormalizedNumericalSignal, event: SyntheticMarketEvent, snapshot: VenueSnapshot) -> StrategyDecision:
        if not isinstance(signal, NormalizedNumericalSignal) or not isinstance(event, SyntheticMarketEvent):
            raise StrategyError("adapter requires typed synthetic signal and event")
        if signal.signal_id in self._signals or event.event_id in self._events:
            return _decision(signal, event, "reject", "duplicate signal or event identity", None)
        if self._last_event_time_ms is not None and event.event_time_ms <= self._last_event_time_ms:
            return _decision(signal, event, "reject", "events must be strictly chronological", None)
        result = decide(signal, event, snapshot, self.config)
        self._signals.add(signal.signal_id)
        self._events.add(event.event_id)
        self._last_event_time_ms = event.event_time_ms
        return result

__all__ = ["STRATEGY_SCHEMA", "STRATEGY_VERSION", "SIGNAL_STATUSES", "NormalizedNumericalSignal", "StrategyConfig", "StrategyDecision", "StrategyError", "SyntheticStrategyAdapter", "decide"]
