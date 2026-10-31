from __future__ import annotations

import json
from pathlib import Path

import pytest

from market_os.local_mutation import LocalMutationAuthority
from market_os.portfolio_broker import B41Approval, B41Broker, B41Genesis, B41Order, B41Policy, BrokerRejected, _fingerprint
from market_os.paper_venue import BUY


KEY = b"local-test-signing-key-which-is-at-least-32-bytes"
SUBJECT = "operator.local"


def policy() -> B41Policy:
    return B41Policy(max_inventory_btc="10", max_loss_usdt="500", max_drawdown_usdt="500", loss_window_ms=86_400_000)


def order(genesis: B41Genesis, *, order_id: str = "order-1", strategy_id: str | None = None) -> B41Order:
    return B41Order(genesis.portfolio_id, order_id, "command-" + order_id, "key-" + order_id,
                    BUY, "market", "0.1", None, 900, strategy_id=strategy_id)


def approval(value: B41Order) -> B41Approval:
    return B41Approval.for_command("approval-" + value.order_id, "owner", value.command_fingerprint, 800, 10_000)


def authority_for(broker: B41Broker, subject: str = SUBJECT) -> LocalMutationAuthority:
    return LocalMutationAuthority(broker, KEY, subject, clock_ms=lambda: 1_500)


def token_for(auth: LocalMutationAuthority, operation: str, portfolio_id: str,
              fingerprint: str, key: str, *, issued: int = 1_000, expires: int = 2_000) -> str:
    return auth.issue(operation, portfolio_id=portfolio_id, command_fingerprint=fingerprint,
                      idempotency_key=key, issued_at_ms=issued, expires_at_ms=expires)


def test_valid_capability_audits_order_and_recovers_equivalently(tmp_path: Path) -> None:
    genesis = B41Genesis.create("strategy-a", "fixture-a", policy())
    broker = B41Broker(tmp_path, genesis, policy())
    auth = authority_for(broker)
    submitted = order(genesis)
    token = token_for(auth, "order.submit", genesis.portfolio_id, submitted.command_fingerprint, submitted.idempotency_key)

    result = auth.submit_order(submitted, approval(submitted), token)
    record = broker.inspect("ledger")["events"][-1]

    assert result["state"] == "open"
    assert record["payload"]["authorization"]["subject"] == SUBJECT
    assert record["payload"]["authorization"]["operation"] == "order.submit"
    assert record["payload"]["authorization"]["capability_fingerprint"]
    recovered = B41Broker.open(tmp_path, genesis.portfolio_id)
    assert recovered.snapshot() == broker.snapshot()
    assert recovered.inspect("ledger") == broker.inspect("ledger")
    assert recovered.inspect("risk") == broker.inspect("risk")


@pytest.mark.parametrize("mismatch,reason", [
    ("subject", "capability.subject_mismatch"),
    ("portfolio", "capability.portfolio_mismatch"),
    ("operation", "capability.operation_mismatch"),
    ("fingerprint", "capability.command_mismatch"),
    ("idempotency", "capability.idempotency_mismatch"),
])
def test_capability_binding_mismatch_fails_before_mutation(tmp_path: Path, mismatch: str, reason: str) -> None:
    genesis = B41Genesis.create("strategy-a", "fixture-a", policy())
    broker = B41Broker(tmp_path, genesis, policy())
    auth = authority_for(broker)
    submitted = order(genesis)
    payload = {
        "subject": SUBJECT,
        "portfolio_id": genesis.portfolio_id,
        "operation": "order.submit",
        "fingerprint": submitted.command_fingerprint,
        "idempotency": submitted.idempotency_key,
    }
    if mismatch == "subject":
        payload["subject"] = "other.operator"
    elif mismatch == "portfolio":
        payload["portfolio_id"] = "portfolio-other"
    elif mismatch == "operation":
        payload["operation"] = "order.cancel"
    elif mismatch == "fingerprint":
        payload["fingerprint"] = "f" * 64
    elif mismatch == "idempotency":
        payload["idempotency"] = "different-key"
    issuer = auth
    if mismatch == "portfolio":
        other_genesis = B41Genesis.create("strategy-other", "fixture-a", policy())
        issuer = authority_for(B41Broker(tmp_path / "other", other_genesis, policy()))
        payload["portfolio_id"] = other_genesis.portfolio_id
    token = issuer.issue(payload["operation"], portfolio_id=payload["portfolio_id"],
                         command_fingerprint=payload["fingerprint"], idempotency_key=payload["idempotency"],
                         issued_at_ms=1_000, expires_at_ms=2_000)
    if mismatch == "subject":
        other_auth = authority_for(broker, "other.operator")
        with pytest.raises(BrokerRejected) as error:
            other_auth.submit_order(submitted, approval(submitted), token)
    else:
        with pytest.raises(BrokerRejected) as error:
            auth.submit_order(submitted, approval(submitted), token)
    assert error.value.reason_code == reason
    assert broker.snapshot()["orders"] == []
    assert not broker.ledger_path.exists()
    assert not broker.checkpoint_path.exists()


