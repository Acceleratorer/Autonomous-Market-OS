"""Deterministic, synthetic-only BTCUSDT Spot virtual venue.

The venue is a local matching harness for explicit synthetic market events and
orders.  It has no provider, network, credential, strategy, signal, or
derivative behavior.  Default costs are conservative test defaults and are not
market-realistic assumptions.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence


VENUE_SCHEMA = "market-os.b3-2.virtual-paper-venue@v1"
VENUE_VERSION = "v1"
SYMBOL = "BTCUSDT"
QUOTE_ASSET = "USDT"
BASE_ASSET = "BTC"
VENUE_FINGERPRINT_VERSION = "market-os.b3-2.virtual-paper-venue-fingerprint@v1"

BUY = "buy"
SELL = "sell"
MARKET = "market"
LIMIT = "limit"
SIDES = frozenset({BUY, SELL})
ORDER_TYPES = frozenset({MARKET, LIMIT})
_FORBIDDEN = ("http://", "https://", "\\", "binance", "provider", "credential", "openai", "typesafe", "jev")


class VenueError(ValueError):
    """Base error for fail-closed venue validation and matching."""


class InvalidMarketEvent(VenueError):
    pass


class InvalidOrder(VenueError):
    pass


class OrderRejected(VenueError):
    pass


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _canonical(value: Any) -> str:
    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise VenueError(f"{field} must be finite")
    return float(value)


def _nonnegative(value: Any, field: str) -> float:
    result = _finite(value, field)
    if result < 0:
        raise VenueError(f"{field} must be non-negative")
    return result


def _positive(value: Any, field: str) -> float:
    result = _finite(value, field)
    if result <= 0:
        raise VenueError(f"{field} must be positive")
    return result


def _timestamp(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise VenueError(f"{field} must be a non-negative integer timestamp")
    return value


def _safe_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 160:
        raise VenueError(f"{field} must be a bounded non-empty string")
    lowered = value.lower()
    if any(token in lowered for token in _FORBIDDEN) or re.search(r"[\x00-\x1f]", value):
        raise VenueError(f"{field} contains a non-synthetic identity")
    return value


def _synthetic_source(value: Any, field: str) -> str:
    result = _safe_text(value, field)
    if not (result.startswith("synthetic-") or (len(result) == 64 and all(char in "0123456789abcdef" for char in result))):
        raise VenueError(f"{field} must be a synthetic reference or SHA-256 fingerprint")
    return result


def _stored_fingerprint(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise VenueError(f"{field} must be a lowercase SHA-256 fingerprint")
    return value


def _validate_fingerprint(provided: str, projection: Mapping[str, Any], field: str) -> None:
    if provided and _fingerprint(projection) != _stored_fingerprint(provided, field):
        raise VenueError(f"{field} mismatch")


@dataclass(frozen=True)
class VenueConfig:
    """Frozen venue policy and explicit synthetic initial state.

    Defaults are conservative test defaults only; they are not market-realistic.
    """

    fee_bps_per_side: float = 10.0
    spread_bps_per_side: float = 1.0
    slippage_bps_per_side: float = 0.5
    initial_cash_usdt: float = 10_000.0
    initial_btc_quantity: float = 0.0
    initial_average_entry_price: float = 0.0
    max_order_notional_usdt: float = 1_000.0
    venue_version: str = VENUE_VERSION
    fingerprint: str = ""

    def __post_init__(self) -> None:
        for field in ("fee_bps_per_side", "spread_bps_per_side", "slippage_bps_per_side", "initial_cash_usdt", "initial_btc_quantity", "initial_average_entry_price", "max_order_notional_usdt"):
            _nonnegative(getattr(self, field), field)
        if self.max_order_notional_usdt <= 0:
            raise VenueError("max_order_notional_usdt must be positive")
        if self.initial_btc_quantity > 0 and self.initial_average_entry_price <= 0:
            raise VenueError("positive initial BTC requires an explicit positive entry price")
        if self.initial_btc_quantity == 0 and self.initial_average_entry_price != 0:
            raise VenueError("initial entry price requires a positive initial BTC quantity")
        if self.venue_version != VENUE_VERSION:
            raise VenueError("unsupported venue version")
        projection = self.to_dict(include_fingerprint=False)
        if self.fingerprint:
            _validate_fingerprint(self.fingerprint, projection, "venue config fingerprint")
        else:
            object.__setattr__(self, "fingerprint", _fingerprint(projection))

    @property
    def spread_bps(self) -> float:
        return self.spread_bps_per_side

    @property
    def slippage_bps(self) -> float:
        return self.slippage_bps_per_side

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        result = {
            "schema": VENUE_SCHEMA,
            "venue_version": self.venue_version,
            "fee_bps_per_side": self.fee_bps_per_side,
            "spread_bps_per_side": self.spread_bps_per_side,
            "slippage_bps_per_side": self.slippage_bps_per_side,
            "initial_cash_usdt": self.initial_cash_usdt,
            "initial_btc_quantity": self.initial_btc_quantity,
            "initial_average_entry_price": self.initial_average_entry_price,
            "max_order_notional_usdt": self.max_order_notional_usdt,
        }
        if include_fingerprint:
            result["fingerprint"] = self.fingerprint
        return result


@dataclass(frozen=True)
class SyntheticMarketEvent:
    event_id: str
    symbol: str
    event_time_ms: int
    bid: float
    ask: float
    last: float
    volume: float
    source_fingerprint: str
    synthetic_only: bool = True
    event_fingerprint: str = ""

    def __post_init__(self) -> None:
        _safe_text(self.event_id, "event_id")
        if self.symbol != SYMBOL:
            raise InvalidMarketEvent("venue is restricted to BTCUSDT Spot")
        _timestamp(self.event_time_ms, "event_time_ms")
        bid, ask, last = _positive(self.bid, "bid"), _positive(self.ask, "ask"), _positive(self.last, "last")
        if ask < bid:
            raise InvalidMarketEvent("ask must be greater than or equal to bid")
        _nonnegative(self.volume, "volume")
        try:
            _synthetic_source(self.source_fingerprint, "source_fingerprint")
        except VenueError as exc:
            raise InvalidMarketEvent(str(exc)) from exc
        if self.synthetic_only is not True:
            raise InvalidMarketEvent("market event must be synthetic-only")
        object.__setattr__(self, "bid", bid)
        object.__setattr__(self, "ask", ask)
        object.__setattr__(self, "last", last)
        object.__setattr__(self, "volume", float(self.volume))
        projection = self.to_dict(include_fingerprint=False)
        if self.event_fingerprint:
            _validate_fingerprint(self.event_fingerprint, projection, "event fingerprint")
        else:
            object.__setattr__(self, "event_fingerprint", _fingerprint(projection))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        result = {
            "schema": "market-os.b3-2.synthetic-market-event@v1",
            "event_id": self.event_id,
            "symbol": self.symbol,
            "event_time_ms": self.event_time_ms,
            "bid": self.bid,
            "ask": self.ask,
            "last": self.last,
            "volume": self.volume,
            "source_fingerprint": self.source_fingerprint,
            "synthetic_only": self.synthetic_only,
        }
        if include_fingerprint:
            result["event_fingerprint"] = self.event_fingerprint
        return result


@dataclass(frozen=True)
class VirtualOrder:
    order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    limit_price: float | None
    submitted_at_ms: int
    client_reference: str
    synthetic_only: bool = True
    order_fingerprint: str = ""

    def __post_init__(self) -> None:
        _safe_text(self.order_id, "order_id")
        if self.symbol != SYMBOL:
            raise InvalidOrder("venue is restricted to BTCUSDT Spot")
        if self.side not in SIDES:
            raise InvalidOrder("side must be buy or sell")
        if self.order_type not in ORDER_TYPES:
            raise InvalidOrder("order_type must be market or limit")
        quantity = _positive(self.quantity, "quantity")
        _timestamp(self.submitted_at_ms, "submitted_at_ms")
        _safe_text(self.client_reference, "client_reference")
        if self.synthetic_only is not True:
            raise InvalidOrder("order must be synthetic-only")
        if self.order_type == LIMIT:
            if self.limit_price is None:
                raise InvalidOrder("limit orders require limit_price")
            limit_price = _positive(self.limit_price, "limit_price")
            object.__setattr__(self, "limit_price", limit_price)
        elif self.limit_price is not None:
            raise InvalidOrder("market orders cannot carry limit_price")
        object.__setattr__(self, "quantity", quantity)
        projection = self.to_dict(include_fingerprint=False)
        if self.order_fingerprint:
            _validate_fingerprint(self.order_fingerprint, projection, "order fingerprint")
        else:
            object.__setattr__(self, "order_fingerprint", _fingerprint(projection))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        result = {
            "schema": "market-os.b3-2.virtual-order@v1",
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "limit_price": self.limit_price,
            "submitted_at_ms": self.submitted_at_ms,
            "client_reference": self.client_reference,
            "synthetic_only": self.synthetic_only,
        }
        if include_fingerprint:
            result["order_fingerprint"] = self.order_fingerprint
        return result


@dataclass(frozen=True)
class VirtualFill:
    fill_id: str
    order_id: str
    event_id: str
    filled_quantity: float
    fill_price: float
    fee_amount: float
    spread_cost: float
    slippage_cost: float
    filled_at_ms: int
    synthetic_only: bool = True
    fill_fingerprint: str = ""

    def __post_init__(self) -> None:
        for value, field in ((self.fill_id, "fill_id"), (self.order_id, "order_id"), (self.event_id, "event_id")):
            _safe_text(value, field)
        for field in ("filled_quantity", "fill_price", "fee_amount", "spread_cost", "slippage_cost"):
            _nonnegative(getattr(self, field), field)
        if self.fill_price <= 0 or self.filled_quantity <= 0:
            raise VenueError("fill quantity and price must be positive")
        _timestamp(self.filled_at_ms, "filled_at_ms")
        if self.synthetic_only is not True:
            raise VenueError("fill must be synthetic-only")
        projection = self.to_dict(include_fingerprint=False)
        if self.fill_fingerprint:
            _validate_fingerprint(self.fill_fingerprint, projection, "fill fingerprint")
        else:
            object.__setattr__(self, "fill_fingerprint", _fingerprint(projection))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        result = {
            "schema": "market-os.b3-2.virtual-fill@v1",
            "fill_id": self.fill_id,
            "order_id": self.order_id,
            "event_id": self.event_id,
            "filled_quantity": self.filled_quantity,
            "fill_price": self.fill_price,
            "fee_amount": self.fee_amount,
            "spread_cost": self.spread_cost,
            "slippage_cost": self.slippage_cost,
            "filled_at_ms": self.filled_at_ms,
            "synthetic_only": self.synthetic_only,
        }
        if include_fingerprint:
            result["fill_fingerprint"] = self.fill_fingerprint
        return result


@dataclass(frozen=True)
class VirtualPosition:
    cash_usdt: float
    btc_quantity: float
    average_entry_price: float
    realized_pnl_usdt: float
    unrealized_pnl_usdt: float
    total_fees_usdt: float
    total_notional_usdt: float
    mark_price: float
    state_fingerprint: str = ""

    def __post_init__(self) -> None:
        for field in ("cash_usdt", "btc_quantity", "average_entry_price", "realized_pnl_usdt", "unrealized_pnl_usdt", "total_fees_usdt", "total_notional_usdt", "mark_price"):
            _finite(getattr(self, field), field)
        for field in ("cash_usdt", "btc_quantity", "average_entry_price", "total_fees_usdt", "total_notional_usdt", "mark_price"):
            if getattr(self, field) < 0:
                raise VenueError(f"{field} cannot be negative")
        if self.btc_quantity > 0 and self.average_entry_price <= 0:
            raise VenueError("positive BTC requires a positive average entry price")
        projection = self.to_dict(include_fingerprint=False)
        if self.state_fingerprint:
            _validate_fingerprint(self.state_fingerprint, projection, "position state fingerprint")
        else:
            object.__setattr__(self, "state_fingerprint", _fingerprint(projection))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        result = {
            "schema": "market-os.b3-2.virtual-position@v1",
            "cash_usdt": self.cash_usdt,
            "btc_quantity": self.btc_quantity,
            "average_entry_price": self.average_entry_price,
            "realized_pnl_usdt": self.realized_pnl_usdt,
            "unrealized_pnl_usdt": self.unrealized_pnl_usdt,
            "total_fees_usdt": self.total_fees_usdt,
            "total_notional_usdt": self.total_notional_usdt,
            "mark_price": self.mark_price,
        }
        if include_fingerprint:
            result["state_fingerprint"] = self.state_fingerprint
        return result


@dataclass(frozen=True)
class VenueSnapshot:
    ordered_event_cursor: tuple[str, ...]
    open_orders: tuple[VirtualOrder, ...]
    fills: tuple[VirtualFill, ...]
    position: VirtualPosition
    venue_version: str = VENUE_VERSION
    last_event_time_ms: int | None = None
    fingerprint: str = ""
    replay_identity: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "ordered_event_cursor", tuple(self.ordered_event_cursor))
        object.__setattr__(self, "open_orders", tuple(self.open_orders))
        object.__setattr__(self, "fills", tuple(self.fills))
        if len(self.ordered_event_cursor) != len(set(self.ordered_event_cursor)):
            raise VenueError("snapshot event cursor contains duplicate event IDs")
        if len({order.order_id for order in self.open_orders}) != len(self.open_orders):
            raise VenueError("snapshot contains duplicate open order IDs")
        if len({fill.fill_id for fill in self.fills}) != len(self.fills):
            raise VenueError("snapshot contains duplicate fill IDs")
        if self.venue_version != VENUE_VERSION:
            raise VenueError("unsupported venue version")
        if self.last_event_time_ms is not None:
            _timestamp(self.last_event_time_ms, "last_event_time_ms")
        projection = self.to_dict(include_fingerprints=False)
        expected = _fingerprint(projection)
        if self.fingerprint:
            if self.fingerprint != expected:
                raise VenueError("snapshot fingerprint mismatch")
        else:
            object.__setattr__(self, "fingerprint", expected)
        replay_projection = {"fingerprint_version": VENUE_FINGERPRINT_VERSION, **projection}
        replay_expected = _fingerprint(replay_projection)
        if self.replay_identity:
            if self.replay_identity != replay_expected:
                raise VenueError("snapshot replay identity mismatch")
        else:
            object.__setattr__(self, "replay_identity", replay_expected)

    def to_dict(self, *, include_fingerprints: bool = True) -> dict[str, Any]:
        result = {
            "schema": "market-os.b3-2.venue-snapshot@v1",
            "venue_version": self.venue_version,
            "ordered_event_cursor": list(self.ordered_event_cursor),
            "last_event_time_ms": self.last_event_time_ms,
            "open_orders": [order.to_dict() for order in self.open_orders],
            "fills": [fill.to_dict() for fill in self.fills],
            "position": self.position.to_dict(),
        }
        if include_fingerprints:
            result["fingerprint"] = self.fingerprint
            result["replay_identity"] = self.replay_identity
        return result

    def __iter__(self):
        return iter(self.fills)

    def __len__(self) -> int:
        return len(self.fills)


class VirtualPaperVenue:
    """Long-only, fully filled virtual BTCUSDT Spot matcher."""

    def __init__(self, config: VenueConfig | None = None) -> None:
        self.config = config or VenueConfig()
        self._last_event_time_ms: int | None = None
        self._last_order_time_ms: int | None = None
        self._event_ids: set[str] = set()
        self._orders: list[VirtualOrder] = []
        self._order_ids: set[str] = set()
        self._fills: list[VirtualFill] = []
        self._cursor: list[str] = []
        self._position = VirtualPosition(
            cash_usdt=self.config.initial_cash_usdt,
            btc_quantity=self.config.initial_btc_quantity,
            average_entry_price=self.config.initial_average_entry_price,
            realized_pnl_usdt=0.0,
            unrealized_pnl_usdt=0.0,
            total_fees_usdt=0.0,
            total_notional_usdt=0.0,
            mark_price=0.0,
        )

    @property
    def initial_position(self) -> VirtualPosition:
        return VirtualPosition(
            cash_usdt=self.config.initial_cash_usdt,
            btc_quantity=self.config.initial_btc_quantity,
            average_entry_price=self.config.initial_average_entry_price,
            realized_pnl_usdt=0.0,
            unrealized_pnl_usdt=0.0,
            total_fees_usdt=0.0,
            total_notional_usdt=0.0,
            mark_price=0.0,
        )

    def submit_order(self, order: VirtualOrder) -> VirtualOrder:
        if not isinstance(order, VirtualOrder):
            raise InvalidOrder("submit_order requires a VirtualOrder")
        if order.order_id in self._order_ids:
            raise InvalidOrder("duplicate order_id")
        if self._last_event_time_ms is not None and order.submitted_at_ms <= self._last_event_time_ms:
            raise InvalidOrder("order timestamp would backdate into an already processed event")
        if self._last_order_time_ms is not None and order.submitted_at_ms < self._last_order_time_ms:
            raise InvalidOrder("orders must be submitted in timestamp order")
        if order.side == SELL and order.quantity > self._position.btc_quantity:
            raise OrderRejected("insufficient BTC")
        if order.order_type == LIMIT and order.quantity * float(order.limit_price) > self.config.max_order_notional_usdt:
            raise OrderRejected("order exceeds max_order_notional_usdt")
        self._orders.append(order)
        self._order_ids.add(order.order_id)
        self._last_order_time_ms = order.submitted_at_ms
        return order

    def process_event(self, event: SyntheticMarketEvent) -> VenueSnapshot:
        if not isinstance(event, SyntheticMarketEvent):
            raise InvalidMarketEvent("process_event requires a SyntheticMarketEvent")
        if event.event_id in self._event_ids:
            raise InvalidMarketEvent("duplicate event_id")
        if self._last_event_time_ms is not None and event.event_time_ms <= self._last_event_time_ms:
            raise InvalidMarketEvent("events must be strictly increasing in event_time_ms")

        cash = self._position.cash_usdt
        btc = self._position.btc_quantity
        average = self._position.average_entry_price
        realized = self._position.realized_pnl_usdt
        fees = self._position.total_fees_usdt
        notional_total = self._position.total_notional_usdt
        candidates: list[tuple[VirtualOrder, VirtualFill, float, float, float, float, float, float]] = []
        remaining: list[VirtualOrder] = []
        for order in self._orders:
            if order.submitted_at_ms > event.event_time_ms:
                remaining.append(order)
                continue
            base_price: float | None = None
            if order.side == BUY:
                if order.order_type == MARKET or (order.limit_price is not None and event.ask <= order.limit_price):
                    base_price = event.ask
                    slippage_price = base_price * self.config.slippage_bps_per_side / 10_000.0
                    fill_price = base_price + slippage_price
                    spread_cost = ((event.ask + event.bid) / 2.0) * self.config.spread_bps_per_side / 10_000.0 * order.quantity
                    slippage_cost = slippage_price * order.quantity
                    fee = fill_price * order.quantity * self.config.fee_bps_per_side / 10_000.0
                    order_notional = fill_price * order.quantity
                    if order_notional > self.config.max_order_notional_usdt:
                        raise OrderRejected("order exceeds max_order_notional_usdt")
                    if cash < order_notional + fee:
                        raise OrderRejected("insufficient cash")
                    new_cash = cash - order_notional - fee
                    new_btc = btc + order.quantity
                    new_average = ((average * btc) + order_notional + fee) / new_btc if btc > 0 else (order_notional + fee) / order.quantity
                    candidates.append((order, self._make_fill(order, event, fill_price, fee, spread_cost, slippage_cost), new_cash, new_btc, new_average, realized, fees + fee, notional_total + order_notional))
                    cash, btc, average, realized, fees, notional_total = new_cash, new_btc, new_average, realized, fees + fee, notional_total + order_notional
                else:
                    remaining.append(order)
            else:
                if order.quantity > btc:
                    raise OrderRejected("insufficient BTC")
                if order.order_type == MARKET or (order.limit_price is not None and event.bid >= order.limit_price):
                    base_price = event.bid
                    slippage_price = base_price * self.config.slippage_bps_per_side / 10_000.0
                    fill_price = base_price - slippage_price
                    if fill_price <= 0:
                        raise OrderRejected("slippage produces a non-positive fill price")
                    spread_cost = ((event.bid + event.ask) / 2.0) * self.config.spread_bps_per_side / 10_000.0 * order.quantity
                    slippage_cost = slippage_price * order.quantity
                    fee = fill_price * order.quantity * self.config.fee_bps_per_side / 10_000.0
                    order_notional = fill_price * order.quantity
                    if order_notional > self.config.max_order_notional_usdt:
                        raise OrderRejected("order exceeds max_order_notional_usdt")
                    new_cash = cash + order_notional - fee
                    new_btc = btc - order.quantity
                    new_realized = realized + (fill_price - average) * order.quantity - fee
                    new_average = 0.0 if new_btc == 0 else average
                    candidates.append((order, self._make_fill(order, event, fill_price, fee, spread_cost, slippage_cost), new_cash, new_btc, new_average, new_realized, fees + fee, notional_total + order_notional))
                    cash, btc, average, realized, fees, notional_total = new_cash, new_btc, new_average, new_realized, fees + fee, notional_total + order_notional
                else:
                    remaining.append(order)

        if cash < 0 or btc < 0:
            raise OrderRejected("matching would create a negative balance")
        self._orders = remaining
        self._fills.extend(fill for _, fill, *_ in candidates)
        self._event_ids.add(event.event_id)
        self._cursor.append(event.event_id)
        unrealized = (event.last - average) * btc if btc > 0 else 0.0
        self._last_event_time_ms = event.event_time_ms
        self._position = VirtualPosition(cash, btc, average, realized, unrealized, fees, notional_total, event.last)
        return self.snapshot()

    def snapshot(self) -> VenueSnapshot:
        return VenueSnapshot(tuple(self._cursor), tuple(self._orders), tuple(self._fills), self._position, last_event_time_ms=self._last_event_time_ms)

    @property
    def current_snapshot(self) -> VenueSnapshot:
        return self.snapshot()

    def get_snapshot(self) -> VenueSnapshot:
        return self.snapshot()

    def _make_fill(self, order: VirtualOrder, event: SyntheticMarketEvent, fill_price: float, fee: float, spread_cost: float, slippage_cost: float) -> VirtualFill:
        fill_id = "synthetic-fill-" + _fingerprint({"order_id": order.order_id, "event_id": event.event_id})[:24]
        return VirtualFill(fill_id, order.order_id, event.event_id, order.quantity, fill_price, fee, spread_cost, slippage_cost, event.event_time_ms)

    def apply_event(self, event: SyntheticMarketEvent) -> VenueSnapshot:
        return self.process_event(event)

    def advance(self, event: SyntheticMarketEvent) -> VenueSnapshot:
        return self.process_event(event)


def replay_virtual_venue(config: VenueConfig, events: Sequence[SyntheticMarketEvent], orders: Sequence[VirtualOrder]) -> VenueSnapshot:
    """Replay timestamped synthetic orders and events deterministically."""
    venue = VirtualPaperVenue(config)
    ordered_orders = sorted(orders, key=lambda item: (item.submitted_at_ms, item.order_id))
    index = 0
    for event in events:
        while index < len(ordered_orders) and ordered_orders[index].submitted_at_ms <= event.event_time_ms:
            venue.submit_order(ordered_orders[index])
            index += 1
        venue.process_event(event)
    while index < len(ordered_orders):
        venue.submit_order(ordered_orders[index])
        index += 1
    return venue.snapshot()


def verify_deterministic_replay(first: VenueSnapshot, second: VenueSnapshot) -> bool:
    return first.fingerprint == second.fingerprint and first.replay_identity == second.replay_identity and first.to_dict() == second.to_dict()


def replay_identity(snapshot: VenueSnapshot) -> str:
    return snapshot.replay_identity


PaperVenue = VirtualPaperVenue
PaperVenueConfig = VenueConfig


__all__ = [
    "VENUE_SCHEMA", "VENUE_VERSION", "SYMBOL", "QUOTE_ASSET", "BASE_ASSET",
    "BUY", "SELL", "MARKET", "LIMIT", "VenueError", "InvalidMarketEvent",
    "InvalidOrder", "OrderRejected", "VenueConfig", "SyntheticMarketEvent",
    "VirtualOrder", "VirtualFill", "VirtualPosition", "VenueSnapshot",
    "VirtualPaperVenue", "PaperVenue", "PaperVenueConfig", "replay_virtual_venue", "verify_deterministic_replay",
    "replay_identity",
]
