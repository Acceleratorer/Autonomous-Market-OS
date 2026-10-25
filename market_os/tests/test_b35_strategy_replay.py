from __future__ import annotations

from dataclasses import replace
import json

import pytest

from market_os.b34_strategy import NormalizedNumericalSignal, StrategyConfig
from market_os.b35_strategy_replay import (
    StrategySignalFixture,
    run_strategy_replay,
    verify_strategy_replay,
)
from market_os.paper_venue import SyntheticMarketEvent, VenueConfig


def event(event_id: str, time_ms: int, bid: float = 100.0, ask: float = 101.0) -> SyntheticMarketEvent:
    return SyntheticMarketEvent(event_id, "BTCUSDT", time_ms, bid, ask, (bid + ask) / 2.0, 1.0, "a" * 64)


def signal(signal_id: str, time_ms: int, probability: float, status: str = "usable") -> NormalizedNumericalSignal:
    return NormalizedNumericalSignal(signal_id, "BTCUSDT", time_ms, "calibrated_probability", probability, status, "b" * 64)


def test_end_to_end_buy_then_sell_is_deterministic_and_delays_orders() -> None:
    events = (event("synthetic-e1", 1_000), event("synthetic-e2", 2_000, 102.0, 103.0), event("synthetic-e3", 3_000, 99.0, 100.0))
    fixtures = (
        StrategySignalFixture("synthetic-e1", signal("synthetic-s1", 1_000, 0.9)),
        StrategySignalFixture("synthetic-e2", signal("synthetic-s2", 2_000, 0.1)),
    )
    # The venue limit must cover the strategy's quantity at the later fill price.
    strategy_config = StrategyConfig(allocation_fraction=0.5)
    venue_config = VenueConfig()
    first = run_strategy_replay(events, fixtures, strategy_config=strategy_config, venue_config=venue_config)
    second = run_strategy_replay(events, fixtures, strategy_config=strategy_config, venue_config=venue_config)
    assert verify_strategy_replay(first, second)
    payload = first.to_dict()
    observations = payload["observations"]
    assert observations[0]["decision"]["action"] == "buy"
    assert observations[0]["command_state"] == "queued"
    assert observations[0]["replay_step"]["accepted_commands"] == []
    assert observations[1]["replay_step"]["accepted_commands"][0]["order"]["order_id"] == "synthetic-order-synthetic-s1"
    assert observations[1]["decision"]["action"] == "sell"
    assert payload["unexecuted_end_of_stream"] == []
    assert payload["replay"]["final_venue_snapshot"]["position"]["btc_quantity"] == 0.0


def test_nonusable_signal_abstains_without_order() -> None:
    report = run_strategy_replay(
        (event("synthetic-e1", 1_000),),
        (StrategySignalFixture("synthetic-e1", signal("synthetic-s1", 1_000, 0.9, "abstained")),),
    )
    observation = report.to_dict()["observations"][0]
    assert observation["decision"]["action"] == "abstain"
    assert observation["command"] is None
    assert observation["command_state"] == "no_order"


def test_terminal_order_is_explicitly_unexecuted() -> None:
    report = run_strategy_replay(
        (event("synthetic-e1", 1_000),),
        (StrategySignalFixture("synthetic-e1", signal("synthetic-s1", 1_000, 0.9)),),
    )
    payload = report.to_dict()
    assert payload["observations"][0]["command_state"] == "unexecuted_end_of_stream"
    assert len(payload["unexecuted_end_of_stream"]) == 1
    assert payload["replay"]["final_venue_snapshot"]["fills"] == []


def test_fixture_identity_and_event_binding_are_fail_closed() -> None:
    with pytest.raises(ValueError, match="unknown event"):
        run_strategy_replay((event("synthetic-e1", 1_000),), (StrategySignalFixture("synthetic-other", signal("synthetic-s1", 1_000, 0.9)),))
    with pytest.raises(ValueError, match="duplicate"):
        run_strategy_replay(
            (event("synthetic-e1", 1_000),),
            (
                StrategySignalFixture("synthetic-e1", signal("synthetic-s1", 1_000, 0.9)),
                StrategySignalFixture("synthetic-e1", signal("synthetic-s2", 1_000, 0.9)),
            ),
        )
    with pytest.raises(ValueError, match="mismatch"):
        run_strategy_replay((event("synthetic-e1", 1_000),), (StrategySignalFixture("synthetic-e1", replace(signal("synthetic-s1", 1_000, 0.9), fingerprint="0" * 64)),))


def test_report_is_self_fingerprint_excluded_and_configs_are_recorded() -> None:
    report = run_strategy_replay((event("synthetic-e1", 1_000),), (), venue_config=VenueConfig(initial_cash_usdt=500.0))
    payload = report.to_dict()
    assert payload["fingerprint"] == report.fingerprint
    assert payload["venue_config"]["initial_cash_usdt"] == 500.0
    canonical_payload = json.loads(report.canonical_payload)
    assert "fingerprint" not in canonical_payload
