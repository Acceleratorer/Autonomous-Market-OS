from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from market_os.portfolio_broker import B41Approval, B41Broker, B41Genesis, B41Order, BrokerRejected
from market_os.tests.test_portfolio_broker import approval, buy, genesis, policy


def test_cancel_rejection_is_typed_idempotent_and_recoverable(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy(order_type="limit", limit_price="100")
    broker.submit_order(order, approval(order))
    cancel_fingerprint = hashlib.sha256(
        ("{\"command_id\":\"cancel-missing\",\"idempotency_key\":\"cancel-missing-key\",\"order_id\":\"missing-order\",\"portfolio_id\":\"" + genesis().portfolio_id + "\",\"submitted_at_ms\":950}").encode()
    ).hexdigest()
    cancel_approval = B41Approval.for_command(
        "cancel-missing-approval", "owner", cancel_fingerprint, 900, 10_000
    )
    before_snapshot = broker.snapshot()

    result = broker.cancel_order(genesis().portfolio_id, "missing-order", "cancel-missing", "cancel-missing-key", 950, cancel_approval)

    assert result["state"] == "rejected"
    assert result["reason_code"] == "order.not_open"
    records = broker.inspect("risk")["records"]
    assert records[-1]["kind"] == "order.cancel.rejected"
    assert records[-1]["result"] == result
    ledger_bytes = broker.ledger_path.read_bytes()
    assert broker.cancel_order(genesis().portfolio_id, "missing-order", "cancel-missing", "cancel-missing-key", 950, cancel_approval) == result
    assert broker.ledger_path.read_bytes() == ledger_bytes
    assert broker.snapshot() == before_snapshot

    recovered = B41Broker.open(tmp_path, genesis().portfolio_id)
    assert recovered.snapshot() == broker.snapshot()
    assert recovered.inspect("risk")["records"] == broker.inspect("risk")["records"]


def test_cancel_idempotency_conflict_is_audited_and_recoverable(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy(order_type="limit", limit_price="100")
    broker.submit_order(order, approval(order))
    cancel_fingerprint = hashlib.sha256(
        ("{\"command_id\":\"cancel-one\",\"idempotency_key\":\"cancel-shared\",\"order_id\":\"" + order.order_id + "\",\"portfolio_id\":\"" + genesis().portfolio_id + "\",\"submitted_at_ms\":950}").encode()
    ).hexdigest()
    cancel_approval = B41Approval.for_command("cancel-one-approval", "owner", cancel_fingerprint, 900, 10_000)
    broker.cancel_order(genesis().portfolio_id, order.order_id, "cancel-one", "cancel-shared", 950, cancel_approval)
    before_snapshot = broker.snapshot()

    with pytest.raises(BrokerRejected, match="idempotency"):
        broker.cancel_order(genesis().portfolio_id, order.order_id, "cancel-two", "cancel-shared", 951, cancel_approval)

    events = broker.inspect("ledger")["events"]
    assert events[-1]["kind"] == "command.idempotency_conflict"
    assert events[-1]["payload"]["command_type"] == "order.cancel"
    assert events[-1]["idempotency_key"] is None
    assert broker.snapshot() == before_snapshot
    assert B41Broker.open(tmp_path, genesis().portfolio_id).inspect("ledger")["events"] == events


def test_submit_wrong_portfolio_is_recorded_and_replayed(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    other_genesis = B41Genesis.create("strategy-other", "synthetic-fixture-v1", policy())
    order = buy()
    order = B41Order(other_genesis.portfolio_id, order.order_id, order.command_id, order.idempotency_key, order.side, order.order_type, order.quantity, order.limit_price, order.submitted_at_ms)
    order_approval = B41Approval.for_command("approval-other", "owner", order.command_fingerprint, 900, 10_000)

    result = broker.submit_order(order, order_approval)

    assert result["state"] == "rejected"
    assert result["reason_code"] == "command.portfolio_mismatch"
    assert broker.inspect("risk")["records"][-1]["kind"] == "order.rejected"
    ledger_bytes = broker.ledger_path.read_bytes()
    assert broker.submit_order(order, order_approval) == result
    assert broker.ledger_path.read_bytes() == ledger_bytes
    recovered = B41Broker.open(tmp_path, genesis().portfolio_id)
    assert recovered.inspect("risk")["records"] == broker.inspect("risk")["records"]


def test_submit_idempotency_conflict_is_audited_and_recoverable(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    first = buy()
    broker.submit_order(first, approval(first))
    changed = B41Order(first.portfolio_id, "order-conflict", first.command_id, first.idempotency_key, first.side, first.order_type, first.quantity * 2, first.limit_price, first.submitted_at_ms)

    with pytest.raises(BrokerRejected, match="idempotency"):
        broker.submit_order(changed, approval(changed))

    events = broker.inspect("ledger")["events"]
    assert events[-1]["kind"] == "command.idempotency_conflict"
    assert events[-1]["payload"]["command_type"] == "order.submit"
    assert events[-1]["idempotency_key"] is None
    assert broker.inspect("risk")["records"][-1] == events[-1]
    assert B41Broker.open(tmp_path, genesis().portfolio_id).inspect("ledger")["events"] == events


def test_revoke_rejection_is_typed_idempotent_and_inspectable(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    order = buy()
    used_approval = approval(order)
    broker.submit_order(order, used_approval)

    result = broker.revoke_approval(used_approval.approval_id, "revoke-used", "revoke-used-key", 950)

    assert result["state"] == "rejected"
    assert result["reason_code"] == "approval.used_cannot_revoke"
    approval_records = broker.inspect("approvals", used_approval.approval_id)["records"]
    assert approval_records[-1]["kind"] == "approval.revoke.rejected"
    assert approval_records[-1]["result"] == result
    ledger_bytes = broker.ledger_path.read_bytes()
    assert broker.revoke_approval(used_approval.approval_id, "revoke-used", "revoke-used-key", 950) == result
    assert broker.ledger_path.read_bytes() == ledger_bytes

    recovered = B41Broker.open(tmp_path, genesis().portfolio_id)
    assert recovered.inspect("approvals", used_approval.approval_id) == broker.inspect("approvals", used_approval.approval_id)


def test_rejected_command_idempotency_conflict_is_audited_without_duplicate_identity(tmp_path: Path) -> None:
    broker = B41Broker(tmp_path, genesis(), policy())
    first = broker.revoke_approval("unknown-approval", "revoke-one", "shared-key", 950, approver_id="operator")
    assert first["reason_code"] == "approval.revocation_unauthorized"
    ledger_bytes = broker.ledger_path.read_bytes()

    with pytest.raises(BrokerRejected, match="idempotency"):
        broker.revoke_approval("different-approval", "revoke-two", "shared-key", 951, approver_id="operator")

    assert broker.ledger_path.read_bytes() != ledger_bytes
    records = broker.inspect("ledger")["events"]
    assert records[-1]["kind"] == "command.idempotency_conflict"
    assert records[-1]["idempotency_key"] is None
    assert records[-1]["result"]["reason_code"] == "command.idempotency_conflict"
    assert broker.inspect("approvals", "different-approval")["records"][-1] == records[-1]
    recovered = B41Broker.open(tmp_path, genesis().portfolio_id)
    assert recovered.inspect("ledger")["events"] == records
