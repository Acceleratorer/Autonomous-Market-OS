"""Local synthetic session runner; no provider, network, or live execution."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .b34_strategy import NormalizedNumericalSignal, StrategyConfig
from .b35_strategy_replay import StrategyReplayReport, StrategySignalFixture, run_strategy_replay
from .b36_accounting import SyntheticAccountingReport, build_synthetic_accounting_report
from .paper_venue import SyntheticMarketEvent, VenueConfig


FIXTURE_SCHEMA = "market-os.b3-8.synthetic-session-fixture@v1"
MANIFEST_SCHEMA = "market-os.b3-8.synthetic-session-manifest@v1"
INTERPRETATION = "synthetic session fixture only; no predictive evidence, profitability claim, or promotion approval"
ARTIFACT_INTERPRETATION = "synthetic session artifacts only; replay and accounting observability"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _keys(value: Mapping[str, Any], required: set[str], optional: set[str], field: str) -> None:
    unknown = set(value) - required - optional
    missing = required - set(value)
    if unknown:
        raise ValueError(f"{field} contains unsupported fields: {sorted(unknown)}")
    if missing:
        raise ValueError(f"{field} is missing fields: {sorted(missing)}")


def _decode_strategy_config(value: Any) -> StrategyConfig:
    item = _mapping(value, "strategy_config")
    _keys(item, {"schema", "strategy_version", "buy_threshold", "sell_threshold", "allocation_fraction", "max_order_notional_usdt", "freshness_window_ms", "fingerprint"}, set(), "strategy_config")
    if item["schema"] != "market-os.b3-4.synthetic-strategy@v1":
        raise ValueError("unsupported strategy config schema")
    return StrategyConfig(
        strategy_version=item["strategy_version"],
        buy_threshold=item["buy_threshold"],
        sell_threshold=item["sell_threshold"],
        allocation_fraction=item["allocation_fraction"],
        max_order_notional_usdt=item["max_order_notional_usdt"],
        freshness_window_ms=item["freshness_window_ms"],
        fingerprint=item["fingerprint"],
    )


def _decode_venue_config(value: Any) -> VenueConfig:
    item = _mapping(value, "venue_config")
    _keys(item, {"schema", "venue_version", "fee_bps_per_side", "spread_bps_per_side", "slippage_bps_per_side", "initial_cash_usdt", "initial_btc_quantity", "initial_average_entry_price", "max_order_notional_usdt", "fingerprint"}, set(), "venue_config")
    if item["schema"] != "market-os.b3-2.virtual-paper-venue@v1":
        raise ValueError("unsupported venue config schema")
    return VenueConfig(
        venue_version=item["venue_version"],
        fee_bps_per_side=item["fee_bps_per_side"],
        spread_bps_per_side=item["spread_bps_per_side"],
        slippage_bps_per_side=item["slippage_bps_per_side"],
        initial_cash_usdt=item["initial_cash_usdt"],
        initial_btc_quantity=item["initial_btc_quantity"],
        initial_average_entry_price=item["initial_average_entry_price"],
        max_order_notional_usdt=item["max_order_notional_usdt"],
        fingerprint=item["fingerprint"],
    )


def _decode_event(value: Any) -> SyntheticMarketEvent:
    item = _mapping(value, "event")
    _keys(item, {"schema", "event_id", "symbol", "event_time_ms", "bid", "ask", "last", "volume", "source_fingerprint", "synthetic_only", "event_fingerprint"}, set(), "event")
    if item["schema"] != "market-os.b3-2.synthetic-market-event@v1":
        raise ValueError("unsupported market event schema")
    return SyntheticMarketEvent(
        item["event_id"], item["symbol"], item["event_time_ms"], item["bid"], item["ask"], item["last"],
        item["volume"], item["source_fingerprint"], item["synthetic_only"], item["event_fingerprint"],
    )


def _decode_signal(value: Any) -> NormalizedNumericalSignal:
    item = _mapping(value, "signal")
    _keys(item, {"schema", "signal_id", "symbol", "event_time_ms", "horizon_ms", "value_kind", "value", "status", "source_fingerprint", "synthetic_only", "fingerprint"}, set(), "signal")
    if item["schema"] != "market-os.b3-4.normalized-numerical-signal@v1":
        raise ValueError("unsupported numerical signal schema")
    return NormalizedNumericalSignal(
        item["signal_id"], item["symbol"], item["event_time_ms"], item["value_kind"], item["value"],
        item["status"], item["source_fingerprint"], item["horizon_ms"], item["synthetic_only"], item["fingerprint"],
    )


@dataclass(frozen=True)
class SyntheticSessionFixture:
    strategy_config: StrategyConfig
    venue_config: VenueConfig
    events: tuple[SyntheticMarketEvent, ...]
    signals: tuple[StrategySignalFixture, ...]
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.strategy_config, StrategyConfig) or not isinstance(self.venue_config, VenueConfig):
            raise ValueError("fixture configuration must use typed strategy and venue contracts")
        events = tuple(self.events)
        signals = tuple(self.signals)
        if not events:
            raise ValueError("synthetic session fixture requires at least one event")
        if any(not isinstance(event, SyntheticMarketEvent) for event in events):
            raise ValueError("fixture events must be typed synthetic market events")
        if any(not isinstance(signal, StrategySignalFixture) for signal in signals):
            raise ValueError("fixture signals must be typed strategy signal fixtures")
        event_ids = [event.event_id for event in events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("fixture contains duplicate event IDs")
        signal_ids = [signal.signal.signal_id for signal in signals]
        if len(signal_ids) != len(set(signal_ids)):
            raise ValueError("fixture contains duplicate signal IDs")
        if any(signal.event_id not in set(event_ids) for signal in signals):
            raise ValueError("fixture signal references an unknown event")
        projection = self.to_dict(include_fingerprint=False)
        if self.fingerprint:
            if self.fingerprint != _fingerprint(projection):
                raise ValueError("fixture fingerprint mismatch")
        else:
            object.__setattr__(self, "fingerprint", _fingerprint(projection))
        object.__setattr__(self, "events", events)
        object.__setattr__(self, "signals", signals)

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        result = {
            "schema": FIXTURE_SCHEMA,
            "synthetic_only": True,
            "interpretation": INTERPRETATION,
            "strategy_config": self.strategy_config.to_dict(),
            "venue_config": self.venue_config.to_dict(),
            "events": [event.to_dict() for event in self.events],
            "signals": [signal.to_dict() for signal in self.signals],
        }
        if include_fingerprint:
            result["fingerprint"] = self.fingerprint
        return result


def fixture_from_dict(value: Any) -> SyntheticSessionFixture:
    item = _mapping(value, "synthetic session fixture")
    _keys(item, {"schema", "synthetic_only", "interpretation", "strategy_config", "venue_config", "events", "signals"}, {"fingerprint"}, "synthetic session fixture")
    if item["schema"] != FIXTURE_SCHEMA or item["synthetic_only"] is not True or item["interpretation"] != INTERPRETATION:
        raise ValueError("fixture does not preserve the synthetic boundary")
    events_value = item["events"]
    signals_value = item["signals"]
    if not isinstance(events_value, list) or not isinstance(signals_value, list):
        raise ValueError("fixture events and signals must be arrays")
    events = tuple(_decode_event(event) for event in events_value)
    decoded_signals: list[StrategySignalFixture] = []
    for signal_value in signals_value:
        signal_item = _mapping(signal_value, "signal binding")
        _keys(signal_item, {"event_id", "signal"}, set(), "signal binding")
        decoded_signals.append(StrategySignalFixture(signal_item["event_id"], _decode_signal(signal_item["signal"])))
    signals = tuple(decoded_signals)
    return SyntheticSessionFixture(_decode_strategy_config(item["strategy_config"]), _decode_venue_config(item["venue_config"]), events, signals, item.get("fingerprint", ""))


def load_synthetic_fixture(path: str | Path) -> SyntheticSessionFixture:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read synthetic fixture: {exc}") from exc
    return fixture_from_dict(value)


@dataclass(frozen=True)
class SyntheticSessionRun:
    fixture: SyntheticSessionFixture
    replay: StrategyReplayReport
    accounting: SyntheticAccountingReport


def run_synthetic_fixture(fixture: SyntheticSessionFixture) -> SyntheticSessionRun:
    if not isinstance(fixture, SyntheticSessionFixture):
        raise ValueError("runner requires a typed synthetic session fixture")
    replay = run_strategy_replay(
        fixture.events,
        fixture.signals,
        strategy_config=fixture.strategy_config,
        venue_config=fixture.venue_config,
    )
    return SyntheticSessionRun(fixture, replay, build_synthetic_accounting_report(replay))


def write_synthetic_session_run(run: SyntheticSessionRun, output_dir: str | Path) -> dict[str, Any]:
    if not isinstance(run, SyntheticSessionRun):
        raise ValueError("writer requires a typed synthetic session run")
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    replay_path = directory / "strategy-replay.json"
    accounting_path = directory / "accounting.json"
    manifest_path = directory / "manifest.json"
    existing = [path.name for path in (replay_path, accounting_path, manifest_path) if path.exists()]
    if existing:
        raise FileExistsError(f"synthetic output artifacts already exist: {', '.join(existing)}")
    replay_path.write_text(json.dumps(run.replay.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    accounting_path.write_text(json.dumps(run.accounting.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_projection = {
        "schema": MANIFEST_SCHEMA,
        "synthetic_only": True,
        "interpretation": ARTIFACT_INTERPRETATION,
        "fixture_fingerprint": run.fixture.fingerprint,
        "replay_fingerprint": run.replay.fingerprint,
        "accounting_fingerprint": run.accounting.fingerprint,
        "files": {"replay": replay_path.name, "accounting": accounting_path.name},
    }
    manifest = {**manifest_projection, "fingerprint": _fingerprint(manifest_projection)}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**manifest, "output_dir": str(directory)}


__all__ = [
    "FIXTURE_SCHEMA",
    "MANIFEST_SCHEMA",
    "INTERPRETATION",
    "SyntheticSessionFixture",
    "SyntheticSessionRun",
    "fixture_from_dict",
    "load_synthetic_fixture",
    "run_synthetic_fixture",
    "write_synthetic_session_run",
]
