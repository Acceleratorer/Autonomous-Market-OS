"""Synthetic, paper-only B4.1 portfolio and virtual broker.

This module deliberately has no provider, network, credential, or live venue
path.  It persists an append-only JSONL ledger and derives state from the
approved synthetic policy and recorded market events.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, InvalidOperation
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import threading
from contextlib import contextmanager
import re
from typing import Any, Mapping

from .paper_venue import BUY, LIMIT, MARKET, SELL, SyntheticMarketEvent


SCHEMA = "market-os.b4-1.paper-broker@v1"
GENESIS_SCHEMA = "market-os.b4-1.paper-portfolio-genesis@v1"
EVENT_SCHEMA = "market-os.b4-1.paper-portfolio-event@v1"
SNAPSHOT_SCHEMA = "market-os.b4-1.portfolio-snapshot@v1"
ORDER_STATES = frozenset({"accepted", "open", "filled", "cancelled", "expired", "risk_rejected"})
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


class BrokerRejected(ValueError):
    """A fail-closed paper command rejection."""

    def __init__(self, message: str, reason_code: str = "broker.rejected") -> None:
        super().__init__(message)
        self.reason_code = reason_code


def _decimal(value: Any, field: str, *, positive: bool = False, nonnegative: bool = False) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise BrokerRejected(f"{field} must be numeric") from exc
    if not result.is_finite() or (positive and result <= 0) or (nonnegative and result < 0):
        raise BrokerRejected(f"{field} has an invalid value")
    return result


def _int(value: Any, field: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or (positive and value <= 0) or (not positive and value < 0):
        raise BrokerRejected(f"{field} must be a valid integer")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 160 or any(ord(char) < 32 for char in value):
        raise BrokerRejected(f"{field} must be a bounded non-empty string")
    return value


def _identifier(value: Any, field: str) -> str:
    result = _text(value, field)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", result):
        raise BrokerRejected(f"{field} must be a stable identifier")
    return result


def _canonical(value: Any) -> str:
    def normalize(item: Any) -> Any:
        if isinstance(item, Decimal):
            return format(item, "f")
        if isinstance(item, Mapping):
            return {str(key): normalize(item[key]) for key in sorted(item, key=str)}
        if isinstance(item, (list, tuple)):
            return [normalize(child) for child in item]
        return item

    return json.dumps(normalize(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _q(value: Decimal, quantum: Decimal) -> Decimal:
    return value.quantize(quantum, rounding=ROUND_HALF_EVEN)


def _as_decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _read_json_object(path: Path, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BrokerRejected(f"{label} is malformed") from exc
    if not isinstance(value, Mapping):
        raise BrokerRejected(f"{label} is malformed")
    return value


def _restore_snapshot_or_reject(broker: "B41Broker", snapshot: Mapping[str, Any]) -> None:
    try:
        broker._restore_snapshot(snapshot)
    except (BrokerRejected, KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise BrokerRejected("ledger resulting snapshot is malformed") from exc


@contextmanager
def _process_lock(path: Path):
    """Lock one portfolio across threads and local processes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            if handle.read(1) == b"":
                handle.seek(0)
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _portfolio_write(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        with self._lock, _process_lock(self.lock_path):
            if self._ledger_head() != self._last_ledger_fingerprint:
                raise BrokerRejected("stale portfolio snapshot; reload before writing")
            return method(self, *args, **kwargs)

    return guarded


@dataclass(frozen=True)
class B41Policy:
    """Owner-approved B4.1 policy; unresolved numeric limits are required."""

    fee_bps_per_side: Decimal = Decimal("10")
    spread_bps_per_side: Decimal = Decimal("1")
    slippage_bps_per_side: Decimal = Decimal("0.5")
    initial_cash_usdt: Decimal = Decimal("10000")
    initial_btc_quantity: Decimal = Decimal("0")
    initial_average_entry_price: Decimal = Decimal("0")
    max_order_notional_usdt: Decimal = Decimal("1000")
    price_quantum: Decimal = Decimal("0.01")
    quantity_step: Decimal = Decimal("0.000001")
    minimum_notional_usdt: Decimal = Decimal("10")
    max_inventory_btc: Decimal | None = None
    max_loss_usdt: Decimal | None = None
    max_drawdown_usdt: Decimal | None = None
    loss_window_ms: int | None = None
    policy_version: str = "b4.1-approved-defaults-v1"

    def __post_init__(self) -> None:
        for name in ("fee_bps_per_side", "spread_bps_per_side", "slippage_bps_per_side", "initial_cash_usdt", "initial_btc_quantity", "initial_average_entry_price", "max_order_notional_usdt", "price_quantum", "quantity_step", "minimum_notional_usdt"):
            value = _decimal(getattr(self, name), name, nonnegative=True)
            object.__setattr__(self, name, value)
        for name in ("max_inventory_btc", "max_loss_usdt", "max_drawdown_usdt"):
            value = getattr(self, name)
            if value is None:
                raise BrokerRejected(f"{name} is required by approved B4.1 policy")
            object.__setattr__(self, name, _decimal(value, name, positive=True))
        if self.loss_window_ms is None or self.loss_window_ms <= 0:
            raise BrokerRejected("loss_window_ms is required by approved B4.1 policy")
        if self.initial_btc_quantity > 0 and self.initial_average_entry_price <= 0:
            raise BrokerRejected("initial_average_entry_price is required for initial BTC")
        if self.initial_btc_quantity == 0 and self.initial_average_entry_price != 0:
            raise BrokerRejected("initial_average_entry_price requires initial BTC")
        if self.max_order_notional_usdt <= 0 or self.price_quantum <= 0 or self.quantity_step <= 0 or self.minimum_notional_usdt <= 0:
            raise BrokerRejected("approved B4.1 positive policy values are invalid")
        if self.initial_cash_usdt != _q(self.initial_cash_usdt, Decimal("0.01")):
            raise BrokerRejected("initial_cash_usdt exceeds approved precision")
        if self.initial_btc_quantity % self.quantity_step != 0:
            raise BrokerRejected("initial_btc_quantity is off quantity_step")
        if self.initial_average_entry_price != _q(self.initial_average_entry_price, self.price_quantum):
            raise BrokerRejected("initial_average_entry_price exceeds approved precision")

    def to_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA + ".policy", **{name: getattr(self, name) for name in self.__dataclass_fields__}}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "B41Policy":
        if payload.get("schema") != SCHEMA + ".policy" or "policy_version" not in payload:
            raise BrokerRejected("unsupported or incomplete policy identity")
        values = {name: payload[name] for name in cls.__dataclass_fields__ if name in payload}
        return cls(**values)

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.to_dict())


