from __future__ import annotations

from dataclasses import replace

import pytest

from market_os.paper_venue import (
    BUY,
    LIMIT,
    MARKET,
    SELL,
    InvalidMarketEvent,
    InvalidOrder,
    OrderRejected,
    SyntheticMarketEvent,
    VenueConfig,
    VirtualOrder,
    VirtualPaperVenue,
    replay_virtual_venue,
    verify_deterministic_replay,
)


def event(event_id: str, time_ms: int = 1_000, bid: float = 100.0, ask: float = 101.0, last: float = 100.5) -> SyntheticMarketEvent:
    return SyntheticMarketEvent(event_id, "BTCUSDT", time_ms, bid, ask, last, 10.0, "synthetic-source-v1")


def order(order_id: str, side: str, time_ms: int = 999, quantity: float = 1.0, order_type: str = MARKET, limit_price: float | None = None) -> VirtualOrder:
    return VirtualOrder(order_id, "BTCUSDT", side, order_type, quantity, limit_price, time_ms, f"client-{order_id}")


def test_deterministic_replay_and_snapshot_serialization() -> None:
    config = VenueConfig(fee_bps_per_side=10.0, slippage_bps_per_side=5.0)
    events = [event("event-1"), event("event-2", 2_000, 102.0, 103.0, 102.5)]
    orders = [order("order-1", BUY), order("order-2", SELL, 2_001)]
    first = replay_virtual_venue(config, events, orders)
    second = replay_virtual_venue(config, events, orders)
    assert verify_deterministic_replay(first, second)
    assert first.to_dict() == second.to_dict()
    assert first.fingerprint and first.replay_identity


def test_market_buy_and_sell_account_for_fee_slippage_and_pnl() -> None:
    venue = VirtualPaperVenue(VenueConfig(fee_bps_per_side=10.0, slippage_bps_per_side=10.0))
    venue.submit_order(order("buy-1", BUY, quantity=1.0))
    bought = venue.process_event(event("event-1"))
    fill = bought.fills[0]
    assert fill.fill_price == pytest.approx(101.101)
    assert fill.fee_amount == pytest.approx(0.101101)
    assert fill.slippage_cost == pytest.approx(0.101)
    assert bought.position.btc_quantity == pytest.approx(1.0)
    venue.submit_order(order("sell-1", SELL, 2_001, quantity=1.0))
    sold = venue.process_event(event("event-2", 3_000, 102.0, 103.0, 102.5))
    assert sold.position.btc_quantity == pytest.approx(0.0)
    assert sold.position.cash_usdt > 10_000.0
    assert sold.position.realized_pnl_usdt > 0.0
    assert sold.position.total_fees_usdt == pytest.approx(fill.fee_amount + sold.fills[-1].fee_amount)
    assert sold.position.total_notional_usdt == pytest.approx(fill.fill_price + sold.fills[-1].fill_price)


def test_limit_buy_and_sell_match_only_at_their_conditions() -> None:
    venue = VirtualPaperVenue()
    venue.submit_order(order("limit-buy", BUY, order_type=LIMIT, limit_price=100.0))
    waiting = venue.process_event(event("event-1"))
    assert len(waiting.fills) == 0
    assert len(waiting.open_orders) == 1
    filled_buy = venue.process_event(event("event-2", 2_000, 99.0, 100.0, 99.5))
    assert len(filled_buy.fills) == 1
    venue.submit_order(order("limit-sell", SELL, 2_001, order_type=LIMIT, limit_price=101.0))
    still_open = venue.process_event(event("event-3", 3_000, 100.0, 100.5, 100.25))
    assert len(still_open.open_orders) == 1
    filled_sell = venue.process_event(event("event-4", 4_000, 101.0, 102.0, 101.5))
    assert len(filled_sell.fills) == 2


def test_insufficient_cash_and_btc_are_rejected_without_negative_balances() -> None:
    venue = VirtualPaperVenue(VenueConfig(initial_cash_usdt=1.0, max_order_notional_usdt=10_000.0))
    venue.submit_order(order("too-large-buy", BUY, quantity=1.0))
    with pytest.raises(OrderRejected, match="insufficient cash"):
        venue.process_event(event("event-1"))
    assert venue.snapshot().position.cash_usdt == pytest.approx(1.0)
    venue = VirtualPaperVenue()
    with pytest.raises(OrderRejected, match="insufficient BTC"):
        venue.submit_order(order("sell-too-much", SELL, quantity=1.0))


