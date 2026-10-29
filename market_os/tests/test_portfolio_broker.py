from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import hashlib
import json
import os
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from market_os.portfolio_broker import (
    B41Approval,
    B41Broker,
    B41Genesis,
    B41Order,
    B41Policy,
    BrokerRejected,
    BrokerStale,
)
from market_os.paper_venue import BUY, LIMIT, MARKET, SELL, SyntheticMarketEvent
from market_os.api import make_handler
from market_os.store import RunStore
from market_os.workflow import MarketWorkflow


def policy(**overrides: object) -> B41Policy:
    values = {
        "max_inventory_btc": Decimal("10"),
        "max_loss_usdt": Decimal("500"),
        "max_drawdown_usdt": Decimal("500"),
        "loss_window_ms": 86_400_000,
    }
    values.update(overrides)
    return B41Policy(**values)


def genesis() -> B41Genesis:
    return B41Genesis.create("strategy-demo", "synthetic-fixture-v1", policy())


def approval(order: B41Order, *, approver: str = "owner", expires_at_ms: int = 10_000) -> B41Approval:
    return B41Approval.for_command("approval-" + order.order_id, approver, order.command_fingerprint, 900, expires_at_ms)


def event(event_id: str, time_ms: int = 1_000, bid: float = 100, ask: float = 101, last: float = 100.5) -> SyntheticMarketEvent:
    return SyntheticMarketEvent(event_id, "BTCUSDT", time_ms, bid, ask, last, 10, "synthetic-source-v1")


def buy(order_id: str = "order-1", *, time_ms: int = 900, quantity: str = "0.1", order_type: str = MARKET, limit_price: str | None = None) -> B41Order:
    return B41Order(genesis().portfolio_id, order_id, "cmd-" + order_id, "key-" + order_id, BUY, order_type, Decimal(quantity), Decimal(limit_price) if limit_price else None, time_ms)


def test_policy_uses_approved_defaults_and_requires_unresolved_limits() -> None:
    current = B41Policy(max_inventory_btc=Decimal("10"), max_loss_usdt=Decimal("500"), max_drawdown_usdt=Decimal("500"), loss_window_ms=86_400_000)
    assert current.fee_bps_per_side == Decimal("10")
    assert current.spread_bps_per_side == Decimal("1")
    assert current.slippage_bps_per_side == Decimal("0.5")
    assert current.price_quantum == Decimal("0.01")
    assert current.quantity_step == Decimal("0.000001")
    assert current.minimum_notional_usdt == Decimal("10")
    with pytest.raises(ValueError, match="max_inventory_btc"):
        B41Policy()
    versioned = policy(policy_version="b4.1-test-policy-v2")
    assert B41Policy.from_dict(versioned.to_dict()).fingerprint == versioned.fingerprint