@dataclass(frozen=True)
class B41Genesis:
    portfolio_id: str
    strategy_id: str
    fixture_lineage: str
    symbol: str = "BTCUSDT"
    quote_asset: str = "USDT"
    base_asset: str = "BTC"
    policy_fingerprint: str = ""
    initial_cash_usdt: Decimal = Decimal("10000")
    initial_btc_quantity: Decimal = Decimal("0")
    initial_average_entry_price: Decimal = Decimal("0")
    synthetic_only: bool = True
    schema: str = GENESIS_SCHEMA

    def __post_init__(self) -> None:
        for name in ("strategy_id", "fixture_lineage", "symbol", "quote_asset", "base_asset"):
            _text(getattr(self, name), name)
        _identifier(self.portfolio_id, "portfolio_id")
        object.__setattr__(self, "initial_cash_usdt", _decimal(self.initial_cash_usdt, "initial_cash_usdt", nonnegative=True))
        object.__setattr__(self, "initial_btc_quantity", _decimal(self.initial_btc_quantity, "initial_btc_quantity", nonnegative=True))
        object.__setattr__(self, "initial_average_entry_price", _decimal(self.initial_average_entry_price, "initial_average_entry_price", nonnegative=True))
        if self.symbol != "BTCUSDT" or self.quote_asset != "USDT" or self.base_asset != "BTC":
            raise BrokerRejected("B4.1 is restricted to synthetic BTCUSDT Spot")
        if self.synthetic_only is not True or self.schema != GENESIS_SCHEMA:
            raise BrokerRejected("genesis must be synthetic-only and versioned")
        identity = {"strategy_id": self.strategy_id, "symbol": self.symbol, "fixture_lineage": self.fixture_lineage}
        if self.portfolio_id != "portfolio-" + _fingerprint(identity)[:24]:
            raise BrokerRejected("portfolio_id must match strategy, instrument, and fixture lineage")
        if self.initial_btc_quantity > 0 and self.initial_average_entry_price <= 0:
            raise BrokerRejected("initial BTC requires an explicit cost basis")
        if self.initial_btc_quantity == 0 and self.initial_average_entry_price != 0:
            raise BrokerRejected("initial cost basis requires initial BTC")

    @classmethod
    def create(cls, strategy_id: str, fixture_lineage: str, policy: B41Policy) -> "B41Genesis":
        identity = {"strategy_id": strategy_id, "symbol": "BTCUSDT", "fixture_lineage": fixture_lineage}
        portfolio_id = "portfolio-" + _fingerprint(identity)[:24]
        return cls(portfolio_id, strategy_id, fixture_lineage, policy_fingerprint=policy.fingerprint, initial_cash_usdt=policy.initial_cash_usdt, initial_btc_quantity=policy.initial_btc_quantity, initial_average_entry_price=policy.initial_average_entry_price)

    def bind_policy(self, policy: B41Policy) -> None:
        if self.policy_fingerprint != policy.fingerprint:
            raise BrokerRejected("genesis policy fingerprint mismatch")
        if (self.initial_cash_usdt, self.initial_btc_quantity, self.initial_average_entry_price) != (policy.initial_cash_usdt, policy.initial_btc_quantity, policy.initial_average_entry_price):
            raise BrokerRejected("genesis wallet does not match pinned policy")

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class B41Order:
    portfolio_id: str
    order_id: str
    command_id: str
    idempotency_key: str
    side: str
    order_type: str
    quantity: Decimal
    limit_price: Decimal | None
    submitted_at_ms: int
    state: str = "accepted"
    command_fingerprint: str = ""

    def __post_init__(self) -> None:
        for name in ("portfolio_id", "order_id", "command_id", "idempotency_key"):
            _text(getattr(self, name), name)
        if self.side not in (BUY, SELL) or self.order_type not in (MARKET, LIMIT):
            raise BrokerRejected("unsupported order side or type")
        object.__setattr__(self, "quantity", _decimal(self.quantity, "quantity", positive=True))
        if self.order_type == LIMIT:
            if self.limit_price is None:
                raise BrokerRejected("limit orders require limit_price")
            object.__setattr__(self, "limit_price", _decimal(self.limit_price, "limit_price", positive=True))
        elif self.limit_price is not None:
            raise BrokerRejected("market orders cannot carry limit_price")
        _int(self.submitted_at_ms, "submitted_at_ms")
        if self.state not in ORDER_STATES:
            raise BrokerRejected("unsupported order state")
        expected = _fingerprint(self._command_projection())
        if self.command_fingerprint and self.command_fingerprint != expected:
            raise BrokerRejected("order command fingerprint mismatch")
        object.__setattr__(self, "command_fingerprint", expected)

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in ("portfolio_id", "order_id", "command_id", "idempotency_key", "side", "order_type", "quantity", "limit_price", "submitted_at_ms")}
        result["state"] = self.state
        if include_fingerprint:
            result["command_fingerprint"] = self.command_fingerprint
        return result

    def _command_projection(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in ("portfolio_id", "order_id", "command_id", "idempotency_key", "side", "order_type", "quantity", "limit_price", "submitted_at_ms")}