@pytest.mark.parametrize(
    "factory, message",
    [
        (lambda: event("event", bid=0.0), "bid"),
        (lambda: SyntheticMarketEvent("event", "ETHUSDT", 1_000, 100, 101, 100.5, 1, "synthetic-source-v1"), "BTCUSDT"),
        (lambda: order("order", BUY, quantity=0.0), "quantity"),
        (lambda: VirtualOrder("order", "BTCUSDT", BUY, LIMIT, 1, None, 1_001, "client-order"), "limit_price"),
        (lambda: VirtualOrder("order", "BTCUSDT", BUY, MARKET, 1, 1.0, 1_001, "client-order"), "limit_price"),
    ],
)
def test_invalid_symbol_quantity_and_price_are_rejected(factory, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        factory()


def test_duplicate_events_orders_and_non_monotonic_events_are_rejected() -> None:
    venue = VirtualPaperVenue()
    venue.process_event(event("event-1"))
    with pytest.raises(InvalidMarketEvent, match="duplicate"):
        venue.process_event(event("event-1", 2_000))
    with pytest.raises(InvalidMarketEvent, match="strictly increasing"):
        venue.process_event(event("event-2", 500))
    venue = VirtualPaperVenue()
    venue.submit_order(order("order-1", BUY))
    with pytest.raises(InvalidOrder, match="duplicate"):
        venue.submit_order(order("order-1", BUY))


def test_order_timestamp_cannot_backdate_into_processed_event() -> None:
    venue = VirtualPaperVenue()
    venue.process_event(event("event-1", 1_000))
    with pytest.raises(InvalidOrder, match="backdate"):
        venue.submit_order(order("late-order", BUY, 1_000))
    venue.submit_order(order("future-order", BUY, 1_001))
    filled = venue.process_event(event("event-2", 2_000))
    assert [fill.order_id for fill in filled.fills] == ["future-order"]


def test_orders_must_be_submitted_in_timestamp_order() -> None:
    venue = VirtualPaperVenue()
    venue.submit_order(order("later", BUY, 1_200))
    with pytest.raises(InvalidOrder, match="timestamp order"):
        venue.submit_order(order("earlier", BUY, 1_100))


def test_non_synthetic_identity_and_tampered_fingerprints_fail_closed() -> None:
    with pytest.raises(InvalidMarketEvent, match="synthetic"):
        SyntheticMarketEvent("event", "BTCUSDT", 1_000, 100, 101, 100.5, 1, "real-source")
    with pytest.raises(InvalidMarketEvent, match="synthetic-only"):
        SyntheticMarketEvent("event", "BTCUSDT", 1_000, 100, 101, 100.5, 1, "synthetic-source-v1", False)
    with pytest.raises(ValueError, match="mismatch"):
        replace(event("event"), event_fingerprint="0" * 64)
    with pytest.raises(ValueError, match="mismatch"):
        replace(order("order", BUY), order_fingerprint="0" * 64)


def test_no_partial_fills_and_sell_only_long_only_behavior() -> None:
    venue = VirtualPaperVenue()
    venue.submit_order(order("buy", BUY, quantity=2.0))
    snapshot = venue.process_event(event("event-1"))
    assert len(snapshot.fills) == 1
    assert snapshot.fills[0].filled_quantity == pytest.approx(2.0)
    assert not hasattr(snapshot.position, "leverage")
    assert not hasattr(snapshot.position, "short_quantity")
    with pytest.raises(ValueError):
        VirtualOrder("short", "BTCUSDT", "short", MARKET, 1.0, None, 2_001, "client-short")


def test_initial_state_is_explicit_and_immutable() -> None:
    config = VenueConfig(initial_cash_usdt=500.0, initial_btc_quantity=0.0)
    venue = VirtualPaperVenue(config)
    position = venue.snapshot().position
    assert position.cash_usdt == 500.0
    assert position.btc_quantity == 0.0
    with pytest.raises(Exception):
        position.cash_usdt = 1.0


def test_explicit_initial_btc_can_be_sold_without_going_short() -> None:
    venue = VirtualPaperVenue(VenueConfig(initial_btc_quantity=2.0, initial_average_entry_price=90.0))
    venue.submit_order(order("sell-initial", SELL))
    snapshot = venue.process_event(event("event-1"))
    assert snapshot.position.btc_quantity == pytest.approx(1.0)
    assert snapshot.position.btc_quantity >= 0.0
