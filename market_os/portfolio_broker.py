"""Synthetic, paper-only B4.1 portfolio and virtual broker.

This module deliberately has no provider, network, credential, or live venue
path.  It persists an append-only JSONL ledger and derives state from the
approved synthetic policy and recorded market events.
"""
from __future__ import annotations

from collections import deque
from bisect import bisect_right
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_CEILING, InvalidOperation
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import stat
import threading
from contextlib import contextmanager
import re
from typing import Any, Mapping

from .paper_venue import BUY, LIMIT, MARKET, SELL, SyntheticMarketEvent


SCHEMA = "market-os.b4-1.paper-broker@v1"
GENESIS_SCHEMA = "market-os.b4-1.paper-portfolio-genesis@v1"
SHARED_GENESIS_SCHEMA = "market-os.b4-15.shared-portfolio-genesis@v1"
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


class BrokerStale(BrokerRejected):
    """A recovered broker changed before its read could be inspected."""


class InspectionCursorError(ValueError):
    """A page cursor does not identify a record in this portfolio."""


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


def _is_risk_record(record: Mapping[str, Any]) -> bool:
    kind = record.get("kind", "")
    if not isinstance(kind, str):
        return False
    result = record.get("result")
    has_risk_rejections = isinstance(result, Mapping) and bool(result.get("risk_rejections"))
    return kind.startswith("risk.") or kind in {
        "command.rejected",
        "order.rejected",
        "order.cancel.rejected",
        "command.idempotency_conflict",
    } or has_risk_rejections


def _is_approval_record(record: Mapping[str, Any]) -> bool:
    payload = record.get("payload")
    if not isinstance(payload, Mapping):
        return False
    kind = record.get("kind")
    return (
        "approval" in payload
        or kind in {"approval.revoked", "approval.revoke.rejected"}
        or (kind == "command.idempotency_conflict" and payload.get("command_type") == "approval.revoke")
    )


def _event_matches_item_id(resource: str, record: Mapping[str, Any], item_id: str) -> bool:
    if resource == "ledger":
        return str(record.get("sequence")) == item_id or record.get("event_fingerprint") == item_id
    payload = record.get("payload")
    payload = payload if isinstance(payload, Mapping) else {}
    result = record.get("result")
    result = result if isinstance(result, Mapping) else {}
    approval = payload.get("approval")
    approval = approval if isinstance(approval, Mapping) else {}
    revoke = payload.get("revoke")
    revoke = revoke if isinstance(revoke, Mapping) else {}
    attempt = payload.get("attempt")
    attempt = attempt if isinstance(attempt, Mapping) else {}
    return item_id in {
        approval.get("approval_id"),
        revoke.get("approval_id"),
        attempt.get("approval_id"),
        result.get("approval_id"),
        result.get("reason_code"),
    }


def _risk_record_reason_code(record: Mapping[str, Any]) -> str:
    result = record.get("result")
    if not isinstance(result, Mapping):
        return "recorded"
    reason_code = result.get("reason_code")
    if isinstance(reason_code, str) and reason_code:
        return reason_code
    rejections = result.get("risk_rejections")
    if isinstance(rejections, list):
        for rejection in rejections:
            if isinstance(rejection, Mapping):
                reason_code = rejection.get("reason_code")
                if isinstance(reason_code, str) and reason_code:
                    return reason_code
    return "recorded"


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 160 or any(ord(char) < 32 for char in value):
        raise BrokerRejected(f"{field} must be a bounded non-empty string")
    return value


def _identifier(value: Any, field: str) -> str:
    result = _text(value, field)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", result):
        raise BrokerRejected(f"{field} must be a stable identifier")
    return result


