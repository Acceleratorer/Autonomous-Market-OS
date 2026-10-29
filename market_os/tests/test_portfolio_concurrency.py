from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from market_os.portfolio_broker import B41Broker, B41Genesis, B41Order, BrokerRejected
from market_os.paper_venue import BUY, MARKET
from market_os.tests.test_portfolio_broker import approval, buy, genesis, policy


def test_stale_writer_must_reload_before_mutation(tmp_path: Path) -> None:
    first = B41Broker(tmp_path, genesis(), policy())
    stale = B41Broker(tmp_path, genesis(), policy())

    first.submit_order(buy(), approval(buy()))
    with pytest.raises(BrokerRejected, match="stale portfolio snapshot; reload before writing"):
        stale.submit_order(buy(order_id="order-2"), approval(buy(order_id="order-2")))

    reloaded = B41Broker.open(tmp_path, genesis().portfolio_id)
    result = reloaded.submit_order(buy(order_id="order-2"), approval(buy(order_id="order-2")))

    assert result["state"] == "open"
    records = reloaded.inspect("ledger")["events"]
    assert [record["sequence"] for record in records] == [1, 2]


def test_isolated_portfolios_keep_independent_heads_and_locks(tmp_path: Path) -> None:
    first_genesis = genesis()
    second_policy = policy()
    second_genesis = B41Genesis.create("strategy-other", "synthetic-fixture-v1", second_policy)
    first = B41Broker(tmp_path, first_genesis, policy())
    second = B41Broker(tmp_path, second_genesis, second_policy)
    second_order = B41Order(second_genesis.portfolio_id, "other-order", "cmd-other-order", "key-other-order", BUY, MARKET, Decimal("0.1"), None, 900)

    first.submit_order(buy(), approval(buy()))
    second.submit_order(second_order, approval(second_order))

    assert first.inspect("ledger")["events"][0]["sequence"] == 1
    assert second.inspect("ledger")["events"][0]["sequence"] == 1
    assert (tmp_path / first_genesis.portfolio_id / ".writer.lock").is_file()
    assert (tmp_path / second_genesis.portfolio_id / ".writer.lock").is_file()


def test_reloaded_writer_preserves_committed_snapshot_before_new_write(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    broker.submit_order(buy(), approval(buy()))
    reopened = B41Broker.open(tmp_path, genesis().portfolio_id)

    assert reopened.snapshot() == broker.snapshot()
    assert reopened.snapshot_fingerprint == broker.snapshot_fingerprint
