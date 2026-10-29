from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from pathlib import Path

from market_os.paper_venue import BUY, LIMIT, MARKET, SyntheticMarketEvent
from market_os.portfolio_broker import B41Approval, B41Broker, B41Genesis, B41Order, B41Policy


def policy(**overrides: object) -> B41Policy:
    values: dict[str, object] = {
        "max_inventory_btc": Decimal("10"),
        "max_loss_usdt": Decimal("500"),
        "max_drawdown_usdt": Decimal("500"),
        "loss_window_ms": 86_400_000,
    }
    values.update(overrides)
    return B41Policy(**values)


def genesis(policy_value: B41Policy | None = None) -> B41Genesis:
    return B41Genesis.create("lifecycle-strategy", "synthetic-fixture-v1", policy_value or policy())


def order(value: B41Genesis, order_id: str, *, order_type: str = MARKET, limit_price: str | None = None, quantity: str = "0.1", time_ms: int = 900) -> B41Order:
    return B41Order(value.portfolio_id, order_id, f"cmd-{order_id}", f"key-{order_id}", BUY, order_type, Decimal(quantity), Decimal(limit_price) if limit_price is not None else None, time_ms)


def approval(value: B41Order, approval_id: str | None = None) -> B41Approval:
    return B41Approval.for_command(approval_id or f"approval-{value.order_id}", "owner", value.command_fingerprint, 800, 10_000)


def market_event(event_id: str, *, time_ms: int = 1_000, volume: float = 10, ask: float = 101, bid: float | None = None) -> SyntheticMarketEvent:
    bid_value = bid if bid is not None else min(100, ask)
    last = (bid_value + ask) / 2
    return SyntheticMarketEvent(event_id, "BTCUSDT", time_ms, bid_value, ask, last, volume, "synthetic-source-v1")


def cancel_approval(value: B41Genesis, order_id: str, *, command_id: str, idempotency_key: str, submitted_at_ms: int) -> B41Approval:
    projection = {
        "portfolio_id": value.portfolio_id,
        "order_id": order_id,
        "command_id": command_id,
        "idempotency_key": idempotency_key,
        "submitted_at_ms": submitted_at_ms,
    }
    fingerprint = hashlib.sha256(json.dumps(projection, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return B41Approval.for_command(f"approval-{command_id}", "owner", fingerprint, 800, 10_000)


def test_market_fill_ignores_informational_event_volume_and_fills_fully(tmp_path: Path) -> None:
    value = genesis()
    broker = B41Broker(tmp_path, value, policy())
    submitted = order(value, "order-volume")
    broker.submit_order(submitted, approval(submitted))

    result = broker.process_market_event(market_event("event-zero-volume", volume=0))

    assert result["fills"][0]["quantity"] == Decimal("0.1")
    assert broker.inspect("orders")["orders"][0]["state"] == "filled"


def test_unmatched_limit_stays_open_and_keeps_reservation_until_match(tmp_path: Path) -> None:
    value = genesis(policy(initial_cash_usdt=Decimal("100")))
    broker = B41Broker(tmp_path, value, policy(initial_cash_usdt=Decimal("100")))
    submitted = order(value, "order-limit", order_type=LIMIT, limit_price="100", quantity="0.5")
    broker.submit_order(submitted, approval(submitted))

    broker.process_market_event(market_event("event-unmatched", time_ms=100_000_000, ask=101))
    assert broker.inspect("orders")["orders"][0]["state"] == "open"
    assert broker.inspect("reservations")["cash_usdt"] > Decimal("50")

    broker.process_market_event(market_event("event-match", time_ms=100_000_001, ask=100, bid=99))
    assert broker.inspect("orders")["orders"][0]["state"] == "filled"
    assert broker.inspect("reservations")["cash_usdt"] == Decimal("0")


def test_accepted_order_fifo_beats_submitted_timestamp(tmp_path: Path) -> None:
    value = genesis()
    broker = B41Broker(tmp_path, value, policy())
    first = order(value, "order-first", time_ms=950)
    second = order(value, "order-second", time_ms=900)
    broker.submit_order(first, approval(first))
    broker.submit_order(second, approval(second))

    result = broker.process_market_event(market_event("event-fifo"))

    assert [fill["order_id"] for fill in result["fills"]] == ["order-first", "order-second"]


def test_cancel_releases_reservation_and_recovery_preserves_terminal_state(tmp_path: Path) -> None:
    value = genesis(policy(initial_cash_usdt=Decimal("100")))
    broker = B41Broker(tmp_path, value, policy(initial_cash_usdt=Decimal("100")))
    submitted = order(value, "order-cancel", order_type=LIMIT, limit_price="100", quantity="0.5")
    broker.submit_order(submitted, approval(submitted))
    assert broker.inspect("reservations")["cash_usdt"] > Decimal("50")

    cancel = cancel_approval(value, submitted.order_id, command_id="cancel-order", idempotency_key="cancel-key", submitted_at_ms=950)
    result = broker.cancel_order(value.portfolio_id, submitted.order_id, "cancel-order", "cancel-key", 950, cancel)
    ledger = broker.ledger_path.read_bytes()
    assert broker.cancel_order(value.portfolio_id, submitted.order_id, "cancel-order", "cancel-key", 950, cancel) == result
    assert broker.ledger_path.read_bytes() == ledger

    assert broker.inspect("reservations")["cash_usdt"] == Decimal("0")
    assert B41Broker.open(tmp_path, value.portfolio_id).inspect("orders") == broker.inspect("orders")


def test_fill_time_risk_rejection_releases_reservation(tmp_path: Path) -> None:
    value = genesis(policy(max_order_notional_usdt=Decimal("100")))
    broker = B41Broker(tmp_path, value, policy(max_order_notional_usdt=Decimal("100")))
    submitted = order(value, "order-risk", quantity="2")
    broker.submit_order(submitted, approval(submitted))

    result = broker.process_market_event(market_event("event-risk"))

    assert result["orders"][0]["state"] == "risk_rejected"
    assert broker.inspect("orders")["orders"][0]["state"] == "risk_rejected"
    assert broker.inspect("reservations")["cash_usdt"] == Decimal("0")
    recovered = B41Broker.open(tmp_path, value.portfolio_id)
    assert recovered.inspect("replay") == broker.inspect("replay")
    assert recovered.inspect("risk") == broker.inspect("risk")