def _is_reparse_point(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    is_junction = getattr(path, "is_junction", None)
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return (
        stat.S_ISLNK(info.st_mode)
        or bool(getattr(info, "st_file_attributes", 0) & reparse_attribute)
        or (callable(is_junction) and is_junction())
    )


def _open_lock_file(path: Path, *, create: bool = True):
    """Open the local writer lock without following a link at its leaf."""
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    parent = path.parent
    if not create and not parent.is_dir():
        raise FileNotFoundError(path)
    if _is_reparse_point(parent) or parent.resolve(strict=True) != parent:
        raise BrokerRejected("portfolio lock directory must remain inside its store")

    flags = os.O_RDWR | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    parent_fd = None
    try:
        if os.name != "nt" and os.open in getattr(os, "supports_dir_fd", set()):
            parent_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
            parent_fd = os.open(parent, parent_flags)
            if create:
                try:
                    descriptor = os.open(path.name, flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=parent_fd)
                except (FileExistsError, FileNotFoundError):
                    if _is_reparse_point(path):
                        raise BrokerRejected("portfolio lock file must be local to its store")
                    if not path.exists():
                        raise
                    descriptor = os.open(path.name, flags, dir_fd=parent_fd)
            else:
                if _is_reparse_point(path):
                    raise BrokerRejected("portfolio lock file must be local to its store")
                descriptor = os.open(path.name, flags, dir_fd=parent_fd)
        else:
            if create:
                try:
                    descriptor = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
                except (FileExistsError, FileNotFoundError):
                    if _is_reparse_point(path):
                        raise BrokerRejected("portfolio lock file must be local to its store")
                    if not path.exists():
                        raise
                    descriptor = os.open(path, flags)
            else:
                if _is_reparse_point(path):
                    raise BrokerRejected("portfolio lock file must be local to its store")
                descriptor = os.open(path, flags)

        try:
            path_info = os.stat(path, follow_symlinks=False)
            file_info = os.fstat(descriptor)
            if (
                _is_reparse_point(path)
                or not stat.S_ISREG(file_info.st_mode)
                or (path_info.st_dev, path_info.st_ino) != (file_info.st_dev, file_info.st_ino)
            ):
                raise BrokerRejected("portfolio lock file must be local to its store")
        except Exception:
            os.close(descriptor)
            raise
        return os.fdopen(descriptor, "r+b")
    finally:
        if parent_fd is not None:
            os.close(parent_fd)


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
def _process_lock(path: Path, *, create: bool = True):
    """Lock one portfolio across threads and local processes."""
    # ponytail: serialize each local portfolio; use a transactional store if distributed writers are required.
    with _open_lock_file(path, create=create) as handle:
        if os.name == "nt":
            import msvcrt

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
        if getattr(self, "read_only", False):
            raise BrokerRejected("portfolio is read-only")
        with self._lock, self._process_guard():
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
    shared_portfolio_id: str | None = None
    member_strategy_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("strategy_id", "fixture_lineage", "symbol", "quote_asset", "base_asset"):
            _text(getattr(self, name), name)
        _identifier(self.portfolio_id, "portfolio_id")
        object.__setattr__(self, "initial_cash_usdt", _decimal(self.initial_cash_usdt, "initial_cash_usdt", nonnegative=True))
        object.__setattr__(self, "initial_btc_quantity", _decimal(self.initial_btc_quantity, "initial_btc_quantity", nonnegative=True))
        object.__setattr__(self, "initial_average_entry_price", _decimal(self.initial_average_entry_price, "initial_average_entry_price", nonnegative=True))
        if self.symbol != "BTCUSDT" or self.quote_asset != "USDT" or self.base_asset != "BTC":
            raise BrokerRejected("B4.1 is restricted to synthetic BTCUSDT Spot")
        expected_schema = SHARED_GENESIS_SCHEMA if self.shared_portfolio_id is not None else GENESIS_SCHEMA
        if self.synthetic_only is not True or self.schema != expected_schema:
            raise BrokerRejected("genesis must be synthetic-only and versioned")
        if not isinstance(self.member_strategy_ids, (tuple, list)):
            raise BrokerRejected("member strategy IDs must be a list")
        for item in self.member_strategy_ids:
            _identifier(item, "member_strategy_id")
        members = tuple(sorted(self.member_strategy_ids))
        if len(set(members)) != len(members):
            raise BrokerRejected("member strategy IDs must be unique")
        object.__setattr__(self, "member_strategy_ids", members)
        if self.shared_portfolio_id is None:
            identity = {"strategy_id": self.strategy_id, "symbol": self.symbol, "fixture_lineage": self.fixture_lineage}
            expected = "portfolio-" + _fingerprint(identity)[:24]
            if self.portfolio_id != expected:
                raise BrokerRejected("portfolio_id must match strategy, instrument, and fixture lineage")
            if members:
                raise BrokerRejected("isolated genesis cannot declare shared members")
        else:
            _identifier(self.shared_portfolio_id, "shared_portfolio_id")
            if len(members) < 2 or self.strategy_id != "shared":
                raise BrokerRejected("shared genesis requires at least two member strategies")
            identity = {"shared_portfolio_id": self.shared_portfolio_id, "symbol": self.symbol, "fixture_lineage": self.fixture_lineage, "member_strategy_ids": members}
            if self.portfolio_id != "portfolio-" + _fingerprint(identity)[:24]:
                raise BrokerRejected("portfolio_id must match shared membership identity")
        if self.initial_btc_quantity > 0 and self.initial_average_entry_price <= 0:
            raise BrokerRejected("initial BTC requires an explicit cost basis")
        if self.initial_btc_quantity == 0 and self.initial_average_entry_price != 0:
            raise BrokerRejected("initial cost basis requires initial BTC")

    @classmethod
    def create(cls, strategy_id: str, fixture_lineage: str, policy: B41Policy) -> "B41Genesis":
        identity = {"strategy_id": strategy_id, "symbol": "BTCUSDT", "fixture_lineage": fixture_lineage}
        portfolio_id = "portfolio-" + _fingerprint(identity)[:24]
        return cls(portfolio_id, strategy_id, fixture_lineage, policy_fingerprint=policy.fingerprint, initial_cash_usdt=policy.initial_cash_usdt, initial_btc_quantity=policy.initial_btc_quantity, initial_average_entry_price=policy.initial_average_entry_price)

    @classmethod
    def create_shared(cls, shared_portfolio_id: str, fixture_lineage: str, member_strategy_ids: tuple[str, ...] | list[str], policy: B41Policy) -> "B41Genesis":
        if not isinstance(member_strategy_ids, (tuple, list)):
            raise BrokerRejected("member strategy IDs must be a list")
        for item in member_strategy_ids:
            _identifier(item, "member_strategy_id")
        members = tuple(sorted(member_strategy_ids))
        identity = {"shared_portfolio_id": shared_portfolio_id, "symbol": "BTCUSDT", "fixture_lineage": fixture_lineage, "member_strategy_ids": members}
        portfolio_id = "portfolio-" + _fingerprint(identity)[:24]
        return cls(portfolio_id, "shared", fixture_lineage, policy_fingerprint=policy.fingerprint, initial_cash_usdt=policy.initial_cash_usdt, initial_btc_quantity=policy.initial_btc_quantity, initial_average_entry_price=policy.initial_average_entry_price, schema=SHARED_GENESIS_SCHEMA, shared_portfolio_id=shared_portfolio_id, member_strategy_ids=members)

    def bind_policy(self, policy: B41Policy) -> None:
        if self.policy_fingerprint != policy.fingerprint:
            raise BrokerRejected("genesis policy fingerprint mismatch")
        if (self.initial_cash_usdt, self.initial_btc_quantity, self.initial_average_entry_price) != (policy.initial_cash_usdt, policy.initial_btc_quantity, policy.initial_average_entry_price):
            raise BrokerRejected("genesis wallet does not match pinned policy")

    def to_dict(self, *, include_member_strategy_ids: bool = True) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in ("portfolio_id", "strategy_id", "fixture_lineage", "symbol", "quote_asset", "base_asset", "policy_fingerprint", "initial_cash_usdt", "initial_btc_quantity", "initial_average_entry_price", "synthetic_only", "schema")}
        if self.shared_portfolio_id is not None:
            result["shared_portfolio_id"] = self.shared_portfolio_id
            if include_member_strategy_ids:
                result["member_strategy_ids"] = list(self.member_strategy_ids)
        return result


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
    strategy_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("portfolio_id", "order_id", "command_id", "idempotency_key"):
            _text(getattr(self, name), name)
        if self.strategy_id is not None:
            _identifier(self.strategy_id, "strategy_id")
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
        if self.strategy_id is not None:
            result["strategy_id"] = self.strategy_id
        result["state"] = self.state
        if include_fingerprint:
            result["command_fingerprint"] = self.command_fingerprint
        return result

    def _command_projection(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in ("portfolio_id", "order_id", "command_id", "idempotency_key", "side", "order_type", "quantity", "limit_price", "submitted_at_ms")}
        if self.strategy_id is not None:
            result["strategy_id"] = self.strategy_id
        return result


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
        directory = Path(root).resolve() / genesis.portfolio_id
        self.read_only = False
        with _LOCKS_GUARD:
            lock = _LOCKS.setdefault(str(directory), threading.RLock())
        with lock, _process_lock(directory / ".writer.lock"):
            self._initialize(root, genesis, policy)

    def _initialize(self, root: str | Path, genesis: B41Genesis, policy: B41Policy) -> None:
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
        genesis.bind_policy(policy)
        if self.genesis_path.exists():
            try:
                stored = B41Genesis(**_read_json_object(self.genesis_path, "genesis"))
            except (TypeError, ValueError, KeyError) as exc:
                raise BrokerRejected("genesis is malformed") from exc
            if stored.to_dict() != genesis.to_dict():
                raise BrokerRejected("portfolio genesis identity conflict")
        else:
            self._atomic_write(self.genesis_path, genesis.to_dict())
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
        self._checkpoint_status = "stale_or_missing"
        self._last_ledger_fingerprint = self._ledger_head()
        if self._last_ledger_fingerprint != "0" * 64:
            recovered = self._recover_locked(root, genesis.portfolio_id, policy)
            self.__dict__.update(recovered.__dict__)

    @classmethod
    def recover(cls, root: str | Path, portfolio_id: str, policy: B41Policy) -> "B41Broker":
        _identifier(portfolio_id, "portfolio_id")
        store_root, directory = cls._store_directory(root, portfolio_id)
        genesis_path = directory / "genesis.json"
        if _is_reparse_point(genesis_path):
            raise BrokerRejected("portfolio genesis must be a local file")
        if not genesis_path.exists():
            raise BrokerRejected("missing portfolio genesis")
        with _LOCKS_GUARD:
            lock = _LOCKS.setdefault(str(directory), threading.RLock())
        with lock, _process_lock(directory / ".writer.lock"):
            return cls._recover_locked(store_root, portfolio_id, policy, portfolio_directory=directory)

    @classmethod
    def _store_directory(cls, root: str | Path, portfolio_id: str) -> tuple[Path, Path]:
        store_root = Path(root).resolve()
        directory = store_root / portfolio_id
        if directory.parent != store_root or _is_reparse_point(directory):
            raise BrokerRejected("portfolio directory must remain inside its store")
        if directory.exists():
            directory = directory.resolve(strict=True)
            if directory.parent != store_root:
                raise BrokerRejected("portfolio directory must remain inside its store")
        return store_root, directory

    @classmethod
    def _recover_locked(
        cls,
        root: str | Path,
        portfolio_id: str,
        policy: B41Policy,
        *,
        portfolio_directory: Path | None = None,
    ) -> "B41Broker":
        directory = portfolio_directory or (Path(root).resolve() / portfolio_id)
        for name in ("genesis.json", "policy.json", "ledger.jsonl", "checkpoint.json"):
            path = directory / name
            if _is_reparse_point(path):
                raise BrokerRejected(f"portfolio {name} must be a local file")
            if path.exists() and path.resolve(strict=True).parent != directory:
                raise BrokerRejected(f"portfolio {name} must remain inside its store")
        genesis_path = directory / "genesis.json"
        if not genesis_path.exists():
            raise BrokerRejected("missing portfolio genesis")
        try:
            genesis = B41Genesis(**_read_json_object(genesis_path, "genesis"))
        except (TypeError, ValueError, KeyError) as exc:
            raise BrokerRejected("genesis is malformed") from exc
        if genesis.portfolio_id != portfolio_id:
            raise BrokerRejected("genesis portfolio identity mismatch")
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
        broker.read_only = False
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
        broker._checkpoint_status = "stale_or_missing"
        previous = "0" * 64
        command_idempotency: set[tuple[str, str]] = set()
        verified_snapshots: dict[int, Mapping[str, Any]] = {}
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
                kind = record.get("kind")
                if kind in {"order.accepted", "order.rejected"}:
                    kind = "order.submit"
                elif kind in {"order.cancelled", "order.cancel.rejected"}:
                    kind = "order.cancel"
                elif kind in {"approval.revoked", "approval.revoke.rejected"}:
                    kind = "approval.revoke"
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
            broker._validate_shared_state()
            if len(broker._cursor) != len(set(broker._cursor)):
                raise BrokerRejected("ledger contains duplicate market event IDs")
            previous = record["event_fingerprint"]
            verified_snapshots[expected_sequence] = resulting_snapshot
        broker._snapshot_fingerprint = _fingerprint(broker._snapshot_payload())
        broker._last_ledger_fingerprint = previous
        if broker.checkpoint_path.exists() and not broker.ledger_path.exists():
            raise BrokerRejected("checkpoint exists without portfolio ledger")
        if broker.ledger_path.exists() and broker.checkpoint_path.exists():
            checkpoint = _read_json_object(broker.checkpoint_path, "checkpoint")
            if checkpoint.get("schema") != SNAPSHOT_SCHEMA + ".checkpoint":
                raise BrokerRejected("checkpoint schema mismatch")
            checkpoint_sequence = checkpoint.get("sequence")
            if not isinstance(checkpoint_sequence, int) or isinstance(checkpoint_sequence, bool) or checkpoint_sequence not in verified_snapshots:
                raise BrokerRejected("checkpoint sequence mismatch")
            checkpoint_snapshot = checkpoint.get("snapshot")
            if not isinstance(checkpoint_snapshot, Mapping) or checkpoint_snapshot.get("schema") != SNAPSHOT_SCHEMA or checkpoint_snapshot.get("portfolio_id") != genesis.portfolio_id:
                raise BrokerRejected("checkpoint snapshot identity mismatch")
            if checkpoint.get("snapshot_fingerprint") != _fingerprint(checkpoint_snapshot):
                raise BrokerRejected("checkpoint snapshot fingerprint mismatch")
            verified_snapshot = verified_snapshots[checkpoint_sequence]
            if _canonical(checkpoint_snapshot) != _canonical(verified_snapshot):
                raise BrokerRejected("checkpoint fingerprint mismatch")
            broker._checkpoint_status = "current" if checkpoint_sequence == len(verified_snapshots) else "stale_or_missing"
        else:
            broker._checkpoint_status = "stale_or_missing"
        return broker

    @classmethod
    def open(cls, root: str | Path, portfolio_id: str, *, read_only: bool = False) -> "B41Broker":
        _identifier(portfolio_id, "portfolio_id")
        store_root, directory = cls._store_directory(root, portfolio_id)
        policy_path = directory / "policy.json"
        if _is_reparse_point(policy_path):
            raise BrokerRejected("portfolio policy must be a local file")
        if not policy_path.is_file():
            raise BrokerRejected("missing portfolio policy")
        if policy_path.resolve(strict=True).parent != directory:
            raise BrokerRejected("portfolio policy must remain inside its store")
        with _LOCKS_GUARD:
            lock = _LOCKS.setdefault(str(directory), threading.RLock())
        with lock, _process_lock(directory / ".writer.lock", create=not read_only):
            policy_path = directory / "policy.json"
            if _is_reparse_point(policy_path) or not policy_path.is_file():
                raise BrokerRejected("missing portfolio policy")
            if policy_path.resolve(strict=True).parent != directory:
                raise BrokerRejected("portfolio policy must remain inside its store")
            broker = cls._recover_locked(
                store_root,
                portfolio_id,
                B41Policy.from_dict(_read_json_object(policy_path, "policy")),
                portfolio_directory=directory,
            )
            broker.read_only = read_only
            return broker

    def _process_guard(self):
        return _process_lock(self.lock_path, create=not self.read_only)

    @property
    def open_orders(self) -> tuple[B41Order, ...]:
        return tuple(order for order in self._orders if order.state == "open")

    def _cash_reservation(self, order: B41Order) -> Decimal:
        notional = order.quantity * order.limit_price if order.order_type == LIMIT else self.policy.max_order_notional_usdt
        if self.genesis.shared_portfolio_id is None:
            return notional * (Decimal("1") + self.policy.fee_bps_per_side / Decimal("10000"))
        notional = notional.quantize(self.policy.price_quantum, rounding=ROUND_CEILING)
        fee = (notional * self.policy.fee_bps_per_side / Decimal("10000")).quantize(self.policy.price_quantum, rounding=ROUND_CEILING)
        return notional + fee

    def _reservations(self) -> dict[str, Any]:
        rows = []
        for order in self.open_orders:
            rows.append({"order_id": order.order_id, "strategy_id": order.strategy_id or self.genesis.strategy_id,
                         "cash_usdt": self._cash_reservation(order) if order.side == BUY else Decimal("0"),
                         "btc_quantity": order.quantity if order.side == SELL else Decimal("0"),
                         "buy_quantity": order.quantity if order.side == BUY else Decimal("0")})
        return {"portfolio_id": self.genesis.portfolio_id, "reservations": rows,
                "cash_usdt": sum((row["cash_usdt"] for row in rows), Decimal("0")),
                "btc_quantity": sum((row["btc_quantity"] for row in rows), Decimal("0")),
                "buy_quantity": sum((row["buy_quantity"] for row in rows), Decimal("0"))}

    def _validate_shared_state(self) -> None:
        if self.genesis.shared_portfolio_id is None:
            return
        if self._cash < 0 or self._btc < 0:
            raise BrokerRejected("shared wallet invariant is invalid")
        if any(order.portfolio_id != self.genesis.portfolio_id or order.strategy_id not in self.genesis.member_strategy_ids for order in self._orders):
            raise BrokerRejected("shared order membership is invalid")
        if len({order.order_id for order in self._orders}) != len(self._orders):
            raise BrokerRejected("shared order identity is duplicated")
        orders = {order.order_id: order for order in self._orders}
        if any(fill.get("order_id") not in orders or fill.get("strategy_id") != orders[fill["order_id"]].strategy_id for fill in self._fills):
            raise BrokerRejected("shared fill membership is invalid")
        reserved = self._reservations()
        if self._cash < reserved["cash_usdt"] or self._btc < reserved["btc_quantity"] or self._btc + reserved["buy_quantity"] > self.policy.max_inventory_btc:
            raise BrokerRejected("shared reservation invariant is invalid")

    @property
    def snapshot_fingerprint(self) -> str:
        return self._snapshot_fingerprint

    def snapshot(self) -> dict[str, Any]:
        return self._snapshot_payload()

    def export_backup_files(self) -> dict[str, bytes]:
        """Read a consistent, validated copy of the persisted portfolio files."""
        with self._lock, self._process_guard():
            if self._ledger_head() != self._last_ledger_fingerprint:
                raise BrokerRejected("stale portfolio snapshot; reload before backup")
            return {
                name: path.read_bytes()
                for name, path in (
                    ("genesis.json", self.genesis_path),
                    ("policy.json", self.policy_path),
                    ("ledger.jsonl", self.ledger_path),
                    ("checkpoint.json", self.checkpoint_path),
                )
                if path.is_file()
            }

    def inspect(self, resource: str, item_id: str | None = None) -> dict[str, Any]:
        with self._lock, self._process_guard():
            if self._ledger_head() != self._last_ledger_fingerprint:
                raise BrokerRejected("stale portfolio snapshot; reload before inspection")
            return self._inspect_locked(resource, item_id)

    def _inspect_locked(self, resource: str, item_id: str | None = None) -> dict[str, Any]:
        if resource not in {"summary", "snapshot", "orders", "fills", "ledger", "risk", "approvals", "fingerprints", "replay", "policy", "genesis", "reservations"}:
            raise KeyError(resource)
        if resource == "reservations":
            return self._reservations()
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
            selected = [record for record in records if _is_risk_record(record)]
            if resource == "approvals":
                selected = [record for record in records if _is_approval_record(record)]
            if item_id is not None:
                selected = [record for record in selected if _event_matches_item_id(resource, record, item_id)]
            return {"portfolio_id": self.genesis.portfolio_id, "records": selected}
        if resource == "fingerprints":
            return {"portfolio_id": self.genesis.portfolio_id, "snapshot_fingerprint": self.snapshot_fingerprint, "ledger_head": self._ledger_head(), "policy_fingerprint": self.policy.fingerprint}
        snapshot = self.snapshot()
        if resource == "summary":
            return {
                key: snapshot[key]
                for key in ("schema", "portfolio_id", "cash_usdt", "btc_quantity", "mark_price", "realized_pnl_usdt", "total_fees_usdt", "event_cursor")
            } | {"open_orders": len(self.open_orders)}
        if resource == "orders":
            rows = snapshot["orders"]
            return {"portfolio_id": self.genesis.portfolio_id, "orders": [row for row in rows if item_id is None or row["order_id"] == item_id]}
        if resource == "fills":
            rows = snapshot["fills"]
            return {"portfolio_id": self.genesis.portfolio_id, "fills": [row for row in rows if item_id is None or row["fill_id"] == item_id]}
        if resource == "replay":
            return {"portfolio_id": self.genesis.portfolio_id, "snapshot_fingerprint": self.snapshot_fingerprint, "ledger_head": self._ledger_head(), "event_count": len(self._cursor), "recovery": "verified", "checkpoint": "verified" if getattr(self, "_checkpoint_status", "stale_or_missing") == "current" else "stale_or_missing"}
        return snapshot

    def inspect_summary_compact(self) -> dict[str, Any]:
        with self._lock, self._process_guard():
            if self._ledger_head() != self._last_ledger_fingerprint:
                raise BrokerStale("stale portfolio snapshot; reload before inspection")
            return {
                "portfolio_id": self.genesis.portfolio_id,
                "cash_usdt": str(self._cash),
                "btc_quantity": str(self._btc),
                "mark_price": str(self._mark),
                "realized_pnl_usdt": str(self._realized),
                "total_fees_usdt": str(self._fees),
                "market_event_count": len(self._cursor),
                "open_orders": sum(order.state == "open" for order in self._orders),
            }

    def inspect_equity_history_page(self, limit: int = 100) -> dict[str, Any]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("equity history page limit must be an integer between 1 and 100")

        with self._lock, self._process_guard():
            if self._ledger_head() != self._last_ledger_fingerprint:
                raise BrokerStale("stale portfolio snapshot; reload before inspection")
            selected = self._equity_history[-limit:]
            if any(selected[index - 1][0] > selected[index][0] for index in range(1, len(selected))):
                raise BrokerRejected("equity history is not in event-time order")
            values = [amount for _, amount in selected]
            total_count = len(self._equity_history)
            return {
                "portfolio_id": self.genesis.portfolio_id,
                "points": [
                    {"event_time_ms": event_time_ms, "equity_usdt": str(amount)}
                    for event_time_ms, amount in selected
                ],
                "minimum_equity_usdt": str(min(values)) if values else None,
                "maximum_equity_usdt": str(max(values)) if values else None,
                "page": {
                    "limit": limit,
                    "returned_count": len(selected),
                    "total_count": total_count,
                    "has_more": total_count > len(selected),
                    "scope": "latest",
                },
            }

    def inspect_genesis_compact(self) -> dict[str, Any]:
        with self._lock, self._process_guard():
            if self._ledger_head() != self._last_ledger_fingerprint:
                raise BrokerStale("stale portfolio snapshot; reload before inspection")
            return json.loads(_canonical(self.genesis.to_dict(include_member_strategy_ids=False)))

    def inspect_members_page(self, limit: int = 25, after_strategy_id: str | None = None) -> dict[str, Any]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("member page limit must be an integer between 1 and 100")
        if after_strategy_id is not None and (
            not isinstance(after_strategy_id, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", after_strategy_id)
        ):
            raise ValueError("member page cursor must be a stable strategy ID")

        with self._lock, self._process_guard():
            if self._ledger_head() != self._last_ledger_fingerprint:
                raise BrokerRejected("stale portfolio snapshot; reload before inspection")
            strategy_ids = self.genesis.member_strategy_ids or (self.genesis.strategy_id,)
            start = 0
            if after_strategy_id is not None:
                start = bisect_right(strategy_ids, after_strategy_id)
                if start == 0 or strategy_ids[start - 1] != after_strategy_id:
                    raise InspectionCursorError("member page cursor is not in this portfolio")
            window = strategy_ids[start:start + limit + 1]
            has_more = len(window) > limit
            selected = window[:limit]
            return {
                "api_version": "market-os.b4-member-page@v1",
                "portfolio_id": self.genesis.portfolio_id,
                "strategy_ids": list(selected),
                "page": {
                    "limit": limit,
                    "after_strategy_id": after_strategy_id,
                    "has_more": has_more,
                    "next_after_strategy_id": selected[-1] if has_more else None,
                    "total_count": len(strategy_ids),
                },
            }

    def inspect_reservations_page(self, limit: int = 25, before_order_id: str | None = None) -> dict[str, Any]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("reservation page limit must be an integer between 1 and 100")
        if before_order_id is not None and (
            not isinstance(before_order_id, str)
            or not before_order_id
            or len(before_order_id) > 160
            or any(ord(character) < 32 for character in before_order_id)
        ):
            raise ValueError("reservation page cursor must be a bounded order ID")

        with self._lock, self._process_guard():
            if self._ledger_head() != self._last_ledger_fingerprint:
                raise BrokerRejected("stale portfolio snapshot; reload before inspection")
            recent: deque[dict[str, str]] = deque(maxlen=limit + 1)
            cash_usdt = Decimal("0")
            btc_quantity = Decimal("0")
            buy_quantity = Decimal("0")
            total_count = 0
            cursor_found = before_order_id is None
            collect_rows = True
            for order in self._orders:
                if order.state != "open":
                    continue
                total_count += 1
                row = {
                    "order_id": order.order_id,
                    "strategy_id": order.strategy_id or self.genesis.strategy_id,
                    "cash_usdt": str(self._cash_reservation(order) if order.side == BUY else Decimal("0")),
                    "btc_quantity": str(order.quantity if order.side == SELL else Decimal("0")),
                    "buy_quantity": str(order.quantity if order.side == BUY else Decimal("0")),
                }
                cash_usdt += Decimal(row["cash_usdt"])
                btc_quantity += Decimal(row["btc_quantity"])
                buy_quantity += Decimal(row["buy_quantity"])
                if before_order_id is not None and order.order_id == before_order_id:
                    cursor_found = True
                    collect_rows = False
                    continue
                if collect_rows:
                    recent.append(row)

            if not cursor_found:
                raise InspectionCursorError("reservation page cursor is not an open order in this portfolio")
            has_more = len(recent) > limit
            selected = list(recent)
            if has_more:
                selected = selected[-limit:]
            selected.reverse()
            return {
                "api_version": "market-os.b4-reservation-page@v1",
                "portfolio_id": self.genesis.portfolio_id,
                "reservations": selected,
                "cash_usdt": str(cash_usdt),
                "btc_quantity": str(btc_quantity),
                "buy_quantity": str(buy_quantity),
                "page": {
                    "limit": limit,
                    "before_order_id": before_order_id,
                    "has_more": has_more,
                    "next_before_order_id": selected[-1]["order_id"] if has_more else None,
                    "total_count": total_count,
                },
            }

    def inspect_orders_page(self, limit: int = 25, before_order_id: str | None = None) -> dict[str, Any]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("order page limit must be an integer between 1 and 100")
        if before_order_id is not None and (
            not isinstance(before_order_id, str)
            or not before_order_id
            or len(before_order_id) > 160
            or any(ord(character) < 32 for character in before_order_id)
        ):
            raise ValueError("order page cursor must be a bounded order ID")

        with self._lock, self._process_guard():
            if self._ledger_head() != self._last_ledger_fingerprint:
                raise BrokerRejected("stale portfolio snapshot; reload before inspection")
            end = len(self._orders)
            if before_order_id is not None:
                cursor_index = next(
                    (index for index, order in enumerate(self._orders) if order.order_id == before_order_id),
                    None,
                )
                if cursor_index is None:
                    raise InspectionCursorError("order page cursor is not in this portfolio")
                end = cursor_index
            start = max(0, end - limit - 1)
            window = self._orders[start:end]
            has_more = start > 0 or len(window) > limit
            selected = window[-limit:]
            next_before_order_id = selected[0].order_id if has_more else None
            selected.reverse()
            orders = [
                {
                    "order_id": order.order_id,
                    "strategy_id": order.strategy_id or self.genesis.strategy_id,
                    "side": order.side,
                    "order_type": order.order_type,
                    "quantity": str(order.quantity),
                    "limit_price": str(order.limit_price) if order.limit_price is not None else None,
                    "state": order.state,
                }
                for order in selected
            ]
            return {
                "api_version": "market-os.b4-order-page@v1",
                "portfolio_id": self.genesis.portfolio_id,
                "orders": orders,
                "page": {
                    "limit": limit,
                    "before_order_id": before_order_id,
                    "has_more": has_more,
                    "next_before_order_id": next_before_order_id,
                },
            }

    def inspect_risk_page(self, limit: int = 25, before_sequence: int | None = None) -> dict[str, Any]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("risk page limit must be an integer between 1 and 100")
        if before_sequence is not None and (
            isinstance(before_sequence, bool)
            or not isinstance(before_sequence, int)
            or before_sequence < 1
        ):
            raise ValueError("risk page cursor must be a positive integer")

        with self._lock, self._process_guard():
            recent: deque[dict[str, Any]] = deque(maxlen=limit + 1)
            cursor_found = before_sequence is None
            ledger_head = "0" * 64
            if self.ledger_path.exists():
                with self.ledger_path.open("r", encoding="utf-8") as ledger:
                    for line in ledger:
                        if not line.strip():
                            continue
                        record = json.loads(line)
                        if not isinstance(record, dict):
                            raise BrokerRejected("risk audit record is malformed")
                        ledger_head = record.get("event_fingerprint")
                        sequence = record.get("sequence")
                        is_risk = _is_risk_record(record)
                        if before_sequence is not None and sequence == before_sequence and is_risk:
                            cursor_found = True
                        if before_sequence is not None and sequence >= before_sequence:
                            continue
                        if is_risk:
                            recent.append(record)

            if ledger_head != self._last_ledger_fingerprint:
                raise BrokerStale("stale portfolio snapshot; reload before inspection")
            if before_sequence is not None and not cursor_found:
                raise InspectionCursorError("risk page cursor is not in this portfolio")
            has_more = len(recent) > limit
            selected = list(recent)
            if has_more:
                selected = selected[-limit:]
            next_before_sequence = str(selected[0]["sequence"]) if has_more else None
            selected.reverse()
            records = [
                {
                    "sequence": str(record["sequence"]),
                    "kind": record["kind"],
                    "reason_code": _risk_record_reason_code(record),
                }
                for record in selected
            ]
            return {
                "api_version": "market-os.b4-risk-page@v1",
                "portfolio_id": self.genesis.portfolio_id,
                "records": records,
                "page": {
                    "limit": limit,
                    "before_sequence": str(before_sequence) if before_sequence is not None else None,
                    "has_more": has_more,
                    "next_before_sequence": next_before_sequence,
                },
            }

    def inspect_event_page(
        self,
        resource: str,
        limit: int = 25,
        before_sequence: int | None = None,
        item_id: str | None = None,
    ) -> dict[str, Any]:
        if resource not in {"ledger", "risk", "approvals"}:
            raise ValueError("event page resource must be ledger, risk, or approvals")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("event page limit must be an integer between 1 and 100")
        if before_sequence is not None and (
            isinstance(before_sequence, bool)
            or not isinstance(before_sequence, int)
            or before_sequence < 1
        ):
            raise ValueError("event page cursor must be a positive integer")
        if item_id is not None and (
            not isinstance(item_id, str)
            or not item_id
            or len(item_id) > 160
            or any(ord(character) < 32 for character in item_id)
        ):
            raise ValueError("event page item ID must be a bounded non-empty string")

        with self._lock, self._process_guard():
            recent: deque[dict[str, Any]] = deque(maxlen=limit + 1)
            cursor_found = before_sequence is None
            total_count = 0
            ledger_head = "0" * 64
            if self.ledger_path.exists():
                with self.ledger_path.open("r", encoding="utf-8") as ledger:
                    for line in ledger:
                        if not line.strip():
                            continue
                        record = json.loads(line)
                        if not isinstance(record, dict):
                            raise BrokerRejected("ledger inspection record is malformed")
                        ledger_head = record.get("event_fingerprint")
                        sequence = record.get("sequence")
                        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
                            raise BrokerRejected("ledger inspection sequence is malformed")
                        matches = (
                            resource == "ledger"
                            or (resource == "risk" and _is_risk_record(record))
                            or (resource == "approvals" and _is_approval_record(record))
                        )
                        if not matches:
                            continue
                        if item_id is not None and not _event_matches_item_id(resource, record, item_id):
                            continue
                        total_count += 1
                        if before_sequence is not None and sequence == before_sequence:
                            cursor_found = True
                        if before_sequence is None or sequence < before_sequence:
                            recent.append(record)

            if ledger_head != self._last_ledger_fingerprint:
                raise BrokerStale("stale portfolio snapshot; reload before inspection")
            if before_sequence is not None and not cursor_found:
                raise InspectionCursorError(f"{resource} page cursor is not in this portfolio")
            has_more = len(recent) > limit
            selected = list(recent)
            if has_more:
                selected = selected[-limit:]
            selected.reverse()
            return {
                "portfolio_id": self.genesis.portfolio_id,
                "events" if resource == "ledger" else "records": selected,
                "page": {
                    "limit": limit,
                    "before_sequence": str(before_sequence) if before_sequence is not None else None,
                    "has_more": has_more,
                    "next_before_sequence": str(selected[-1]["sequence"]) if has_more else None,
                    "total_count": total_count,
                },
            }

    def inspect_fills_page(self, limit: int = 25, before_fill_id: str | None = None) -> dict[str, Any]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("fill page limit must be an integer between 1 and 100")
        if before_fill_id is not None and (
            not isinstance(before_fill_id, str)
            or not before_fill_id
            or len(before_fill_id) > 160
            or any(ord(character) < 32 for character in before_fill_id)
        ):
            raise ValueError("fill page cursor must be a bounded fill ID")

        with self._lock, self._process_guard():
            if self._ledger_head() != self._last_ledger_fingerprint:
                raise BrokerRejected("stale portfolio snapshot; reload before inspection")
            end = len(self._fills)
            if before_fill_id is not None:
                cursor_index = next(
                    (index for index, fill in enumerate(self._fills) if fill.get("fill_id") == before_fill_id),
                    None,
                )
                if cursor_index is None:
                    raise InspectionCursorError("fill page cursor is not in this portfolio")
                end = cursor_index
            start = max(0, end - limit - 1)
            window = self._fills[start:end]
            has_more = start > 0 or len(window) > limit
            selected = list(window[-limit:])
            selected.reverse()
            return {
                "portfolio_id": self.genesis.portfolio_id,
                "fills": json.loads(_canonical(selected)),
                "page": {
                    "limit": limit,
                    "before_fill_id": before_fill_id,
                    "has_more": has_more,
                    "next_before_fill_id": selected[-1]["fill_id"] if has_more else None,
                    "total_count": len(self._fills),
                },
            }

    def inspect_item_jsonable(self, resource: str, item_id: str) -> dict[str, Any]:
        if resource not in {"orders", "fills"}:
            raise ValueError("item inspection supports orders or fills")
        if not isinstance(item_id, str) or not item_id or len(item_id) > 160 or any(ord(character) < 32 for character in item_id):
            raise ValueError("item ID must be a bounded non-empty string")
        with self._lock, self._process_guard():
            if self._ledger_head() != self._last_ledger_fingerprint:
                raise BrokerRejected("stale portfolio snapshot; reload before inspection")
            if resource == "orders":
                rows = [order.to_dict() for order in self._orders if order.order_id == item_id]
            else:
                rows = [fill for fill in self._fills if fill.get("fill_id") == item_id]
            return json.loads(_canonical({"portfolio_id": self.genesis.portfolio_id, resource: rows}))

    def inspect_jsonable(self, resource: str, item_id: str | None = None) -> dict[str, Any]:
        return json.loads(_canonical(self.inspect(resource, item_id)))

    def _record_command_rejection(self, kind: str, payload: dict[str, Any], identity: dict[str, Any], error: BrokerRejected) -> dict[str, Any]:
        result = {**identity, "state": "rejected", "reason_code": error.reason_code, "reason": str(error)}
        self._append_event(kind, payload | {"reason_code": error.reason_code}, result)
        return result

    def _record_idempotency_conflict(self, command_type: str, idempotency_key: str, fingerprint: str, attempt: dict[str, Any]) -> BrokerRejected:
        error = BrokerRejected("idempotency key conflicts with a different command", "command.idempotency_conflict")
        result = {"command_type": command_type, "conflicting_idempotency_key": idempotency_key, "attempted_command_fingerprint": fingerprint, "state": "rejected", "reason_code": error.reason_code, "reason": str(error)}
        self._append_event("command.idempotency_conflict", {"command_type": command_type, "idempotency_key": idempotency_key, "attempted_command_fingerprint": fingerprint, "attempt": attempt}, result)
        return error

    @_portfolio_write
    def submit_order(self, order: B41Order, approval: B41Approval) -> dict[str, Any]:
        existing = self._find_idempotency(order.idempotency_key, ("order.accepted", "order.rejected"))
        if existing is not None:
            if existing["command_fingerprint"] == order.command_fingerprint:
                return existing
            raise self._record_idempotency_conflict("order.submit", order.idempotency_key, order.command_fingerprint, {"order": order.to_dict(), "approval": approval.to_dict()})
        try:
            if self._last_event_time_ms is not None and order.submitted_at_ms <= self._last_event_time_ms:
                raise BrokerRejected("order cannot backdate into a processed market event", "order.backdated")
            if order.portfolio_id != self.genesis.portfolio_id:
                raise BrokerRejected("portfolio identity mismatch", "command.portfolio_mismatch")
            if self.genesis.shared_portfolio_id is not None:
                if order.strategy_id not in self.genesis.member_strategy_ids:
                    raise BrokerRejected("strategy is not a portfolio member", "membership.not_member")
            elif order.strategy_id is not None and order.strategy_id != self.genesis.strategy_id:
                raise BrokerRejected("strategy is not a portfolio member", "membership.not_member")
            if approval.approver_id != "owner":
                raise BrokerRejected("approver identity is not authorized", "approval.unauthorized")
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
                order_reserve = self._cash_reservation(order)
                existing_reserve = sum((self._cash_reservation(candidate) for candidate in self.open_orders if candidate.side == BUY), Decimal("0"))
                if existing_reserve + order_reserve > self._cash:
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
    def cancel_order(self, portfolio_id: str, order_id: str, command_id: str, idempotency_key: str, submitted_at_ms: int, approval: B41Approval, strategy_id: str | None = None) -> dict[str, Any]:
        cancel_projection = {"portfolio_id": portfolio_id, "order_id": order_id, "command_id": command_id, "idempotency_key": idempotency_key, "submitted_at_ms": submitted_at_ms}
        if strategy_id is not None:
            cancel_projection["strategy_id"] = strategy_id
        cancel_fingerprint = _fingerprint(cancel_projection)
        existing = self._find_idempotency(idempotency_key, ("order.cancelled", "order.cancel.rejected"))
        if existing is not None:
            if existing.get("command_fingerprint") != cancel_fingerprint:
                raise self._record_idempotency_conflict("order.cancel", idempotency_key, cancel_fingerprint, {**cancel_projection, "approval": approval.to_dict()})
            return existing
        identity = {"command_id": command_id, "idempotency_key": idempotency_key, "order_id": order_id, "command_fingerprint": cancel_fingerprint}
        if strategy_id is not None:
            identity["strategy_id"] = strategy_id
        payload = {"cancel": cancel_projection, "approval": approval.to_dict()}
        try:
            if portfolio_id != self.genesis.portfolio_id:
                raise BrokerRejected("portfolio identity mismatch", "command.portfolio_mismatch")
            if self.genesis.shared_portfolio_id is not None and strategy_id not in self.genesis.member_strategy_ids:
                raise BrokerRejected("strategy is not a portfolio member", "membership.not_member")
            if self.genesis.shared_portfolio_id is None and strategy_id is not None and strategy_id != self.genesis.strategy_id:
                raise BrokerRejected("strategy is not a portfolio member", "membership.not_member")
            if self._last_event_time_ms is not None and submitted_at_ms <= self._last_event_time_ms:
                raise BrokerRejected("cancel command cannot backdate into a processed market event", "command.backdated")
            if approval.approver_id != "owner" or approval.command_fingerprint != cancel_fingerprint:
                raise BrokerRejected("cancel approval is invalid", "approval.command_mismatch")
            if approval.revoked or not approval.single_use or approval.issued_at_ms > submitted_at_ms or approval.expires_at_ms <= submitted_at_ms:
                raise BrokerRejected("cancel approval is expired or revoked", "approval.expired_or_revoked")
            if approval.approval_id in self._revoked_approval_ids or self._approval_used(approval.approval_id):
                raise BrokerRejected("approval is revoked or already used", "approval.reused_or_revoked")
        except BrokerRejected as exc:
            return self._record_command_rejection("order.cancel.rejected", payload, identity, exc)
        for index, order in enumerate(self._orders):
            if order.order_id == order_id and order.state == "open":
                if self.genesis.shared_portfolio_id is not None and order.strategy_id != strategy_id:
                    return self._record_command_rejection("order.cancel.rejected", payload, identity, BrokerRejected("order is owned by another strategy", "membership.order_owner"))
                changed = B41Order(**{**order.to_dict(include_fingerprint=False), "state": "cancelled"})
                self._orders[index] = changed
                result = {**identity, "state": "cancelled"}
                try:
                    self._append_event("order.cancelled", {"cancel": payload["cancel"], "approval": approval.to_dict()}, result)
                except Exception:
                    self._orders[index] = order
                    raise
                return result
        return self._record_command_rejection("order.cancel.rejected", payload, identity, BrokerRejected("open order not found", "order.not_open"))

    @_portfolio_write
    def revoke_approval(self, approval_id: str, command_id: str, idempotency_key: str, revoked_at_ms: int, approver_id: str = "owner") -> dict[str, Any]:
        command_fingerprint = _fingerprint({"approval_id": approval_id, "command_id": command_id, "idempotency_key": idempotency_key, "revoked_at_ms": revoked_at_ms})
        existing = self._find_idempotency(idempotency_key, ("approval.revoked", "approval.revoke.rejected"))
        if existing is not None:
            if existing.get("command_fingerprint") == command_fingerprint:
                return existing
            raise self._record_idempotency_conflict("approval.revoke", idempotency_key, command_fingerprint, {"approval_id": approval_id, "command_id": command_id, "revoked_at_ms": revoked_at_ms, "approver_id": approver_id})
        identity = {"approval_id": approval_id, "command_id": command_id, "idempotency_key": idempotency_key, "command_fingerprint": command_fingerprint}
        payload = {"revoke": {"approval_id": approval_id, "command_id": command_id, "idempotency_key": idempotency_key, "revoked_at_ms": revoked_at_ms, "approver_id": approver_id}}
        try:
            if approver_id != "owner":
                raise BrokerRejected("approval revocation identity is invalid", "approval.revocation_unauthorized")
            if self._last_event_time_ms is not None and revoked_at_ms <= self._last_event_time_ms:
                raise BrokerRejected("approval revocation event time is invalid", "command.backdated")
            if approval_id in self._revoked_approval_ids:
                raise BrokerRejected("approval is already revoked", "approval.already_revoked")
            if self._approval_used(approval_id):
                raise BrokerRejected("used approval cannot be revoked", "approval.used_cannot_revoke")
        except BrokerRejected as exc:
            return self._record_command_rejection("approval.revoke.rejected", payload, identity, exc)
        result = {"approval_id": approval_id, "command_id": command_id, "idempotency_key": idempotency_key, "command_fingerprint": command_fingerprint, "state": "revoked"}
        self._revoked_approval_ids.append(approval_id)
        try:
            self._append_event("approval.revoked", payload["revoke"], result)
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
                fill = {"fill_id": _fingerprint({"order_id": order.order_id, "event_id": event.event_id})[:24], "order_id": order.order_id, "event_id": event.event_id, "quantity": order.quantity, "price": fill_price, "fee": fee, "spread_cost": spread_cost}
                if order.strategy_id is not None:
                    fill["strategy_id"] = order.strategy_id
                fills.append(fill)
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
            self._validate_shared_state()
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
        last_line: str | None = None
        current_line: list[str] = []
        current_line_has_content = False
        leading_invalid_whitespace: str | None = None
        line_separators = ("\n", "\r", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029")
        with self.ledger_path.open("r", encoding="utf-8") as ledger:
            while chunk := ledger.read(64 * 1024):
                for part in chunk.splitlines(keepends=True):
                    separator = "\r\n" if part.endswith("\r\n") else next(
                        (item for item in line_separators if part.endswith(item)),
                        "",
                    )
                    line_part = part[:-len(separator)] if separator else part
                    if current_line_has_content:
                        current_line.append(line_part)
                    elif line_part:
                        index = 0
                        while index < len(line_part) and line_part[index].isspace():
                            character = line_part[index]
                            if character not in " \t" and leading_invalid_whitespace is None:
                                leading_invalid_whitespace = character
                            index += 1
                        if index < len(line_part):
                            if leading_invalid_whitespace is not None:
                                current_line.append(leading_invalid_whitespace)
                            current_line.append(line_part[index:])
                            current_line_has_content = True
                            last_line = None
                    if separator:
                        if current_line_has_content:
                            last_line = "".join(current_line)
                        current_line.clear()
                        current_line_has_content = False
                        leading_invalid_whitespace = None
            if current_line_has_content:
                last_line = "".join(current_line)
        return json.loads(last_line)["event_fingerprint"] if last_line is not None else "0" * 64

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
