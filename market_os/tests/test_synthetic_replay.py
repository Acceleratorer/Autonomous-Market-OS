from __future__ import annotations

from dataclasses import replace
import json
import threading

import pytest

from market_os.paper_venue import (
    BUY,
    MARKET,
    SELL,
    InvalidMarketEvent,
    SyntheticMarketEvent,
    VenueConfig,
    VirtualOrder,
    VirtualPaperVenue,
    replay_virtual_venue,
)
from market_os.synthetic_replay import (
    STATUS_COMPLETED,
    ReplayCommand,
    ReplayError,
    ReplaySession,
    ReplayStateError,
    replay_synthetic,
    verify_deterministic_replay,
)


def event(event_id: str, time_ms: int = 1_000, bid: float = 100.0, ask: float = 101.0) -> SyntheticMarketEvent:
    return SyntheticMarketEvent(event_id, "BTCUSDT", time_ms, bid, ask, (bid + ask) / 2.0, 10.0, "synthetic-source-v1")


def order(order_id: str, side: str = BUY, time_ms: int = 900, quantity: float = 1.0) -> VirtualOrder:
    return VirtualOrder(order_id, "BTCUSDT", side, MARKET, quantity, None, time_ms, f"client-{order_id}")


def session(config: VenueConfig | None = None) -> ReplaySession:
    return ReplaySession(
        [event("event-1"), event("event-2", 2_000, 102.0, 103.0)],
        [order("buy-1"), order("sell-1", SELL, 1_500)],
        config,
    )


def test_deterministic_full_replay_and_stable_fingerprint() -> None:
    first = replay_synthetic([event("event-1"), event("event-2", 2_000, 102.0, 103.0)], [order("buy-1"), order("sell-1", SELL, 1_500)])
    second = replay_synthetic([event("event-1"), event("event-2", 2_000, 102.0, 103.0)], [order("buy-1"), order("sell-1", SELL, 1_500)])
    assert verify_deterministic_replay(first, second)
    assert first.to_dict() == second.to_dict()
    assert first.replay_fingerprint == second.replay_fingerprint
    assert json.dumps(first.to_dict(), sort_keys=True, separators=(",", ":")) == json.dumps(second.to_dict(), sort_keys=True, separators=(",", ":"))


def test_step_by_step_replay_equals_full_replay() -> None:
    full = session().run()
    stepped = session()
    stepped.step()
    stepped.step()
    assert stepped.to_dict() == full.to_dict()


def test_pause_resume_does_not_change_output() -> None:
    paused = session()
    paused.pause()
    with pytest.raises(ReplayStateError, match="paused"):
        paused.step()
    paused.resume()
    paused.run()
    assert paused.to_dict() == session().run().to_dict()


def test_reset_restores_exact_initial_state() -> None:
    replay = session()
    initial = replay.to_dict()
    replay.run()
    replay.reset()
    assert replay.to_dict() == initial
    replay.run()
    assert replay.to_dict() == session().run().to_dict()


def test_pending_commands_wait_for_a_later_event() -> None:
    replay = ReplaySession([event("event-1"), event("event-2", 2_000, 102.0, 103.0)], [order("future", BUY, 1_500)])
    first = replay.step()
    assert first.accepted_commands == ()
    assert replay.pending_commands[0].command_id == "future"
    second = replay.step()
    assert [item.command_id for item in second.accepted_commands] == ["future"]
    assert replay.final_venue_snapshot.fills[0].order_id == "future"


def test_rejected_commands_remain_explicit() -> None:
    replay = ReplaySession([event("event-1")], [order("too-large")], VenueConfig(initial_cash_usdt=1.0, max_order_notional_usdt=10_000.0))
    step = replay.step()
    assert len(step.rejected_commands) == 1
    assert "insufficient cash" in step.rejected_commands[0].reason
    assert replay.final_venue_snapshot.fills == ()


def test_duplicate_and_non_monotonic_events_are_rejected() -> None:
    with pytest.raises(InvalidMarketEvent, match="duplicate"):
        ReplaySession([event("event-1"), event("event-1", 2_000)], [])
    with pytest.raises(InvalidMarketEvent, match="strictly increasing"):
        ReplaySession([event("event-1", 2_000), event("event-2", 1_000)], [])
    replay = session()
    replay.step()
    with pytest.raises(InvalidMarketEvent, match="duplicate"):
        replay.step(event("event-1", 1_000))


def test_completed_session_rejects_further_processing_until_reset() -> None:
    replay = ReplaySession([event("event-1")], []).run()
    assert replay.status == STATUS_COMPLETED
    with pytest.raises(ReplayStateError, match="reset"):
        replay.step()
    replay.reset()
    assert replay.status != STATUS_COMPLETED


def test_tampered_fingerprints_fail_closed() -> None:
    with pytest.raises(ValueError, match="mismatch"):
        replace(ReplayCommand("cmd", 900, order("order")), fingerprint="0" * 64)
    with pytest.raises(ValueError, match="mismatch"):
        replace(session().clock, fingerprint="0" * 64)
    replay = session().run()
    with pytest.raises(ValueError, match="mismatch"):
        replace(replay.steps[0], step_fingerprint="0" * 64)


def test_non_synthetic_identity_is_rejected() -> None:
    with pytest.raises(ValueError, match="synthetic"):
        SyntheticMarketEvent("event", "BTCUSDT", 1_000, 100, 101, 100.5, 1, "provider-source")
    with pytest.raises(ReplayError, match="non-synthetic"):
        ReplaySession([event("event-1")], [], session_id="https://example.invalid")


def test_venue_snapshot_remains_accounting_source_of_truth() -> None:
    events = [event("event-1"), event("event-2", 2_000, 102.0, 103.0)]
    orders = [order("buy-1"), order("sell-1", SELL, 1_500)]
    replay = ReplaySession(events, orders).run()
    direct = replay_virtual_venue(VenueConfig(), events, orders)
    assert replay.final_venue_snapshot.to_dict() == direct.to_dict()
    assert replay.final_venue_snapshot.position.total_fees_usdt >= 0.0
    assert replay.final_venue_snapshot.position.btc_quantity >= 0.0
    assert not hasattr(replay.final_venue_snapshot.position, "leverage")


def test_no_wall_clock_or_background_thread_dependency() -> None:
    before = {thread.ident for thread in threading.enumerate()}
    replay = session().run()
    after = {thread.ident for thread in threading.enumerate()}
    assert before == after
    assert replay.clock.step_mode is True
    assert replay.clock.speed == 0.0
    assert not hasattr(replay, "leverage")
    assert not hasattr(replay, "futures")
    assert not hasattr(replay, "perpetual")


def test_commands_cannot_be_backdated_after_an_event() -> None:
    replay = ReplaySession([event("event-1"), event("event-2", 2_000, 102.0, 103.0)], [])
    replay.step()
    replay.submit_command(order("late", BUY, 1_000))
    replay.step()
    assert replay.pending_commands == ()
    assert replay.steps[1].rejected_commands[0].reason == "order timestamp would backdate into an already processed event"


def test_replay_command_requires_matching_order_timestamp() -> None:
    with pytest.raises(ReplayError, match="timestamps"):
        ReplayCommand("cmd", 900, order("order", BUY, 901))