@dataclass(frozen=True)
class B41Approval:
    approval_id: str
    approver_id: str
    command_fingerprint: str
    issued_at_ms: int
    expires_at_ms: int
    revoked: bool = False
    single_use: bool = True

    @classmethod
    def for_command(cls, approval_id: str, approver_id: str, command_fingerprint: str, issued_at_ms: int, expires_at_ms: int) -> "B41Approval":
        return cls(approval_id, approver_id, command_fingerprint, issued_at_ms, expires_at_ms)

    def __post_init__(self) -> None:
        _text(self.approval_id, "approval_id")
        if self.approver_id != "owner":
            raise BrokerRejected("approver identity is not authorized")
        if len(self.command_fingerprint) != 64:
            raise BrokerRejected("approval must bind an exact command fingerprint")
        _int(self.issued_at_ms, "issued_at_ms")
        _int(self.expires_at_ms, "expires_at_ms", positive=True)
        if self.expires_at_ms <= self.issued_at_ms:
            raise BrokerRejected("approval expiry must be after issue time")

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


class B41Broker:
    def __init__(self, root: str | Path, genesis: B41Genesis, policy: B41Policy) -> None:
        self.root = Path(root).resolve() / genesis.portfolio_id
        self.root.mkdir(parents=True, exist_ok=True)
        self.genesis = genesis
        self.policy = policy
        self.genesis_path = self.root / "genesis.json"
        self.policy_path = self.root / "policy.json"
        self.ledger_path = self.root / "ledger.jsonl"
        self.checkpoint_path = self.root / "checkpoint.json"
        self.lock_path = self.root / ".writer.lock"
        with _LOCKS_GUARD:
            self._lock = _LOCKS.setdefault(str(self.root), threading.RLock())
        if self.genesis_path.exists():
            stored = B41Genesis(**_read_json_object(self.genesis_path, "genesis"))
            if stored.to_dict() != genesis.to_dict():
                raise BrokerRejected("portfolio genesis identity conflict")
        else:
            self._atomic_write(self.genesis_path, genesis.to_dict())
        genesis.bind_policy(policy)
        if self.policy_path.exists():
            stored_policy = B41Policy.from_dict(_read_json_object(self.policy_path, "policy"))
            if stored_policy.fingerprint != policy.fingerprint:
                raise BrokerRejected("portfolio policy identity conflict")
        else:
            self._atomic_write(self.policy_path, policy.to_dict())
        self._orders: list[B41Order] = []
        self._fills: list[dict[str, Any]] = []
        self._cursor: list[str] = []
        self._cash = policy.initial_cash_usdt
        self._btc = policy.initial_btc_quantity
        self._average = policy.initial_average_entry_price
        self._realized = Decimal("0")
        self._fees = Decimal("0")
        self._notional = Decimal("0")
        self._mark = Decimal("0")
        self._peak_equity = self._equity()
        self._last_event_time_ms: int | None = None
        self._equity_history: list[tuple[int, Decimal]] = []
        self._revoked_approval_ids: list[str] = []
        self._snapshot_fingerprint = _fingerprint(self._snapshot_payload())
        self._last_ledger_fingerprint = self._ledger_head()
        if self._last_ledger_fingerprint != "0" * 64:
            recovered = self.recover(root, genesis.portfolio_id, policy)
            self.__dict__.update(recovered.__dict__)

    @classmethod
    def recover(cls, root: str | Path, portfolio_id: str, policy: B41Policy) -> "B41Broker":
        directory = Path(root).resolve() / portfolio_id
        genesis_path = directory / "genesis.json"
        if not genesis_path.exists():
            raise BrokerRejected("missing portfolio genesis")
        genesis = B41Genesis(**_read_json_object(genesis_path, "genesis"))
        genesis.bind_policy(policy)
        policy_path = directory / "policy.json"
        if not policy_path.exists():
            raise BrokerRejected("missing portfolio policy")
        stored_policy = B41Policy.from_dict(_read_json_object(policy_path, "policy"))
        if stored_policy.fingerprint != policy.fingerprint:
            raise BrokerRejected("portfolio policy identity conflict")
        broker = object.__new__(cls)
        broker.root = directory
        broker.genesis = genesis
        broker.policy = policy
        broker.genesis_path = directory / "genesis.json"
        broker.policy_path = directory / "policy.json"
        broker.ledger_path = directory / "ledger.jsonl"
        broker.checkpoint_path = directory / "checkpoint.json"
        broker.lock_path = directory / ".writer.lock"
        with _LOCKS_GUARD:
            broker._lock = _LOCKS.setdefault(str(directory), threading.RLock())
        broker._orders = []
        broker._fills = []
        broker._cursor = []
        broker._cash = policy.initial_cash_usdt
        broker._btc = policy.initial_btc_quantity
        broker._average = policy.initial_average_entry_price
        broker._realized = Decimal("0")
        broker._fees = Decimal("0")
        broker._notional = Decimal("0")
        broker._mark = Decimal("0")
        broker._peak_equity = broker._equity()
        broker._last_event_time_ms = None
        broker._equity_history = []
        broker._revoked_approval_ids: list[str] = []
        broker._snapshot_fingerprint = _fingerprint(broker._snapshot_payload())
        previous = "0" * 64
        command_idempotency: set[tuple[str, str]] = set()
        try:
            ledger_lines = broker.ledger_path.read_text(encoding="utf-8").splitlines() if broker.ledger_path.exists() else []
        except UnicodeDecodeError as exc:
            raise BrokerRejected("ledger record is malformed") from exc
        for expected_sequence, line in enumerate(ledger_lines, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BrokerRejected("ledger record is malformed") from exc
            if not isinstance(record, Mapping):
                raise BrokerRejected("ledger record is malformed")
            if record.get("schema") != EVENT_SCHEMA or record.get("sequence") != expected_sequence:
                raise BrokerRejected("ledger sequence or schema is invalid")
            if record.get("portfolio_id") != genesis.portfolio_id:
                raise BrokerRejected("ledger portfolio identity mismatch")
            key = record.get("idempotency_key")
            if key is not None:
                kind = "order.submit" if record.get("kind") in {"order.accepted", "order.rejected"} else record.get("kind")
                identity = (kind, key)
                if identity in command_idempotency:
                    raise BrokerRejected("duplicate command idempotency identity")
                command_idempotency.add(identity)
            if record.get("previous_event_fingerprint") != previous or record.get("event_fingerprint") != _fingerprint({key: value for key, value in record.items() if key != "event_fingerprint"}):
                raise BrokerRejected("ledger fingerprint chain is invalid")
            resulting_snapshot = record.get("resulting_snapshot")
            if not isinstance(resulting_snapshot, Mapping) or resulting_snapshot.get("schema") != SNAPSHOT_SCHEMA or resulting_snapshot.get("portfolio_id") != genesis.portfolio_id:
                raise BrokerRejected("ledger resulting snapshot identity is invalid")
            if record.get("resulting_snapshot_fingerprint") is not None and record.get("resulting_snapshot_fingerprint") != _fingerprint(resulting_snapshot):
                raise BrokerRejected("resulting snapshot fingerprint mismatch")
            _restore_snapshot_or_reject(broker, record["resulting_snapshot"])
            if len(broker._cursor) != len(set(broker._cursor)):
                raise BrokerRejected("ledger contains duplicate market event IDs")
            previous = record["event_fingerprint"]
        broker._snapshot_fingerprint = _fingerprint(broker._snapshot_payload())
        broker._last_ledger_fingerprint = previous
        if broker.ledger_path.exists() and broker.checkpoint_path.exists():
            checkpoint = _read_json_object(broker.checkpoint_path, "checkpoint")
            if checkpoint.get("schema") != SNAPSHOT_SCHEMA + ".checkpoint":
                raise BrokerRejected("checkpoint schema mismatch")
            if checkpoint.get("sequence") != len([line for line in ledger_lines if line.strip()]):
                raise BrokerRejected("checkpoint sequence mismatch")
            checkpoint_snapshot = checkpoint.get("snapshot")
            if not isinstance(checkpoint_snapshot, Mapping) or checkpoint_snapshot.get("schema") != SNAPSHOT_SCHEMA or checkpoint_snapshot.get("portfolio_id") != genesis.portfolio_id:
                raise BrokerRejected("checkpoint snapshot identity mismatch")
            if checkpoint.get("snapshot_fingerprint") != _fingerprint(checkpoint_snapshot):
                raise BrokerRejected("checkpoint snapshot fingerprint mismatch")
            if checkpoint.get("snapshot_fingerprint") != broker._snapshot_fingerprint or _canonical(checkpoint_snapshot) != _canonical(broker._snapshot_payload()):
                raise BrokerRejected("checkpoint fingerprint mismatch")
        return broker

    @classmethod
    def open(cls, root: str | Path, portfolio_id: str) -> "B41Broker":
        _identifier(portfolio_id, "portfolio_id")
        directory = Path(root).resolve() / portfolio_id
        policy_path = directory / "policy.json"
        if not policy_path.exists():
            raise BrokerRejected("missing portfolio policy")
        return cls.recover(root, portfolio_id, B41Policy.from_dict(_read_json_object(policy_path, "policy")))

    @property
    def open_orders(self) -> tuple[B41Order, ...]:
        return tuple(order for order in self._orders if order.state == "open")

    @property
    def snapshot_fingerprint(self) -> str:
        return self._snapshot_fingerprint

    def snapshot(self) -> dict[str, Any]:
        return self._snapshot_payload()

    def inspect(self, resource: str, item_id: str | None = None) -> dict[str, Any]:
        if resource not in {"summary", "snapshot", "orders", "fills", "ledger", "risk", "approvals", "fingerprints", "replay", "policy", "genesis"}:
            raise KeyError(resource)
        if resource == "policy":
            return self.policy.to_dict() | {"fingerprint": self.policy.fingerprint}
        if resource == "genesis":
            return self.genesis.to_dict()
        if resource == "ledger":
            records = [json.loads(line) for line in self.ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()] if self.ledger_path.exists() else []
            if item_id is not None:
                records = [record for record in records if str(record.get("sequence")) == item_id or record.get("event_fingerprint") == item_id]
            return {"portfolio_id": self.genesis.portfolio_id, "events": records}
        if resource in {"risk", "approvals"}:
            records = [json.loads(line) for line in self.ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()] if self.ledger_path.exists() else []
            selected = [record for record in records if record.get("kind", "").startswith("risk.") or (resource == "approvals" and "approval" in record.get("payload", {})) or (resource == "risk" and (record.get("kind") in {"command.rejected", "order.rejected"} or record.get("result", {}).get("risk_rejections")))]
            if resource == "approvals":
                selected = [record for record in records if "approval" in record.get("payload", {}) or record.get("kind") == "approval.revoked"]
            if item_id is not None:
                selected = [record for record in selected if record.get("payload", {}).get("approval", {}).get("approval_id") == item_id or record.get("result", {}).get("reason_code") == item_id]
            return {"portfolio_id": self.genesis.portfolio_id, "records": selected}
        if resource == "fingerprints":
            return {"portfolio_id": self.genesis.portfolio_id, "snapshot_fingerprint": self.snapshot_fingerprint, "ledger_head": self._ledger_head(), "policy_fingerprint": self.policy.fingerprint}
        snapshot = self.snapshot()
        if resource == "summary":
            return {key: snapshot[key] for key in ("schema", "portfolio_id", "cash_usdt", "btc_quantity", "mark_price", "realized_pnl_usdt", "total_fees_usdt", "event_cursor")}
        if resource == "orders":
            rows = snapshot["orders"]
            return {"portfolio_id": self.genesis.portfolio_id, "orders": [row for row in rows if item_id is None or row["order_id"] == item_id]}
        if resource == "fills":
            rows = snapshot["fills"]
            return {"portfolio_id": self.genesis.portfolio_id, "fills": [row for row in rows if item_id is None or row["fill_id"] == item_id]}
        if resource == "replay":
            return {"portfolio_id": self.genesis.portfolio_id, "snapshot_fingerprint": self.snapshot_fingerprint, "ledger_head": self._ledger_head(), "event_count": len(snapshot["event_cursor"]), "recovery": "verified", "checkpoint": "verified" if self.checkpoint_path.exists() else "missing"}
        return snapshot

    def inspect_jsonable(self, resource: str, item_id: str | None = None) -> dict[str, Any]:
        return json.loads(_canonical(self.inspect(resource, item_id)))

    @_portfolio_write
    def submit_order(self, order: B41Order, approval: B41Approval) -> dict[str, Any]:
        if order.portfolio_id != self.genesis.portfolio_id:
            raise BrokerRejected("portfolio identity mismatch")
        existing = self._find_idempotency(order.idempotency_key, ("order.accepted", "order.rejected"))
        if existing is not None:
            if existing["command_fingerprint"] == order.command_fingerprint:
                return existing
            raise BrokerRejected("idempotency key conflicts with a different command")
        try:
            if self._last_event_time_ms is not None and order.submitted_at_ms <= self._last_event_time_ms:
                raise BrokerRejected("order cannot backdate into a processed market event", "order.backdated")
            if approval.command_fingerprint != order.command_fingerprint:
                raise BrokerRejected("approval command fingerprint mismatch", "approval.command_mismatch")
            if approval.revoked or not approval.single_use or approval.issued_at_ms > order.submitted_at_ms or approval.expires_at_ms <= order.submitted_at_ms:
                raise BrokerRejected("approval is expired or revoked", "approval.expired_or_revoked")
            if approval.approval_id in self._revoked_approval_ids or self._approval_used(approval.approval_id):
                raise BrokerRejected("approval is revoked or already used", "approval.reused_or_revoked")
            if any(existing.order_id == order.order_id for existing in self._orders):
                raise BrokerRejected("duplicate order_id", "order.duplicate_id")
            if order.quantity % self.policy.quantity_step != 0:
                raise BrokerRejected("quantity is off quantity_step", "order.quantity_step")
            if order.limit_price is not None and order.limit_price != _q(order.limit_price, self.policy.price_quantum):
                raise BrokerRejected("limit_price is off price precision", "order.price_precision")
            if order.order_type == LIMIT and order.quantity * order.limit_price < self.policy.minimum_notional_usdt:
                raise BrokerRejected("order is below minimum notional", "risk.minimum_notional")
            if order.order_type == LIMIT and order.quantity * order.limit_price > self.policy.max_order_notional_usdt:
                raise BrokerRejected("order exceeds max_order_notional_usdt", "risk.max_order_notional")
            if order.side == SELL:
                reserved_btc = sum((candidate.quantity for candidate in self.open_orders if candidate.side == SELL), Decimal("0"))
                if reserved_btc + order.quantity > self._btc:
                    raise BrokerRejected("sell order exceeds unreserved BTC inventory", "risk.inventory_limit")
            else:
                order_reserve = order.quantity * order.limit_price if order.order_type == LIMIT else self.policy.max_order_notional_usdt
                existing_reserve = sum((candidate.quantity * candidate.limit_price if candidate.order_type == LIMIT else self.policy.max_order_notional_usdt for candidate in self.open_orders if candidate.side == BUY), Decimal("0"))
                if (existing_reserve + order_reserve) * (Decimal("1") + self.policy.fee_bps_per_side / Decimal("10000")) > self._cash:
                    raise BrokerRejected("buy order exceeds unreserved cash", "risk.cash_reserve")
                reserved_btc = sum((candidate.quantity for candidate in self.open_orders if candidate.side == BUY), Decimal("0"))
                if self._btc + reserved_btc + order.quantity > self.policy.max_inventory_btc:
                    raise BrokerRejected("buy order exceeds reserved inventory limit", "risk.inventory_limit")
        except BrokerRejected as exc:
            result = {"command_id": order.command_id, "idempotency_key": order.idempotency_key, "order_id": order.order_id, "state": "rejected", "reason_code": exc.reason_code, "reason": str(exc), "command_fingerprint": order.command_fingerprint}
            self._append_event("order.rejected", {"order": order.to_dict(), "approval": approval.to_dict(), "reason_code": exc.reason_code}, result)
            return result
        record = {"command_fingerprint": order.command_fingerprint, "idempotency_key": order.idempotency_key, "order_id": order.order_id, "state": "open"}
        accepted = B41Order(**{**order.to_dict(include_fingerprint=False), "state": "open"})
        self._orders.append(accepted)
        try:
            self._append_event("order.accepted", {"order": order.to_dict(), "approval": approval.to_dict()}, record)
        except Exception:
            self._orders.pop()
            raise
        return record

    @_portfolio_write
    def cancel_order(self, portfolio_id: str, order_id: str, command_id: str, idempotency_key: str, submitted_at_ms: int, approval: B41Approval) -> dict[str, Any]:
        cancel_fingerprint = _fingerprint({"portfolio_id": portfolio_id, "order_id": order_id, "command_id": command_id, "idempotency_key": idempotency_key, "submitted_at_ms": submitted_at_ms})
        existing = self._find_idempotency(idempotency_key, "order.cancelled")
        if existing is not None:
            if existing.get("command_fingerprint") != cancel_fingerprint:
                raise BrokerRejected("idempotency key conflicts with a different cancel command")
            return existing
        if portfolio_id != self.genesis.portfolio_id or approval.approver_id != "owner" or approval.command_fingerprint != cancel_fingerprint or approval.revoked or not approval.single_use or approval.issued_at_ms > submitted_at_ms or approval.expires_at_ms <= submitted_at_ms:
            raise BrokerRejected("cancel approval is invalid")
        if approval.approval_id in self._revoked_approval_ids or self._approval_used(approval.approval_id):
            raise BrokerRejected("approval is revoked or already used")
        for index, order in enumerate(self._orders):
            if order.order_id == order_id and order.state == "open":
                changed = B41Order(**{**order.to_dict(include_fingerprint=False), "state": "cancelled"})
                self._orders[index] = changed
                result = {"command_id": command_id, "idempotency_key": idempotency_key, "order_id": order_id, "state": "cancelled", "command_fingerprint": cancel_fingerprint}
                try:
                    self._append_event("order.cancelled", {"order_id": order_id, "approval": approval.to_dict()}, result)
                except Exception:
                    self._orders[index] = order
                    raise
                return result
        raise BrokerRejected("open order not found")

    @_portfolio_write
    def revoke_approval(self, approval_id: str, command_id: str, idempotency_key: str, revoked_at_ms: int, approver_id: str = "owner") -> dict[str, Any]:
        if approver_id != "owner" or (self._last_event_time_ms is not None and revoked_at_ms <= self._last_event_time_ms):
            raise BrokerRejected("approval revocation identity or event time is invalid")
        existing = self._find_idempotency(idempotency_key, "approval.revoked")
        command_fingerprint = _fingerprint({"approval_id": approval_id, "command_id": command_id, "idempotency_key": idempotency_key, "revoked_at_ms": revoked_at_ms})
        if existing is not None:
            if existing.get("command_fingerprint") == command_fingerprint:
                return existing
            raise BrokerRejected("idempotency key conflicts with a different revocation")
        if self._approval_used(approval_id):
            raise BrokerRejected("used approval cannot be revoked")
        result = {"approval_id": approval_id, "command_id": command_id, "idempotency_key": idempotency_key, "command_fingerprint": command_fingerprint, "state": "revoked"}
        self._revoked_approval_ids.append(approval_id)
        try:
            self._append_event("approval.revoked", {"approval_id": approval_id, "revoked_at_ms": revoked_at_ms, "approver_id": approver_id}, result)
        except Exception:
            self._revoked_approval_ids.remove(approval_id)
            raise
        return result

    def _approval_used(self, approval_id: str) -> bool:
        if not self.ledger_path.exists():
            return False
        for line in self.ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            approval = json.loads(line).get("payload", {}).get("approval")
            if approval and approval.get("approval_id") == approval_id:
                return True
        return False

    @_portfolio_write
    def process_market_event(self, event: SyntheticMarketEvent) -> dict[str, Any]:
        if event.symbol != self.genesis.symbol:
            raise BrokerRejected("market event symbol mismatch")
        if event.event_id in self._cursor:
            raise BrokerRejected("duplicate market event ID")
        if self._last_event_time_ms is not None and event.event_time_ms <= self._last_event_time_ms:
            raise BrokerRejected("market events must be strictly increasing")
        before = self._snapshot_payload()
        previous_equity = self._equity()
        try:
            self._mark = _q(_decimal(event.last, "last", positive=True), self.policy.price_quantum)
            if not self._equity_history:
                self._equity_history.append((event.event_time_ms, previous_equity))
            fills: list[dict[str, Any]] = []
            risk_rejections: list[dict[str, Any]] = []
            for index, order in enumerate(self._orders):
                if order.state != "open" or order.submitted_at_ms > event.event_time_ms:
                    continue
                if order.order_type == LIMIT and ((order.side == BUY and Decimal(str(event.ask)) > order.limit_price) or (order.side == SELL and Decimal(str(event.bid)) < order.limit_price)):
                    continue
                base = Decimal(str(event.ask if order.side == BUY else event.bid))
                slip = base * self.policy.slippage_bps_per_side / Decimal("10000")
                fill_price = _q(base + slip if order.side == BUY else base - slip, self.policy.price_quantum)
                if fill_price <= 0:
                    raise BrokerRejected("slippage produces a non-positive fill price")
                if order.order_type == LIMIT and ((order.side == BUY and fill_price > order.limit_price) or (order.side == SELL and fill_price < order.limit_price)):
                    continue
                notional = _q(fill_price * order.quantity, self.policy.price_quantum)
                fee = _q(notional * self.policy.fee_bps_per_side / Decimal("10000"), self.policy.price_quantum)
                midpoint = (Decimal(str(event.bid)) + Decimal(str(event.ask))) / Decimal("2")
                spread_cost = _q(midpoint * self.policy.spread_bps_per_side / Decimal("10000") * order.quantity, self.policy.price_quantum)
                if notional < self.policy.minimum_notional_usdt or notional > self.policy.max_order_notional_usdt:
                    below_minimum = notional < self.policy.minimum_notional_usdt
                    reason_code = "risk.minimum_notional" if below_minimum else "risk.max_order_notional"
                    reason = "fill notional is below the approved minimum" if below_minimum else "fill notional exceeds the approved maximum"
                    self._orders[index] = B41Order(**{**order.to_dict(include_fingerprint=False), "state": "risk_rejected"})
                    risk_rejections.append({
                        "order_id": order.order_id,
                        "command_id": order.command_id,
                        "event_id": event.event_id,
                        "reason_code": reason_code,
                        "reason": reason,
                        "notional": notional,
                    })
                    continue
                if order.side == BUY:
                    new_cash = self._cash - notional - fee
                    new_btc = self._btc + order.quantity
                    new_average = _q(((self._average * self._btc) + notional + fee) / new_btc, self.policy.price_quantum)
                    new_realized = self._realized
                else:
                    if order.quantity > self._btc:
                        raise BrokerRejected("insufficient BTC")
                    new_cash = self._cash + notional - fee
                    new_btc = self._btc - order.quantity
                    new_average = Decimal("0") if new_btc == 0 else self._average
                    new_realized = self._realized + (fill_price - self._average) * order.quantity - fee
                if new_cash < 0 or new_btc < 0:
                    raise BrokerRejected("negative cash or inventory")
                if new_btc > self.policy.max_inventory_btc:
                    raise BrokerRejected("maximum inventory limit")
                self._cash, self._btc, self._average, self._realized = new_cash, new_btc, new_average, new_realized
                self._fees += fee
                self._notional += notional
                self._orders[index] = B41Order(**{**order.to_dict(include_fingerprint=False), "state": "filled"})
                fills.append({"fill_id": _fingerprint({"order_id": order.order_id, "event_id": event.event_id})[:24], "order_id": order.order_id, "event_id": event.event_id, "quantity": order.quantity, "price": fill_price, "fee": fee, "spread_cost": spread_cost})
            equity = self._equity()
            cutoff = event.event_time_ms - self.policy.loss_window_ms
            self._equity_history = [(when, amount) for when, amount in self._equity_history if when >= cutoff]
            window_start = self._equity_history[0][1]
            window_peak = max(amount for _, amount in self._equity_history)
            if window_start - equity > self.policy.max_loss_usdt:
                raise BrokerRejected("maximum loss limit")
            if window_peak - equity > self.policy.max_drawdown_usdt:
                raise BrokerRejected("maximum drawdown limit")
            self._peak_equity = max(self._peak_equity, equity)
            self._equity_history.append((event.event_time_ms, equity))
            self._last_event_time_ms = event.event_time_ms
            self._fills.extend(fills)
            self._cursor.append(event.event_id)
            result = {"event_id": event.event_id, "fill_count": len(fills), "fills": fills, "risk_rejections": risk_rejections}
            self._append_event("market.processed", {"market_event": event.to_dict(), "result": result}, result)
            return self.snapshot()
        except Exception:
            self._restore_snapshot(before)
            raise

    def _equity(self) -> Decimal:
        return self._cash + self._mark * self._btc

    def _snapshot_payload(self) -> dict[str, Any]:
        return {"schema": SNAPSHOT_SCHEMA, "portfolio_id": self.genesis.portfolio_id, "cash_usdt": self._cash, "btc_quantity": self._btc, "average_entry_price": self._average, "realized_pnl_usdt": self._realized, "total_fees_usdt": self._fees, "total_notional_usdt": self._notional, "mark_price": self._mark, "peak_equity": self._peak_equity, "last_event_time_ms": self._last_event_time_ms, "equity_history": self._equity_history, "revoked_approval_ids": self._revoked_approval_ids, "open_orders": [order.to_dict() for order in self.open_orders], "orders": [order.to_dict() for order in self._orders], "fills": list(self._fills), "event_cursor": list(self._cursor)}

    def _restore_snapshot(self, snapshot: Mapping[str, Any]) -> None:
        for field in ("cash_usdt", "btc_quantity", "average_entry_price", "realized_pnl_usdt", "total_fees_usdt", "total_notional_usdt", "mark_price", "peak_equity"):
            _decimal(snapshot[field], field)
        last_event_time_ms = snapshot.get("last_event_time_ms")
        if last_event_time_ms is not None:
            _int(last_event_time_ms, "last_event_time_ms")
        equity_history = snapshot.get("equity_history", [])
        if not isinstance(equity_history, list):
            raise BrokerRejected("equity_history must be a list")
        for point in equity_history:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                raise BrokerRejected("equity_history point is malformed")
            _int(point[0], "equity_history timestamp")
            _decimal(point[1], "equity_history value")
        revoked_approval_ids = snapshot.get("revoked_approval_ids", [])
        if not isinstance(revoked_approval_ids, list) or any(not isinstance(item, str) for item in revoked_approval_ids):
            raise BrokerRejected("revoked approval IDs are malformed")
        orders = snapshot["orders"]
        fills = snapshot["fills"]
        cursor = snapshot["event_cursor"]
        if not isinstance(orders, list) or any(not isinstance(item, Mapping) for item in orders):
            raise BrokerRejected("orders are malformed")
        if not isinstance(fills, list) or any(not isinstance(item, Mapping) for item in fills):
            raise BrokerRejected("fills are malformed")
        if not isinstance(cursor, list) or any(not isinstance(item, str) for item in cursor):
            raise BrokerRejected("event cursor is malformed")
        self._cash = _as_decimal(snapshot["cash_usdt"])
        self._btc = _as_decimal(snapshot["btc_quantity"])
        self._average = _as_decimal(snapshot["average_entry_price"])
        self._realized = _as_decimal(snapshot["realized_pnl_usdt"])
        self._fees = _as_decimal(snapshot["total_fees_usdt"])
        self._notional = _as_decimal(snapshot["total_notional_usdt"])
        self._mark = _as_decimal(snapshot["mark_price"])
        self._peak_equity = _as_decimal(snapshot.get("peak_equity", self._equity()))
        self._last_event_time_ms = last_event_time_ms
        self._equity_history = [(int(when), _as_decimal(amount)) for when, amount in equity_history]
        self._revoked_approval_ids = list(revoked_approval_ids)
        self._orders = [B41Order(**{**item, "quantity": _as_decimal(item["quantity"]), "limit_price": _as_decimal(item["limit_price"]) if item.get("limit_price") is not None else None}) for item in orders]
        self._fills = [{**item, "quantity": _as_decimal(item["quantity"]), "price": _as_decimal(item["price"]), "fee": _as_decimal(item["fee"]), "spread_cost": _as_decimal(item.get("spread_cost", "0"))} for item in fills]
        self._cursor = list(cursor)

    def _find_idempotency(self, key: str, command_type: str | tuple[str, ...]) -> dict[str, Any] | None:
        command_types = (command_type,) if isinstance(command_type, str) else command_type
        for line in self.ledger_path.read_text(encoding="utf-8").splitlines() if self.ledger_path.exists() else ():
            if line.strip():
                record = json.loads(line)
                if record.get("kind") in command_types and record.get("idempotency_key") == key:
                    return record.get("result")
        return None

    def _ledger_head(self) -> str:
        if not self.ledger_path.exists():
            return "0" * 64
        lines = [line for line in self.ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return json.loads(lines[-1])["event_fingerprint"] if lines else "0" * 64

    def _append_event(self, kind: str, payload: dict[str, Any], result: dict[str, Any]) -> None:
        with self._lock:
            previous = "0" * 64
            sequence = 1
            if self.ledger_path.exists():
                lines = [line for line in self.ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                if lines:
                    last = json.loads(lines[-1])
                    previous = last["event_fingerprint"]
                    sequence = last["sequence"] + 1
            resulting_snapshot = self._snapshot_payload()
            record = {"schema": EVENT_SCHEMA, "sequence": sequence, "portfolio_id": self.genesis.portfolio_id, "kind": kind, "payload": payload, "result": result, "idempotency_key": result.get("idempotency_key"), "previous_event_fingerprint": previous, "resulting_snapshot_fingerprint": _fingerprint(resulting_snapshot), "resulting_snapshot": resulting_snapshot}
            record["event_fingerprint"] = _fingerprint(record)
            raw = (_canonical(record) + "\n").encode("utf-8")
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with self.ledger_path.open("ab") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
        self._snapshot_fingerprint = _fingerprint(self._snapshot_payload())
        self._last_ledger_fingerprint = record["event_fingerprint"]
        self._checkpoint_status = "current"
        try:
            self._atomic_write(self.checkpoint_path, {"schema": SNAPSHOT_SCHEMA + ".checkpoint", "sequence": sequence, "snapshot_fingerprint": self._snapshot_fingerprint, "snapshot": self._snapshot_payload()})
        except OSError:
            self._checkpoint_status = "stale_or_missing"

    @staticmethod
    def _atomic_write(path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(_canonical(value) + "\n", encoding="utf-8")
        with temp.open("r+b") as handle:
            os.fsync(handle.fileno())
        temp.replace(path)


__all__ = ["B41Policy", "B41Genesis", "B41Order", "B41Approval", "B41Broker", "BrokerRejected"]