def test_capability_rejects_malformed_tampered_and_wrong_signing_key(tmp_path: Path) -> None:
    genesis = B41Genesis.create("strategy-a", "fixture-a", policy())
    broker = B41Broker(tmp_path, genesis, policy())
    auth = authority_for(broker)
    submitted = order(genesis)
    token = token_for(auth, "order.submit", genesis.portfolio_id, submitted.command_fingerprint, submitted.idempotency_key)
    other_key_auth = LocalMutationAuthority(broker, b"another-key-that-is-long-enough-for-testing", SUBJECT)
    forged = token[:-1] + ("A" if token[-1] != "A" else "B")

    for bad in ("not-a-token", forged, token + ".extra"):
        with pytest.raises(BrokerRejected) as error:
            auth.submit_order(submitted, approval(submitted), bad)
        assert error.value.reason_code == "capability.invalid"
    with pytest.raises(BrokerRejected) as error:
        other_key_auth.submit_order(submitted, approval(submitted), token)
    assert error.value.reason_code == "capability.invalid"
    assert not broker.ledger_path.exists()


@pytest.mark.parametrize("now,reason", [(999, "capability.not_yet_valid"), (2_000, "capability.expired")])
def test_capability_validity_window_is_half_open(tmp_path: Path, now: int, reason: str) -> None:
    genesis = B41Genesis.create("strategy-a", "fixture-a", policy())
    broker = B41Broker(tmp_path, genesis, policy())
    auth = authority_for(broker)
    submitted = order(genesis)
    token = token_for(auth, "order.submit", genesis.portfolio_id, submitted.command_fingerprint, submitted.idempotency_key)
    clocked = LocalMutationAuthority(broker, KEY, SUBJECT, clock_ms=lambda: now)
    with pytest.raises(BrokerRejected) as error:
        clocked.submit_order(submitted, approval(submitted), token)
    assert error.value.reason_code == reason
    assert not broker.ledger_path.exists()


def test_authenticated_retry_is_idempotent_and_conflicting_command_stays_rejected(tmp_path: Path) -> None:
    genesis = B41Genesis.create("strategy-a", "fixture-a", policy())
    broker = B41Broker(tmp_path, genesis, policy())
    auth = authority_for(broker)
    submitted = order(genesis)
    token = token_for(auth, "order.submit", genesis.portfolio_id, submitted.command_fingerprint, submitted.idempotency_key)
    first = auth.submit_order(submitted, approval(submitted), token)
    ledger = broker.ledger_path.read_bytes()
    retry_token = token_for(auth, "order.submit", genesis.portfolio_id, submitted.command_fingerprint,
                            submitted.idempotency_key, issued=1_499, expires=2_500)

    assert auth.submit_order(submitted, approval(submitted), retry_token) == first
    assert broker.ledger_path.read_bytes() == ledger
    changed = B41Order(genesis.portfolio_id, "order-2", "command-order-2", submitted.idempotency_key,
                       BUY, "market", "0.2", None, 901)
    changed_token = token_for(auth, "order.submit", genesis.portfolio_id,
                              changed.command_fingerprint, changed.idempotency_key)
    with pytest.raises(BrokerRejected, match="idempotency key conflicts"):
        auth.submit_order(changed, approval(changed), changed_token)
    assert broker.inspect("ledger")["events"][-1]["kind"] == "command.idempotency_conflict"
    assert broker.inspect("ledger")["events"][-1]["payload"]["authorization"]["subject"] == SUBJECT


