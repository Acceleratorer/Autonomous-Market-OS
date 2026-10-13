"""Versioned domain contracts for the first Market OS slice."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

API_VERSION = "market-os.v1"

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

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

@dataclass(frozen=True)
class Run:
    run_id: str
    task_id: str
    status: Literal["running", "completed", "failed", "cancelled", "rejected"]
    started_at: str
    finished_at: str | None = None
    error: str | None = None

@dataclass(frozen=True)
class RunEvent:
    event_id: str
    run_id: str
    kind: str
    timestamp: str
    payload: dict[str, Any] = field(default_factory=dict)

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

@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    kind: Literal["market", "document"]
    title: str
    source: str
    observed_at: str
    content: str
    symbols: tuple[str, ...] = ()

@dataclass(frozen=True)
class ResearchResult:
    summary: str
    citations: tuple[str, ...]
    evidence_ids: tuple[str, ...]

@dataclass(frozen=True)
class BacktestResult:
    initial_cash: float
    final_cash: float
    return_pct: float
    equity_curve: tuple[dict[str, Any], ...]
    input_fingerprint: str

@dataclass(frozen=True)
class Order:
    symbol: str
    side: Literal["buy", "sell"]
    quantity: int
    reference_price: float
    notional: float

@dataclass(frozen=True)
class OrderPlan:
    mode: Literal["paper"]
    orders: tuple[Order, ...]
    total_notional: float

    def __post_init__(self) -> None:
        if self.mode != "paper":
            raise ValueError("live execution is disabled in market-os.v1")

@dataclass(frozen=True)
class RiskDecision:
    status: Literal["approved", "rejected"]
    reasons: tuple[str, ...]
    limits: dict[str, float]

def to_dict(value: Any) -> dict[str, Any]:
    return asdict(value)
