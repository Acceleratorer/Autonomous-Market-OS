"""Versioned, dependency-free domain contracts for Market OS."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
import json
import math
import re
from typing import Any, Literal, Mapping, TypeVar

API_VERSION = "market-os.v1"
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")
_T = TypeVar("_T")


class ContractError(ValueError):
    """A stable client-facing validation error."""

    def __init__(self, code: str, message: str, *, field: str | None = None) -> None:
        self.code = code
        self.field = field
        super().__init__(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(value: str, field: str) -> None:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise ContractError("invalid_id", f"{field} must be a short stable identifier", field=field)


def _text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractError("required", f"{field} must not be empty", field=field)


def _date(value: str, field: str) -> None:
    if not isinstance(value, str) or not _DATE_RE.fullmatch(value):
        raise ContractError("invalid_date", f"{field} must use YYYY-MM-DD", field=field)
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError("invalid_date", f"{field} is not a calendar date", field=field) from exc


def _timestamp(value: str, field: str) -> None:
    if not isinstance(value, str):
        raise ContractError("invalid_timestamp", f"{field} must be an ISO-8601 timestamp", field=field)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("invalid_timestamp", f"{field} must be an ISO-8601 timestamp", field=field) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError("invalid_timestamp", f"{field} must include a UTC offset", field=field)
    if parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise ContractError("invalid_timestamp", f"{field} must be in UTC", field=field)


def _number(value: float, field: str, *, minimum: float = 0.0) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        raise ContractError("invalid_number", f"{field} must be finite and >= {minimum}", field=field)


def _choice(value: str, choices: tuple[str, ...], field: str) -> None:
    if value not in choices:
        raise ContractError("invalid_status", f"{field} must be one of {', '.join(choices)}", field=field)


def _version(value: str) -> None:
    if value != API_VERSION:
        raise ContractError("unsupported_version", f"unsupported contract version: {value}", field="api_version")


def _symbols(values: tuple[str, ...], field: str = "symbols") -> None:
    if not isinstance(values, tuple) or not values:
        raise ContractError("required", f"{field} must contain at least one symbol", field=field)
    for symbol in values:
        _symbol(symbol, field)


def _symbol(value: str, field: str) -> None:
    _text(value, field)
    if not _SYMBOL_RE.fullmatch(value):
        raise ContractError("invalid_symbol", f"{field} contains an invalid US symbol", field=field)


def _integer(value: int, field: str, *, minimum: int = 0) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ContractError("invalid_number", f"{field} must be an integer >= {minimum}", field=field)


@dataclass(frozen=True)
class AgentProfile:
    agent_id: str
    name: str
    provider: str
    model: str
    tools: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    memory_scope: str = "task"
    api_version: str = API_VERSION

    def __post_init__(self) -> None:
        _id(self.agent_id, "agent_id")
        _text(self.name, "name")
        _text(self.provider, "provider")
        _text(self.model, "model")
        _text(self.memory_scope, "memory_scope")
        _version(self.api_version)


@dataclass(frozen=True)
class Task:
    task_id: str
    objective: str
    symbols: tuple[str, ...]
    start: str
    end: str
    created_at: str
    execution_mode: Literal["paper"] = "paper"
    idempotency_key: str | None = None
    api_version: str = API_VERSION

    def __post_init__(self) -> None:
        _id(self.task_id, "task_id")
        _text(self.objective, "objective")
        _symbols(self.symbols)
        _date(self.start, "start")
        _date(self.end, "end")
        if self.start > self.end:
            raise ContractError("invalid_range", "start must be on or before end")
        _timestamp(self.created_at, "created_at")
        if self.execution_mode != "paper":
            raise ContractError("live_disabled", "live execution is disabled in market-os.v1", field="execution_mode")
        if self.idempotency_key is not None:
            _text(self.idempotency_key, "idempotency_key")
            if len(self.idempotency_key) > 255:
                raise ContractError("invalid_idempotency_key", "idempotency_key is too long", field="idempotency_key")
        _version(self.api_version)


@dataclass(frozen=True)
class Run:
    run_id: str
    task_id: str
    status: Literal["running", "completed", "failed", "cancelled", "rejected"]
    started_at: str
    finished_at: str | None = None
    error: str | None = None
    api_version: str = API_VERSION

    def __post_init__(self) -> None:
        _id(self.run_id, "run_id")
        _id(self.task_id, "task_id")
        _timestamp(self.started_at, "started_at")
        _choice(self.status, ("running", "completed", "failed", "cancelled", "rejected"), "status")
        if self.finished_at is not None:
            _timestamp(self.finished_at, "finished_at")
        if self.status == "running" and self.finished_at is not None:
            raise ContractError("invalid_status", "running runs cannot have finished_at")
        if self.status in {"failed", "rejected"} and not self.error:
            raise ContractError("missing_error", f"{self.status} runs must include error")
        _version(self.api_version)


@dataclass(frozen=True)
class RunEvent:
    event_id: str
    run_id: str
    kind: str
    timestamp: str
    payload: dict[str, Any] = field(default_factory=dict)
    actor: str = "market-os"
    tool: str | None = None
    model: str | None = None
    input_refs: tuple[str, ...] = ()
    output_refs: tuple[str, ...] = ()
    cost: float | None = None
    error: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    api_version: str = API_VERSION

    def __post_init__(self) -> None:
        _id(self.event_id, "event_id")
        _id(self.run_id, "run_id")
        _text(self.kind, "kind")
        _timestamp(self.timestamp, "timestamp")
        _text(self.actor, "actor")
        if self.cost is not None:
            _number(self.cost, "cost")
        _version(self.api_version)


@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    run_id: str
    kind: str
    media_type: str
    path: str
    created_at: str
    sha256: str
    lineage: tuple[str, ...] = ()
    access_policy: str = "owner"
    api_version: str = API_VERSION

    def __post_init__(self) -> None:
        _id(self.artifact_id, "artifact_id")
        _id(self.run_id, "run_id")
        _text(self.kind, "kind")
        _text(self.media_type, "media_type")
        _text(self.path, "path")
        _timestamp(self.created_at, "created_at")
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ContractError("invalid_digest", "sha256 must be a lowercase SHA-256 digest", field="sha256")
        _text(self.access_policy, "access_policy")
        _version(self.api_version)


@dataclass(frozen=True)
class KnowledgeDocument:
    document_id: str
    source: str
    modality: Literal["text", "pdf", "image", "audio", "video"]
    observed_at: str
    content_ref: str
    api_version: str = API_VERSION

    def __post_init__(self) -> None:
        _id(self.document_id, "document_id")
        _text(self.source, "source")
        _timestamp(self.observed_at, "observed_at")
        _text(self.content_ref, "content_ref")
        _version(self.api_version)


@dataclass(frozen=True)
class MarketObject:
    symbol: str
    venue: str
    observed_at: str
    price: float
    currency: str = "USD"
    price_basis: str = "close"
    api_version: str = API_VERSION

    def __post_init__(self) -> None:
        _symbol(self.symbol, "symbol")
        _text(self.venue, "venue")
        _timestamp(self.observed_at, "observed_at")
        _number(self.price, "price", minimum=0.0000001)
        _text(self.currency, "currency")
        _text(self.price_basis, "price_basis")
        _version(self.api_version)


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    kind: Literal["market", "document"]
    title: str
    source: str
    observed_at: str
    content: str
    symbols: tuple[str, ...] = ()
    api_version: str = API_VERSION

    def __post_init__(self) -> None:
        _id(self.evidence_id, "evidence_id")
        _text(self.title, "title")
        _text(self.source, "source")
        _timestamp(self.observed_at, "observed_at")
        _text(self.content, "content")
        _choice(self.kind, ("market", "document"), "kind")
        if self.kind == "market":
            _symbols(self.symbols)
        _version(self.api_version)


@dataclass(frozen=True)
class ResearchResult:
    summary: str
    citations: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    assumptions: tuple[str, ...] = ()
    api_version: str = API_VERSION

    def __post_init__(self) -> None:
        _text(self.summary, "summary")
        if not self.citations or not self.evidence_ids:
            raise ContractError("missing_citations", "research results need citations and evidence ids")
        _version(self.api_version)


@dataclass(frozen=True)
class BacktestResult:
    initial_cash: float
    final_cash: float
    return_pct: float
    equity_curve: tuple[dict[str, Any], ...]
    input_fingerprint: str
    api_version: str = API_VERSION

    def __post_init__(self) -> None:
        _number(self.initial_cash, "initial_cash", minimum=0.0000001)
        _number(self.final_cash, "final_cash")
        _number(self.return_pct, "return_pct", minimum=-100.0)
        _text(self.input_fingerprint, "input_fingerprint")
        _version(self.api_version)


@dataclass(frozen=True)
class Portfolio:
    portfolio_id: str
    base_currency: str
    cash: float
    positions: Mapping[str, float] = field(default_factory=dict)
    api_version: str = API_VERSION

    def __post_init__(self) -> None:
        _id(self.portfolio_id, "portfolio_id")
        _text(self.base_currency, "base_currency")
        _number(self.cash, "cash")
        _version(self.api_version)


@dataclass(frozen=True)
class Order:
    symbol: str
    side: Literal["buy", "sell"]
    quantity: int
    reference_price: float
    notional: float
    api_version: str = API_VERSION

    def __post_init__(self) -> None:
        _symbol(self.symbol, "symbol")
        _choice(self.side, ("buy", "sell"), "side")
        _integer(self.quantity, "quantity", minimum=1)
        _number(self.reference_price, "reference_price", minimum=0.0000001)
        _number(self.notional, "notional", minimum=0.0000001)
        _version(self.api_version)


@dataclass(frozen=True)
class OrderPlan:
    mode: Literal["paper"]
    orders: tuple[Order, ...]
    total_notional: float
    api_version: str = API_VERSION

    def __post_init__(self) -> None:
        if self.mode != "paper":
            raise ContractError("live_disabled", "live execution is disabled in market-os.v1", field="mode")
        _number(self.total_notional, "total_notional")
        _version(self.api_version)


@dataclass(frozen=True)
class RiskDecision:
    status: Literal["approved", "rejected"]
    reasons: tuple[str, ...]
    limits: dict[str, float]
    api_version: str = API_VERSION

    def __post_init__(self) -> None:
        _choice(self.status, ("approved", "rejected"), "status")
        if self.status == "rejected" and not self.reasons:
            raise ContractError("missing_reason", "rejected risk decisions need a reason")
        _version(self.api_version)


@dataclass(frozen=True)
class Approval:
    approval_id: str
    run_id: str
    status: Literal["pending", "approved", "rejected"]
    requested_by: str
    created_at: str
    decided_by: str | None = None
    decided_at: str | None = None
    api_version: str = API_VERSION

    def __post_init__(self) -> None:
        _id(self.approval_id, "approval_id")
        _id(self.run_id, "run_id")
        _text(self.requested_by, "requested_by")
        _timestamp(self.created_at, "created_at")
        _choice(self.status, ("pending", "approved", "rejected"), "status")
        if self.decided_at is not None:
            _timestamp(self.decided_at, "decided_at")
        if self.status != "pending" and (not self.decided_by or not self.decided_at):
            raise ContractError("missing_decision", "decided approvals need decided_by and decided_at")
        _version(self.api_version)


@dataclass(frozen=True)
class CancellationRequest:
    run_id: str
    requested_by: str
    requested_at: str
    reason: str
    api_version: str = API_VERSION

    def __post_init__(self) -> None:
        _id(self.run_id, "run_id")
        _text(self.requested_by, "requested_by")
        _timestamp(self.requested_at, "requested_at")
        _text(self.reason, "reason")
        _version(self.api_version)


@dataclass(frozen=True)
class ErrorResponse:
    code: str
    message: str
    retryable: bool = False
    request_id: str | None = None
    field: str | None = None
    api_version: str = API_VERSION

    def __post_init__(self) -> None:
        _text(self.code, "code")
        _text(self.message, "message")
        _version(self.api_version)


def error_response(error: ContractError, *, request_id: str | None = None) -> dict[str, Any]:
    return asdict(ErrorResponse(error.code, str(error), request_id=request_id, field=error.field))


def to_dict(value: Any) -> dict[str, Any]:
    """Serialize a contract to JSON-compatible primitives."""
    if not hasattr(value, "__dataclass_fields__"):
        raise TypeError("value must be a Market OS contract")
    return asdict(value)


def to_json(value: Any) -> str:
    """Serialize a contract with deterministic key ordering and separators."""
    return json.dumps(to_dict(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def task_from_dict(payload: Mapping[str, Any]) -> Task:
    """Validate and normalize a task received from JSON or another adapter."""
    values = _payload(payload, {"task_id", "objective", "symbols", "start", "end", "created_at", "execution_mode", "idempotency_key", "api_version"})
    if "symbols" in values:
        values["symbols"] = _tuple(values["symbols"], "symbols")
    return Task(**values)


def order_plan_from_dict(payload: Mapping[str, Any]) -> OrderPlan:
    """Validate and normalize a paper order plan received from JSON."""
    values = _payload(payload, {"mode", "orders", "total_notional", "api_version"})
    orders = values.get("orders", ())
    if not isinstance(orders, (list, tuple)):
        raise ContractError("invalid_payload", "orders must be an array", field="orders")
    normalized: list[Order] = []
    for order in orders:
        if isinstance(order, Order):
            normalized.append(order)
        elif isinstance(order, Mapping):
            normalized.append(order_from_dict(order))
        else:
            raise ContractError("invalid_payload", "each order must be an object", field="orders")
    values["orders"] = tuple(normalized)
    return OrderPlan(**values)


def _payload(payload: Mapping[str, Any], allowed: set[str]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ContractError("invalid_payload", "contract payload must be an object")
    values = dict(payload)
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise ContractError("unknown_field", f"unknown contract field: {unknown[0]}", field=unknown[0])
    if "api_version" not in values:
        values["api_version"] = API_VERSION
    return values


def _tuple(value: Any, field: str) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise ContractError("invalid_payload", f"{field} must be an array", field=field)
    return tuple(value)


def run_from_dict(payload: Mapping[str, Any]) -> Run:
    return Run(**_payload(payload, {"run_id", "task_id", "status", "started_at", "finished_at", "error", "api_version"}))


def run_event_from_dict(payload: Mapping[str, Any]) -> RunEvent:
    values = _payload(payload, {"event_id", "run_id", "kind", "timestamp", "payload", "actor", "tool", "model", "input_refs", "output_refs", "cost", "error", "provenance", "api_version"})
    values["input_refs"] = _tuple(values.get("input_refs", ()), "input_refs")
    values["output_refs"] = _tuple(values.get("output_refs", ()), "output_refs")
    return RunEvent(**values)


def artifact_from_dict(payload: Mapping[str, Any]) -> Artifact:
    values = _payload(payload, {"artifact_id", "run_id", "kind", "media_type", "path", "created_at", "sha256", "lineage", "access_policy", "api_version"})
    values["lineage"] = _tuple(values.get("lineage", ()), "lineage")
    return Artifact(**values)


def evidence_from_dict(payload: Mapping[str, Any]) -> Evidence:
    values = _payload(payload, {"evidence_id", "kind", "title", "source", "observed_at", "content", "symbols", "api_version"})
    values["symbols"] = _tuple(values.get("symbols", ()), "symbols")
    return Evidence(**values)


def research_result_from_dict(payload: Mapping[str, Any]) -> ResearchResult:
    values = _payload(payload, {"summary", "citations", "evidence_ids", "assumptions", "api_version"})
    values["citations"] = _tuple(values.get("citations", ()), "citations")
    values["evidence_ids"] = _tuple(values.get("evidence_ids", ()), "evidence_ids")
    values["assumptions"] = _tuple(values.get("assumptions", ()), "assumptions")
    return ResearchResult(**values)


def backtest_result_from_dict(payload: Mapping[str, Any]) -> BacktestResult:
    values = _payload(payload, {"initial_cash", "final_cash", "return_pct", "equity_curve", "input_fingerprint", "api_version"})
    values["equity_curve"] = _tuple(values.get("equity_curve", ()), "equity_curve")
    return BacktestResult(**values)


def order_from_dict(payload: Mapping[str, Any]) -> Order:
    return Order(**_payload(payload, {"symbol", "side", "quantity", "reference_price", "notional", "api_version"}))


def risk_decision_from_dict(payload: Mapping[str, Any]) -> RiskDecision:
    values = _payload(payload, {"status", "reasons", "limits", "api_version"})
    values["reasons"] = _tuple(values.get("reasons", ()), "reasons")
    return RiskDecision(**values)


_READERS: dict[type[Any], Any] = {
    Task: task_from_dict,
    Run: run_from_dict,
    RunEvent: run_event_from_dict,
    Artifact: artifact_from_dict,
    Evidence: evidence_from_dict,
    ResearchResult: research_result_from_dict,
    BacktestResult: backtest_result_from_dict,
    Order: order_from_dict,
    OrderPlan: order_plan_from_dict,
    RiskDecision: risk_decision_from_dict,
}


def from_json(payload: str | bytes, contract_type: type[_T]) -> _T:
    """Decode and validate one supported contract from JSON."""
    reader = _READERS.get(contract_type)
    if reader is None:
        raise TypeError(f"unsupported contract type: {contract_type!r}")
    try:
        value = json.loads(payload)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ContractError("invalid_json", "contract payload is not valid JSON") from exc
    try:
        return reader(value)
    except TypeError as exc:
        raise ContractError("missing_field", f"contract payload is missing a required field: {exc}") from exc