def test_persisted_broker_matches_and_recovers_deterministically(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy()
    broker.submit_order(order, approval(order))
    snapshot = broker.process_market_event(event("event-1"))
    assert snapshot["cash_usdt"] == Decimal("9989.89")
    assert snapshot["btc_quantity"] == Decimal("0.1")
    assert len(snapshot["fills"]) == 1
    recovered = B41Broker.recover(tmp_path, genesis().portfolio_id, policy())
    assert recovered.snapshot() == snapshot
    assert recovered.snapshot_fingerprint == broker.snapshot_fingerprint
    reopened = B41Broker(tmp_path, genesis(), policy())
    assert reopened.snapshot() == snapshot
    replay = B41Broker.recover(tmp_path, genesis().portfolio_id, policy())
    assert replay.snapshot_fingerprint == recovered.snapshot_fingerprint


def test_market_event_id_is_unique_and_retry_does_not_mutate(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    first = event("event-1", time_ms=1_000)
    broker.process_market_event(first)
    before_snapshot = broker.snapshot()
    before_ledger = broker.ledger_path.read_bytes()

    with pytest.raises(BrokerRejected, match="duplicate market event"):
        broker.process_market_event(event("event-1", time_ms=2_000, bid=101, ask=102, last=101.5))

    assert broker.snapshot() == before_snapshot
    assert broker.ledger_path.read_bytes() == before_ledger


def test_limit_matching_uses_adversely_slipped_price_for_buy_and_sell(tmp_path: Path) -> None:
    buy_broker = B41Broker(tmp_path / "buy", genesis(), policy())
    buy_order = buy(order_type=LIMIT, limit_price="101", quantity="0.1")
    buy_broker.submit_order(buy_order, approval(buy_order))
    buy_snapshot = buy_broker.process_market_event(event("buy-limit-event", bid=100, ask=101, last=100.5))
    assert not buy_snapshot["fills"]
    assert buy_snapshot["orders"][0]["state"] == "open"

    seeded_policy = policy(initial_btc_quantity=Decimal("0.1"), initial_average_entry_price=Decimal("100"))
    seeded_genesis = B41Genesis.create("strategy-demo", "synthetic-fixture-v1", seeded_policy)
    sell_broker = B41Broker(tmp_path / "sell", seeded_genesis, seeded_policy)
    sell_order = B41Order(seeded_genesis.portfolio_id, "sell-limit", "cmd-sell-limit", "key-sell-limit", SELL, LIMIT, Decimal("0.1"), Decimal("100.01"), 900)
    sell_approval = B41Approval.for_command("approval-sell-limit", "owner", sell_order.command_fingerprint, 900, 10_000)
    sell_broker.submit_order(sell_order, sell_approval)
    sell_snapshot = sell_broker.process_market_event(event("sell-limit-event", bid=100, ask=101, last=100.5))
    assert not sell_snapshot["fills"]
    assert sell_snapshot["orders"][0]["state"] == "open"


def test_idempotent_retry_and_conflict_are_recorded_once(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    first = buy()
    result = broker.submit_order(first, approval(first))
    retry = broker.submit_order(first, approval(first))
    assert retry == result
    changed = B41Order(first.portfolio_id, "order-2", first.command_id, first.idempotency_key, BUY, MARKET, Decimal("0.2"), None, first.submitted_at_ms)
    with pytest.raises(BrokerRejected, match="idempotency"):
        broker.submit_order(changed, approval(changed))
    assert len(broker.open_orders) == 1


def test_cancel_is_approval_bound_and_idempotent(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy(order_type=LIMIT, limit_price="100", quantity="0.1")
    broker.submit_order(order, approval(order))
    cancel_fingerprint = hashlib.sha256(("{\"command_id\":\"cancel-1\",\"idempotency_key\":\"cancel-key\",\"order_id\":\"" + order.order_id + "\",\"portfolio_id\":\"" + genesis().portfolio_id + "\",\"submitted_at_ms\":950}").encode()).hexdigest()
    cancel_approval = B41Approval.for_command("cancel-approval", "owner", cancel_fingerprint, 900, 10_000)
    result = broker.cancel_order(genesis().portfolio_id, order.order_id, "cancel-1", "cancel-key", 950, cancel_approval)
    assert result["state"] == "cancelled"
    assert not broker.open_orders
    assert broker.cancel_order(genesis().portfolio_id, order.order_id, "cancel-1", "cancel-key", 950, cancel_approval) == result


def test_idempotency_key_is_scoped_by_command_type(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy(order_type=LIMIT, limit_price="100", quantity="0.1")
    shared_key = "shared-command-key"
    order = B41Order(order.portfolio_id, order.order_id, order.command_id, shared_key, order.side, order.order_type, order.quantity, order.limit_price, order.submitted_at_ms)
    broker.submit_order(order, approval(order))
    cancel_fingerprint = hashlib.sha256(("{\"command_id\":\"cancel-shared\",\"idempotency_key\":\"" + shared_key + "\",\"order_id\":\"" + order.order_id + "\",\"portfolio_id\":\"" + genesis().portfolio_id + "\",\"submitted_at_ms\":950}").encode()).hexdigest()
    cancel_approval = B41Approval.for_command("cancel-approval-shared", "owner", cancel_fingerprint, 900, 10_000)

    result = broker.cancel_order(genesis().portfolio_id, order.order_id, "cancel-shared", shared_key, 950, cancel_approval)

    assert result["state"] == "cancelled"
    assert broker.inspect("ledger")["events"][0]["kind"] == "order.accepted"
    assert broker.inspect("ledger")["events"][1]["kind"] == "order.cancelled"


def test_recovery_rejects_duplicate_command_identity(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy()
    broker.submit_order(order, approval(order))
    lines = broker.ledger_path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    duplicate = dict(first)
    duplicate["sequence"] = 2
    duplicate["previous_event_fingerprint"] = first["event_fingerprint"]
    duplicate["event_fingerprint"] = hashlib.sha256(
        json.dumps({key: value for key, value in duplicate.items() if key != "event_fingerprint"}, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    broker.ledger_path.write_text("\n".join((lines[0], json.dumps(duplicate))) + "\n", encoding="utf-8")

    with pytest.raises(BrokerRejected, match="duplicate command idempotency"):
        B41Broker.open(tmp_path, genesis().portfolio_id)


def test_risk_limits_fail_closed_and_no_negative_balances(tmp_path: Path) -> None:
    tight_policy = policy(max_inventory_btc=Decimal("0.05"))
    tight_genesis = B41Genesis.create("strategy-demo", "synthetic-fixture-v1", tight_policy)
    broker = B41Broker(tmp_path, tight_genesis, tight_policy)
    order = buy(quantity="0.1")
    result = broker.submit_order(order, approval(order))
    assert result["state"] == "rejected"
    assert result["reason_code"] == "risk.inventory_limit"
    assert broker.submit_order(order, approval(order)) == result
    assert broker.inspect("risk")["records"][-1]["kind"] == "order.rejected"
    assert broker.snapshot()["cash_usdt"] == Decimal("10000")
    assert not broker.snapshot()["fills"]


def test_order_and_risk_inspection_pages_are_bounded_and_exclusive(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    for index in range(27):
        order = buy(order_id=f"page-order-{index:03d}", order_type=LIMIT, limit_price="100")
        assert broker.submit_order(order, approval(order))["state"] == "open"
    for index in range(3):
        rejected = buy(order_id=f"page-rejected-{index}", quantity="11")
        assert broker.submit_order(rejected, approval(rejected))["state"] == "rejected"

    latest_orders = broker.inspect_orders_page(limit=25)
    assert len(latest_orders["orders"]) == 25
    assert latest_orders["page"]["has_more"] is True
    older_orders = broker.inspect_orders_page(limit=25, before_order_id=latest_orders["page"]["next_before_order_id"])
    assert [order["order_id"] for order in older_orders["orders"]] == ["page-order-001", "page-order-000"]
    assert older_orders["page"]["has_more"] is False

    latest_risk = broker.inspect_risk_page(limit=2)
    assert len(latest_risk["records"]) == 2
    assert latest_risk["page"]["has_more"] is True
    older_risk = broker.inspect_risk_page(limit=2, before_sequence=int(latest_risk["page"]["next_before_sequence"]))
    assert len(older_risk["records"]) == 1
    assert older_risk["page"]["has_more"] is False
    assert int(older_risk["records"][0]["sequence"]) < int(latest_risk["records"][-1]["sequence"])
    with pytest.raises(ValueError, match="risk page cursor"):
        broker.inspect_risk_page(limit=2, before_sequence=10_000)
    with pytest.raises(ValueError, match="order page cursor"):
        broker.inspect_orders_page(limit=25, before_order_id="missing-order")


def test_ledger_page_uses_its_scan_for_freshness_and_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy(order_id="ledger-single-scan", order_type=LIMIT, limit_price="100")
    broker.submit_order(order, approval(order))
    monkeypatch.setattr(broker, "_ledger_head", lambda: pytest.fail("ledger page performed a second full-file head scan"))

    page = broker.inspect_event_page("ledger", limit=1)

    assert len(page["events"]) == 1
    assert page["page"]["total_count"] == 1


def test_risk_page_uses_its_scan_for_freshness_and_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy(order_id="risk-single-scan", quantity="11")
    broker.submit_order(order, approval(order))
    monkeypatch.setattr(broker, "_ledger_head", lambda: pytest.fail("risk page performed a second full-file head scan"))

    page = broker.inspect_risk_page(limit=1)

    assert len(page["records"]) == 1
    assert page["page"]["has_more"] is False


def test_event_page_rejects_a_changed_ledger_from_its_scan_tail(tmp_path: Path) -> None:
    writer = B41Broker(tmp_path, genesis(), policy())
    first = buy(order_id="ledger-stale-first", order_type=LIMIT, limit_price="100")
    writer.submit_order(first, approval(first))
    stale = B41Broker.open(tmp_path, genesis().portfolio_id)
    changed = buy(order_id="ledger-stale-risk", quantity="11")
    assert writer.submit_order(changed, approval(changed))["state"] == "rejected"

    with pytest.raises(BrokerStale, match="stale portfolio snapshot"):
        stale.inspect_event_page("ledger", limit=25)
    with pytest.raises(BrokerStale, match="stale portfolio snapshot"):
        stale.inspect_risk_page(limit=25)


def test_summary_freshness_check_streams_without_materializing_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy(order_id="summary-tail-only", order_type=LIMIT, limit_price="100")
    broker.submit_order(order, approval(order))
    original_read_text = Path.read_text

    def reject_full_ledger_read(path: Path, *args: object, **kwargs: object) -> str:
        if path == broker.ledger_path:
            pytest.fail("freshness check materialized the complete ledger")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", reject_full_ledger_read)

    assert broker.inspect_summary_compact()["open_orders"] == 1


def test_summary_freshness_check_handles_crlf_and_trailing_blank_lines(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy(order_id="summary-tail-lines", order_type=LIMIT, limit_price="100")
    broker.submit_order(order, approval(order))
    lines = broker.ledger_path.read_bytes().splitlines()
    broker.ledger_path.write_bytes(b"\r\n".join([b" " * 9000 + lines[0]]) + b"\r\n  \r\n" + b" " * (1024 * 1024))

    assert broker.inspect_summary_compact()["open_orders"] == 1


def test_ledger_head_preserves_long_trailing_same_line_whitespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy(order_id="summary-same-line-whitespace", order_type=LIMIT, limit_price="100")
    broker.submit_order(order, approval(order))
    last_record = broker.ledger_path.read_bytes().splitlines()[-1]
    broker.ledger_path.write_bytes(last_record + b" " * (1024 * 1024))
    expected = json.loads(last_record)["event_fingerprint"]
    original_loads = json.loads
    parsed_lengths: list[int] = []

    def capture_json_input(value: str | bytes | bytearray, *args: object, **kwargs: object) -> object:
        parsed_lengths.append(len(value))
        return original_loads(value, *args, **kwargs)

    monkeypatch.setattr("market_os.portfolio_broker.json.loads", capture_json_input)

    assert broker._ledger_head() == expected
    assert parsed_lengths == [len(last_record) + 1024 * 1024]


def test_ledger_head_rejects_raw_tab_at_chunk_boundary(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy(order_id="summary-chunk-boundary", order_type=LIMIT, limit_price="100")
    broker.submit_order(order, approval(order))
    last_record = broker.ledger_path.read_bytes().splitlines()[-1]
    value_start = last_record.index(b'"idempotency_key":"') + len(b'"idempotency_key":"')
    tab_position = 64 * 1024 - 1
    padding = b" " * (tab_position - value_start)
    broker.ledger_path.write_bytes(last_record[:value_start] + padding + b"\t" + last_record[value_start:])

    with pytest.raises(json.JSONDecodeError):
        broker._ledger_head()


def test_ledger_head_skips_long_unicode_whitespace_only_line(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy(order_id="summary-unicode-blank-line", order_type=LIMIT, limit_price="100")
    broker.submit_order(order, approval(order))
    last_record = broker.ledger_path.read_bytes().splitlines()[-1]
    expected = json.loads(last_record)["event_fingerprint"]
    broker.ledger_path.write_bytes(last_record + b"\n" + ("\u00a0" * (1024 * 1024)).encode("utf-8"))

    assert broker._ledger_head() == expected


def test_ledger_head_rejects_non_json_whitespace_prefix(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy(order_id="summary-invalid-prefix", order_type=LIMIT, limit_price="100")
    broker.submit_order(order, approval(order))
    last_record = broker.ledger_path.read_bytes().splitlines()[-1]
    broker.ledger_path.write_bytes("\u00a0".encode("utf-8") + last_record)

    with pytest.raises(json.JSONDecodeError):
        broker._ledger_head()


def test_summary_freshness_check_rejects_interior_utf8_corruption(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    for index in range(2):
        order = buy(order_id=f"summary-interior-utf8-{index}", order_type=LIMIT, limit_price="100")
        broker.submit_order(order, approval(order))
    lines = broker.ledger_path.read_bytes().splitlines()
    corrupted = bytearray(lines[0])
    marker = corrupted.find(b'"kind"')
    assert marker >= 0
    corrupted[marker + 1] = 0xFF
    broker.ledger_path.write_bytes(b"\n".join([bytes(corrupted), *lines[1:]]) + b"\n")

    with pytest.raises(UnicodeDecodeError):
        broker.inspect_summary_compact()


def test_broker_open_rejects_drive_qualified_store_paths(tmp_path: Path) -> None:
    if os.name != "nt":
        pytest.skip("drive-qualified path escape syntax is specific to Windows")
    store_root = (tmp_path / "store").resolve()
    store_root.mkdir()
    current_drive = store_root.drive[:1].upper()
    alternate_drive = "D" if current_drive != "D" else "C"
    portfolio_id = f"{alternate_drive}:outside"
    drive_qualified = store_root / portfolio_id
    assert drive_qualified.parent != store_root

    with pytest.raises(BrokerRejected, match="inside its store"):
        B41Broker.open(store_root, portfolio_id)


def test_broker_open_rejects_symlinked_portfolio_directory(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    portfolio = genesis()
    B41Broker(source_root, portfolio, policy())
    store_root = tmp_path / "store"
    store_root.mkdir()
    link = store_root / portfolio.portfolio_id
    try:
        link.symlink_to(source_root / portfolio.portfolio_id, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are not available: {exc}")

    with pytest.raises(BrokerRejected, match="inside its store"):
        B41Broker.open(store_root, portfolio.portfolio_id)


def test_broker_open_rejects_symlinked_portfolio_policy(tmp_path: Path) -> None:
    store_root = tmp_path / "store"
    portfolio = genesis()
    broker = B41Broker(store_root, portfolio, policy())
    policy_path = broker.policy_path
    external_policy = tmp_path / "external-policy.json"
    external_policy.write_bytes(policy_path.read_bytes())
    policy_path.unlink()
    try:
        policy_path.symlink_to(external_policy)
    except OSError as exc:
        pytest.skip(f"file symlinks are not available: {exc}")

    with pytest.raises(BrokerRejected, match="policy must be a local file"):
        B41Broker.open(store_root, portfolio.portfolio_id)


def test_broker_open_rejects_symlinked_writer_lock(tmp_path: Path) -> None:
    portfolio = genesis()
    broker = B41Broker(tmp_path / "store", portfolio, policy())
    lock_path = broker.lock_path
    lock_path.unlink()
    external_lock = tmp_path / "outside.lock"
    external_lock.write_bytes(b"external lock remains unchanged")
    try:
        lock_path.symlink_to(external_lock)
    except OSError as exc:
        pytest.skip(f"file symlinks are not available: {exc}")

    with pytest.raises(BrokerRejected, match="lock file must be local"):
        B41Broker.open(tmp_path / "store", portfolio.portfolio_id)
    assert external_lock.read_bytes() == b"external lock remains unchanged"


def test_broker_open_rejects_dangling_symlinked_writer_lock(tmp_path: Path) -> None:
    portfolio = genesis()
    broker = B41Broker(tmp_path / "store", portfolio, policy())
    lock_path = broker.lock_path
    lock_path.unlink()
    external_lock = tmp_path / "missing" / "outside.lock"
    try:
        lock_path.symlink_to(external_lock)
    except OSError as exc:
        pytest.skip(f"file symlinks are not available: {exc}")

    with pytest.raises(BrokerRejected, match="lock file must be local"):
        B41Broker.open(tmp_path / "store", portfolio.portfolio_id)
    assert not external_lock.exists()


def test_reservation_inspection_pages_are_bounded_and_keep_portfolio_totals(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    for index in range(27):
        order = buy(order_id=f"reservation-{index:03d}", order_type=LIMIT, limit_price="100")
        assert broker.submit_order(order, approval(order))["state"] == "open"

    latest = broker.inspect_reservations_page(limit=25)
    assert [row["order_id"] for row in latest["reservations"]] == [
        f"reservation-{index:03d}" for index in range(26, 1, -1)
    ]
    assert latest["page"] == {
        "limit": 25,
        "before_order_id": None,
        "has_more": True,
        "next_before_order_id": "reservation-002",
        "total_count": 27,
    }
    assert Decimal(latest["cash_usdt"]) == Decimal("270.270")
    assert latest["buy_quantity"] == "2.7"

    older = broker.inspect_reservations_page(limit=25, before_order_id="reservation-002")
    assert [row["order_id"] for row in older["reservations"]] == ["reservation-001", "reservation-000"]
    assert older["page"]["has_more"] is False
    assert Decimal(older["cash_usdt"]) == Decimal("270.270")
    with pytest.raises(ValueError, match="reservation page cursor"):
        broker.inspect_reservations_page(limit=25, before_order_id="missing-order")


def test_market_fill_risk_rejection_is_terminal_and_event_progresses(tmp_path: Path) -> None:
    roomy_policy = policy(max_inventory_btc=Decimal("100"))
    roomy_genesis = B41Genesis.create("strategy-demo", "synthetic-fixture-v1", roomy_policy)
    broker = B41Broker(tmp_path, roomy_genesis, roomy_policy)
    oversized = B41Order(roomy_genesis.portfolio_id, "oversized-market", "cmd-oversized-market", "key-oversized-market", BUY, MARKET, Decimal("20"), None, 900)
    broker.submit_order(oversized, approval(oversized))

    snapshot = broker.process_market_event(event("event-over-cap"))

    assert snapshot["event_cursor"] == ["event-over-cap"]
    assert not snapshot["fills"]
    assert snapshot["orders"][0]["state"] == "risk_rejected"
    risk = broker.inspect("risk")["records"][-1]
    assert risk["kind"] == "market.processed"
    assert risk["result"]["risk_rejections"][0]["reason_code"] == "risk.max_order_notional"

    next_snapshot = broker.process_market_event(event("event-after-rejection", time_ms=2_000))
    assert next_snapshot["event_cursor"] == ["event-over-cap", "event-after-rejection"]
    recovered = B41Broker.open(tmp_path, roomy_genesis.portfolio_id)
    assert recovered.snapshot() == next_snapshot
    assert recovered.inspect("risk")["records"] == broker.inspect("risk")["records"]


def test_read_only_inspection_and_policy_recovery(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy()
    broker.submit_order(order, approval(order))
    assert broker.inspect("summary")["portfolio_id"] == genesis().portfolio_id
    assert broker.inspect("orders")["orders"][0]["state"] == "open"
    opened = B41Broker.open(tmp_path, genesis().portfolio_id)
    assert opened.inspect("policy")["fingerprint"] == policy().fingerprint
    with pytest.raises(KeyError):
        broker.inspect("mutate")


def test_recovery_rejects_checkpoint_snapshot_spoof(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy()
    broker.submit_order(order, approval(order))
    checkpoint_path = broker.checkpoint_path
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["snapshot"]["cash_usdt"] = "1"
    checkpoint["snapshot_fingerprint"] = hashlib.sha256(
        json.dumps(checkpoint["snapshot"], sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
    with pytest.raises(BrokerRejected, match="checkpoint"):
        B41Broker.open(tmp_path, genesis().portfolio_id)


def test_recovery_rejects_checkpoint_metadata_mismatch(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy()
    broker.submit_order(order, approval(order))
    checkpoint_path = broker.checkpoint_path
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["sequence"] = checkpoint["sequence"] + 1
    checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
    with pytest.raises(BrokerRejected, match="checkpoint sequence mismatch"):
        B41Broker.open(tmp_path, genesis().portfolio_id)


def test_recovery_rejects_ledger_result_snapshot_fingerprint_mismatch(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy()
    broker.submit_order(order, approval(order))
    ledger_path = broker.ledger_path
    record = json.loads(ledger_path.read_text(encoding="utf-8").splitlines()[0])
    record["resulting_snapshot_fingerprint"] = "0" * 64
    record["event_fingerprint"] = hashlib.sha256(
        json.dumps({key: value for key, value in record.items() if key != "event_fingerprint"}, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    ledger_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(BrokerRejected, match="resulting snapshot fingerprint"):
        B41Broker.open(tmp_path, genesis().portfolio_id)


@pytest.mark.parametrize("tail", [b'{"schema":"market-os.b4-1.paper-portfolio-event@v1"', b"\xff\n", b"[]\n"])
def test_recovery_rejects_malformed_ledger_record(tmp_path: Path, tail: bytes) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy()
    broker.submit_order(order, approval(order))
    with broker.ledger_path.open("ab") as handle:
        handle.write(tail)

    with pytest.raises(BrokerRejected, match="ledger record is malformed"):
        B41Broker.open(tmp_path, genesis().portfolio_id)


@pytest.mark.parametrize(
    ("resource", "payload", "message"),
    [
        ("genesis", b"{", "genesis is malformed"),
        ("policy", b"[]\n", "policy is malformed"),
    ],
)
def test_recovery_rejects_malformed_portfolio_metadata(tmp_path: Path, resource: str, payload: bytes, message: str) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    path = getattr(broker, f"{resource}_path")
    path.write_bytes(payload)

    with pytest.raises(BrokerRejected, match=message):
        B41Broker.open(tmp_path, genesis().portfolio_id)


def test_recovery_rejects_malformed_checkpoint_metadata(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy()
    broker.submit_order(order, approval(order))
    broker.checkpoint_path.write_bytes(b"\xff\n")

    with pytest.raises(BrokerRejected, match="checkpoint is malformed"):
        B41Broker.open(tmp_path, genesis().portfolio_id)


@pytest.mark.parametrize("collection", ["orders", "fills"])
def test_recovery_rejects_malformed_snapshot_records(tmp_path: Path, collection: str) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy()
    broker.submit_order(order, approval(order))
    if collection == "fills":
        broker.process_market_event(event("fill-event"))

    records = [json.loads(line) for line in broker.ledger_path.read_text(encoding="utf-8").splitlines()]
    snapshot = records[-1]["resulting_snapshot"]
    snapshot[collection][0] = {"malformed": True}
    records[-1]["resulting_snapshot_fingerprint"] = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    records[-1]["event_fingerprint"] = hashlib.sha256(
        json.dumps({key: value for key, value in records[-1].items() if key != "event_fingerprint"}, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    broker.ledger_path.write_text("\n".join(json.dumps(record, sort_keys=True, separators=(",", ":")) for record in records) + "\n", encoding="utf-8")

    with pytest.raises(BrokerRejected, match="ledger resulting snapshot is malformed"):
        B41Broker.open(tmp_path, genesis().portfolio_id)


@pytest.mark.parametrize(
    ("field", "value"),
    [("last_event_time_ms", "not-an-int"), ("event_cursor", {"event": "event-1"}), ("equity_history", ["not-a-point"])],
)
def test_recovery_rejects_malformed_snapshot_scalars(tmp_path: Path, field: str, value: object) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy()
    broker.submit_order(order, approval(order))
    broker.process_market_event(event("scalar-event"))

    records = [json.loads(line) for line in broker.ledger_path.read_text(encoding="utf-8").splitlines()]
    snapshot = records[-1]["resulting_snapshot"]
    snapshot[field] = value
    records[-1]["resulting_snapshot_fingerprint"] = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    records[-1]["event_fingerprint"] = hashlib.sha256(
        json.dumps({key: item for key, item in records[-1].items() if key != "event_fingerprint"}, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    broker.ledger_path.write_text("\n".join(json.dumps(record, sort_keys=True, separators=(",", ":")) for record in records) + "\n", encoding="utf-8")

    with pytest.raises(BrokerRejected, match="ledger resulting snapshot is malformed"):
        B41Broker.open(tmp_path, genesis().portfolio_id)


def test_recovery_rejects_policy_identity_conflict(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    changed_policy = policy(fee_bps_per_side=Decimal("11"))
    broker.policy_path.write_text(json.dumps(changed_policy.to_dict(), default=str), encoding="utf-8")
    with pytest.raises(BrokerRejected, match="policy identity conflict"):
        B41Broker.recover(tmp_path, genesis().portfolio_id, policy())


def test_recovery_rejects_ledger_portfolio_identity_mismatch(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy()
    broker.submit_order(order, approval(order))
    ledger_path = broker.ledger_path
    record = json.loads(ledger_path.read_text(encoding="utf-8").splitlines()[0])
    record["portfolio_id"] = "portfolio-other"
    record["event_fingerprint"] = hashlib.sha256(
        json.dumps({key: value for key, value in record.items() if key != "event_fingerprint"}, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    ledger_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    with pytest.raises(BrokerRejected, match="portfolio identity mismatch"):
        B41Broker.open(tmp_path, genesis().portfolio_id)


def test_approval_is_single_use_and_revocable(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    first = buy()
    broker.submit_order(first, approval(first))
    second = buy(order_id="order-2")
    reused = B41Approval.for_command("approval-reused", "owner", first.command_fingerprint, 900, 10_000)
    rejected_reuse = broker.submit_order(second, reused)
    assert rejected_reuse["state"] == "rejected"
    assert rejected_reuse["reason_code"] == "approval.command_mismatch"
    third = buy(order_id="order-3")
    third_approval = B41Approval.for_command("approval-order-3", "owner", third.command_fingerprint, 900, 10_000)
    broker.revoke_approval("approval-order-3", "revoke-1", "revoke-key", 950)
    rejected_revocation = broker.submit_order(third, third_approval)
    assert rejected_revocation["state"] == "rejected"
    assert rejected_revocation["reason_code"] == "approval.reused_or_revoked"
    assert broker.inspect("approvals")["records"]


def test_cli_and_http_expose_read_only_b4_resources(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    broker = B41Broker(tmp_path / "b4-paper", genesis(), policy())
    order = buy()
    broker.submit_order(order, approval(order))
    from market_os.cli import main

    assert main(["b4-paper", "inspect", genesis().portfolio_id, "--store-root", str(tmp_path / "b4-paper"), "--resource", "orders"]) == 0
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["orders"][0]["order_id"] == order.order_id
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(tmp_path / "workflow"))))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/v1/b4/portfolios/{genesis().portfolio_id}/orders?id={order.order_id}"
        # The API's fixed inspection root is the workflow's b4-paper root.
        target = tmp_path / "workflow" / "b4-paper"
        target.mkdir(parents=True)
        (target / genesis().portfolio_id).mkdir()
        for source in (tmp_path / "b4-paper" / genesis().portfolio_id).iterdir():
            (target / genesis().portfolio_id / source.name).write_bytes(source.read_bytes())
        payload = json.loads(urlopen(url, timeout=2).read())
        assert payload["orders"][0]["order_id"] == order.order_id
        with pytest.raises(HTTPError) as exc:
            urlopen(f"http://127.0.0.1:{server.server_port}/v1/b4/portfolios/{genesis().portfolio_id}/submit", timeout=2)
        assert exc.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_u5_operator_dashboard_is_read_only_and_escaped(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path / "b4-paper", genesis(), policy())
    unsafe = buy(order_id="order-<unsafe>&")
    broker.submit_order(unsafe, approval(unsafe))
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(tmp_path / "workflow"))))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        target = tmp_path / "workflow" / "b4-paper"
        target.mkdir(parents=True)
        (target / genesis().portfolio_id).mkdir()
        for source in (tmp_path / "b4-paper" / genesis().portfolio_id).iterdir():
            (target / genesis().portfolio_id / source.name).write_bytes(source.read_bytes())
        response = urlopen(f"http://127.0.0.1:{server.server_port}/v1/b4/portfolios/{genesis().portfolio_id}/dashboard", timeout=2)
        body = response.read().decode("utf-8")
        assert response.headers["Content-Type"] == "text/html; charset=utf-8"
        assert "synthetic-only · paper-only · read-only" in body
        assert "order-&lt;unsafe&gt;&amp;" in body
        assert "<form" not in body.lower()
        with pytest.raises(HTTPError) as exc:
            urlopen(f"http://127.0.0.1:{server.server_port}/v1/b4/portfolios/{genesis().portfolio_id}/dashboard", data=b"{}", timeout=2)
        assert exc.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