def test_authenticated_cancel_and_revoke_use_exact_command_fingerprints(tmp_path: Path) -> None:
    genesis = B41Genesis.create("strategy-a", "fixture-a", policy())
    broker = B41Broker(tmp_path, genesis, policy())
    auth = authority_for(broker)
    submitted = order(genesis)
    submit_token = token_for(auth, "order.submit", genesis.portfolio_id, submitted.command_fingerprint, submitted.idempotency_key)
    auth.submit_order(submitted, approval(submitted), submit_token)
    projection = {"portfolio_id": genesis.portfolio_id, "order_id": submitted.order_id,
                  "command_id": "cancel-1", "idempotency_key": "cancel-key", "submitted_at_ms": 950}
    cancel_fingerprint = _fingerprint(projection)
    cancel_approval = B41Approval.for_command("cancel-approval", "owner", cancel_fingerprint, 900, 10_000)
    cancel_token = token_for(auth, "order.cancel", genesis.portfolio_id, cancel_fingerprint, "cancel-key")
    cancelled = auth.cancel_order(genesis.portfolio_id, submitted.order_id, "cancel-1", "cancel-key",
                                  950, cancel_approval, cancel_token)
    assert cancelled["state"] == "cancelled"

    revoke_projection = {"approval_id": "unused-approval", "command_id": "revoke-1",
                         "idempotency_key": "revoke-key", "revoked_at_ms": 960}
    revoke_fingerprint = _fingerprint(revoke_projection)
    revoke_token = token_for(auth, "approval.revoke", genesis.portfolio_id, revoke_fingerprint, "revoke-key")
    revoked = auth.revoke_approval("unused-approval", "revoke-1", "revoke-key", 960,
                                   revoke_token)
    assert revoked["state"] == "revoked"
    kinds = [row["kind"] for row in broker.inspect("ledger")["events"]]
    assert kinds[-2:] == ["order.cancelled", "approval.revoked"]


def test_shared_strategy_capability_binds_order_membership_and_stale_writers(tmp_path: Path) -> None:
    policy_value = policy()
    genesis = B41Genesis.create_shared("shared-local", "fixture-a", ("strategy-a", "strategy-b"), policy_value)
    writer = B41Broker(tmp_path, genesis, policy_value)
    stale = B41Broker.open(tmp_path, genesis.portfolio_id)
    auth = authority_for(writer)
    submitted = order(genesis, order_id="shared-order", strategy_id="strategy-a")
    token = token_for(auth, "order.submit", genesis.portfolio_id, submitted.command_fingerprint, submitted.idempotency_key)
    assert auth.submit_order(submitted, approval(submitted), token)["state"] == "open"

    stale_order = order(genesis, order_id="stale-order", strategy_id="strategy-b")
    stale_auth = authority_for(stale)
    stale_token = token_for(stale_auth, "order.submit", genesis.portfolio_id,
                            stale_order.command_fingerprint, stale_order.idempotency_key)
    with pytest.raises(BrokerRejected, match="stale portfolio snapshot"):
        stale_auth.submit_order(stale_order, approval(stale_order), stale_token)
    reloaded = B41Broker.open(tmp_path, genesis.portfolio_id)
    result = authority_for(reloaded).submit_order(
        stale_order, approval(stale_order),
        token_for(authority_for(reloaded), "order.submit", genesis.portfolio_id,
                  stale_order.command_fingerprint, stale_order.idempotency_key),
    )
    assert result["state"] == "open"
    assert reloaded.inspect("reservations")["cash_usdt"] > 0


def test_raw_secret_and_capability_never_enter_portfolio_artifacts(tmp_path: Path) -> None:
    genesis = B41Genesis.create("strategy-a", "fixture-a", policy())
    broker = B41Broker(tmp_path, genesis, policy())
    auth = authority_for(broker)
    submitted = order(genesis)
    token = token_for(auth, "order.submit", genesis.portfolio_id, submitted.command_fingerprint, submitted.idempotency_key)
    auth.submit_order(submitted, approval(submitted), token)
    files = [broker.genesis_path, broker.policy_path, broker.ledger_path, broker.checkpoint_path]
    for path in files:
        raw = path.read_bytes()
        assert KEY not in raw
        assert token.encode("ascii") not in raw
    inspected = json.dumps(broker.inspect_jsonable("ledger"), sort_keys=True)
    assert token not in inspected
    assert KEY.decode("ascii") not in inspected


def test_capability_requires_nontrivial_in_memory_key() -> None:
    with pytest.raises(ValueError, match="at least 32 bytes"):
        LocalMutationAuthority(object(), b"short", SUBJECT)  # type: ignore[arg-type]


def test_broker_rejects_forged_authorization_context(tmp_path: Path) -> None:
    genesis = B41Genesis.create("strategy-a", "fixture-a", policy())
    broker = B41Broker(tmp_path, genesis, policy())
    submitted = order(genesis)
    with pytest.raises(BrokerRejected, match="authorization context"):
        broker.submit_order(
            submitted,
            approval(submitted),
            _authorization_context={
                "subject": SUBJECT,
                "operation": "made-up.operation",
                "capability_fingerprint": "0" * 64,
            },
        )
