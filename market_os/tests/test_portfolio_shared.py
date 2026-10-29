from __future__ import annotations

from decimal import Decimal
import hashlib
from pathlib import Path

import pytest

from market_os.paper_venue import BUY, LIMIT, MARKET, SELL, SyntheticMarketEvent
from market_os.portfolio_broker import (
    B41Approval,
    B41Broker,
    B41Genesis,
    B41Order,
    B41Policy,
    BrokerRejected,
)


def policy(**overrides: object) -> B41Policy:
    values: dict[str, object] = {
        "max_inventory_btc": Decimal("10"),
        "max_loss_usdt": Decimal("500"),
        "max_drawdown_usdt": Decimal("500"),
        "loss_window_ms": 86_400_000,
    }
    values.update(overrides)
    return B41Policy(**values)


def shared_genesis(policy_value: B41Policy | None = None) -> B41Genesis:
    return B41Genesis.create_shared(
        "shared-paper",
        "synthetic-fixture-v1",
        ("strategy-a", "strategy-b"),
        policy_value or policy(),
    )


def order(genesis: B41Genesis, strategy_id: str, order_id: str, *, side: str = BUY, quantity: str = "0.1", order_type: str = MARKET, limit_price: str = "100", time_ms: int = 900, key: str | None = None) -> B41Order:
    return B41Order(
        genesis.portfolio_id,
        order_id,
        f"cmd-{order_id}",
        key or f"key-{order_id}",
        side,
        order_type,
        Decimal(quantity),
        Decimal(limit_price) if order_type == LIMIT else None,
        time_ms,
        strategy_id=strategy_id,
    )


def approval(value: B41Order, approval_id: str | None = None) -> B41Approval:
    return B41Approval.for_command(
        approval_id or f"approval-{value.order_id}",
        "owner",
        value.command_fingerprint,
        800,
        10_000,
    )


def event(event_id: str = "event-1") -> SyntheticMarketEvent:
    return SyntheticMarketEvent(event_id, "BTCUSDT", 1_000, 100, 101, 100.5, 10, "synthetic-source-v1")


def test_shared_membership_is_isolated_and_stable(tmp_path: Path) -> None:
    genesis = shared_genesis()
    broker = B41Broker(tmp_path, genesis, policy())
    accepted = order(genesis, "strategy-a", "order-a")
    assert broker.submit_order(accepted, approval(accepted))["state"] == "open"

    outsider = order(genesis, "strategy-outsider", "order-outsider")
    result = broker.submit_order(outsider, approval(outsider))
    assert result["reason_code"] == "membership.not_member"
    assert B41Genesis(**genesis.to_dict()).to_dict() == genesis.to_dict()


def test_member_inspection_pages_are_bounded_and_exclusive(tmp_path: Path) -> None:
    member_ids = [f"strategy-{index:03d}" for index in range(27)]
    genesis = B41Genesis.create_shared("shared-pages", "synthetic-fixture-v1", member_ids, policy())
    broker = B41Broker(tmp_path, genesis, policy())

    first = broker.inspect_members_page(limit=25)
    assert first["strategy_ids"] == member_ids[:25]
    assert first["page"] == {
        "limit": 25,
        "after_strategy_id": None,
        "has_more": True,
        "next_after_strategy_id": member_ids[24],
        "total_count": 27,
    }

    last = broker.inspect_members_page(limit=25, after_strategy_id=first["page"]["next_after_strategy_id"])
    assert last["strategy_ids"] == [member_ids[25], member_ids[26]]
    assert last["page"]["has_more"] is False
    assert last["page"]["next_after_strategy_id"] is None
    assert last["page"]["total_count"] == 27

    with pytest.raises(ValueError, match="member page cursor"):
        broker.inspect_members_page(limit=25, after_strategy_id="missing-strategy")


def test_shared_strategy_membership_and_ordering_are_portfolio_wide(tmp_path: Path) -> None:
    genesis = shared_genesis()
    broker = B41Broker(tmp_path, genesis, policy())
    first = order(genesis, "strategy-b", "order-b")
    second = order(genesis, "strategy-a", "order-a")
    broker.submit_order(first, approval(first))
    broker.submit_order(second, approval(second))

    result = broker.process_market_event(event())
    assert [fill["order_id"] for fill in result["fills"]] == ["order-b", "order-a"]
    assert [row["strategy_id"] for row in broker.inspect("orders")["orders"]] == ["strategy-b", "strategy-a"]


def test_shared_cash_reservation_is_attributed_and_released(tmp_path: Path) -> None:
    genesis = shared_genesis(policy(initial_cash_usdt=Decimal("100")))
    broker = B41Broker(tmp_path, genesis, policy(initial_cash_usdt=Decimal("100")))
    first = order(genesis, "strategy-a", "order-a", quantity="0.8", order_type=LIMIT)
    second = order(genesis, "strategy-b", "order-b", quantity="0.8", order_type=LIMIT)
    broker.submit_order(first, approval(first))
    rejected = broker.submit_order(second, approval(second))
    assert rejected["reason_code"] == "risk.cash_reserve"
    reservations = broker.inspect("reservations")
    assert reservations["cash_usdt"] > Decimal("80")
    assert reservations["reservations"][0]["strategy_id"] == "strategy-a"
    cancel_fp = hashlib.sha256(("{\"command_id\":\"cancel-a\",\"idempotency_key\":\"cancel-a-key\",\"order_id\":\"order-a\",\"portfolio_id\":\"" + genesis.portfolio_id + "\",\"strategy_id\":\"strategy-a\",\"submitted_at_ms\":950}").encode()).hexdigest()
    cancel_approval = B41Approval.for_command("approval-cancel-a", "owner", cancel_fp, 900, 10_000)
    broker.cancel_order(genesis.portfolio_id, first.order_id, "cancel-a", "cancel-a-key", 950, cancel_approval, strategy_id="strategy-a")
    assert broker.inspect("reservations")["cash_usdt"] == Decimal("0")


def test_shared_inventory_reservation_is_attributed(tmp_path: Path) -> None:
    broker_policy = policy(initial_btc_quantity=Decimal("1"), initial_average_entry_price=Decimal("100"))
    genesis = shared_genesis(broker_policy)
    broker = B41Broker(tmp_path, genesis, broker_policy)
    first = order(genesis, "strategy-a", "sell-a", side=SELL, quantity="0.6")
    second = order(genesis, "strategy-b", "sell-b", side=SELL, quantity="0.5")
    broker.submit_order(first, approval(first))
    rejected = broker.submit_order(second, approval(second))
    assert rejected["reason_code"] == "risk.inventory_limit"
    assert broker.inspect("reservations")["btc_quantity"] == Decimal("0.6")


def test_shared_stale_writer_retry_and_idempotency_are_fail_closed(tmp_path: Path) -> None:
    genesis = shared_genesis()
    first = B41Broker(tmp_path, genesis, policy())
    stale = B41Broker(tmp_path, genesis, policy())
    first_order = order(genesis, "strategy-a", "order-a")
    stale_order = order(genesis, "strategy-b", "order-b")
    first.submit_order(first_order, approval(first_order))
    with pytest.raises(BrokerRejected, match="stale portfolio snapshot"):
        stale.submit_order(stale_order, approval(stale_order))

    reloaded = B41Broker.open(tmp_path, genesis.portfolio_id)
    assert reloaded.submit_order(stale_order, approval(stale_order))["state"] == "open"
    assert reloaded.submit_order(stale_order, approval(stale_order))["state"] == "open"
    conflict = B41Order(genesis.portfolio_id, "order-conflict", "cmd-conflict", stale_order.idempotency_key, BUY, LIMIT, Decimal("0.2"), Decimal("100"), 901, strategy_id="strategy-b")
    with pytest.raises(BrokerRejected, match="idempotency"):
        reloaded.submit_order(conflict, approval(conflict, "approval-conflict"))


def test_shared_recovery_preserves_reservations_and_audit_inspection(tmp_path: Path) -> None:
    genesis = shared_genesis()
    broker = B41Broker(tmp_path, genesis, policy())
    first = order(genesis, "strategy-a", "order-a")
    broker.submit_order(first, approval(first))
    broker.process_market_event(event())
    before = {resource: broker.inspect(resource) for resource in ("reservations", "ledger", "risk", "orders", "fingerprints", "replay")}

    recovered = B41Broker.open(tmp_path, genesis.portfolio_id)
    after = {resource: recovered.inspect(resource) for resource in before}
    assert after == before


def test_missing_portfolio_inspection_does_not_create_files(tmp_path: Path) -> None:
    with pytest.raises(BrokerRejected, match="missing portfolio policy"):
        B41Broker.open(tmp_path, "portfolio-missing")
    with pytest.raises(BrokerRejected, match="missing portfolio genesis"):
        B41Broker.recover(tmp_path, "portfolio-missing", policy())
    assert not list(tmp_path.iterdir())
