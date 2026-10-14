"""Small, replaceable providers used by the first offline proof."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import math
from typing import Literal, Protocol

from .contracts import BacktestResult, Evidence, ResearchResult


def _utc_timestamp(value: str, field: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise ValueError(f"{field} must include a UTC offset")


@dataclass(frozen=True)
class ProviderHealth:
    """Observable health for a provider without exposing provider internals."""

    provider: str
    status: Literal["healthy", "degraded", "unavailable"]
    checked_at: str
    message: str = ""

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider is required")
        if self.status not in {"healthy", "degraded", "unavailable"}:
            raise ValueError("invalid provider health status")
        _utc_timestamp(self.checked_at, "checked_at")


@dataclass(frozen=True)
class ProviderCapability:
    """A named capability advertised by a provider adapter."""

    name: str
    version: str
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.version.strip():
            raise ValueError("capability name and version are required")


@dataclass(frozen=True)
class ProviderDeadline:
    """Per-request wall-clock limit owned by the Market OS caller."""

    timeout_seconds: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True)
class ProviderError:
    """Normalized provider failure information for run events and retries."""

    code: str
    message: str
    retryable: bool = False
    provider: str | None = None

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.message.strip():
            raise ValueError("provider error code and message are required")


class ProviderCancelled(RuntimeError):
    """A provider stopped work after the root workflow requested cancellation."""


@dataclass(frozen=True)
class RateLimit:
    """Provider quota state captured at the adapter seam."""

    limit: int | None = None
    remaining: int | None = None
    reset_at: str | None = None

    def __post_init__(self) -> None:
        for value, field in ((self.limit, "limit"), (self.remaining, "remaining")):
            if value is not None and value < 0:
                raise ValueError(f"{field} must be non-negative")
        if self.reset_at is not None:
            _utc_timestamp(self.reset_at, "reset_at")


@dataclass(frozen=True)
class DataFreshness:
    """The source timestamp and retrieval time used to judge staleness."""

    as_of: str
    retrieved_at: str
    max_age_seconds: float | None = None

    def __post_init__(self) -> None:
        _utc_timestamp(self.as_of, "as_of")
        _utc_timestamp(self.retrieved_at, "retrieved_at")
        if self.max_age_seconds is not None and (
            not math.isfinite(self.max_age_seconds) or self.max_age_seconds < 0
        ):
            raise ValueError("max_age_seconds must be non-negative")


@dataclass(frozen=True)
class LicenseMetadata:
    """Usage classification carried with provider output."""

    classification: str
    license_name: str | None = None
    attribution: str | None = None
    restrictions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.classification.strip():
            raise ValueError("license classification is required")


@dataclass(frozen=True)
class Provenance:
    """Stable source identity for evidence, bars, and documents."""

    provider: str
    source_ref: str
    retrieved_at: str
    request_id: str | None = None

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.source_ref.strip():
            raise ValueError("provider and source_ref are required")
        _utc_timestamp(self.retrieved_at, "retrieved_at")


@dataclass(frozen=True)
class CachePolicy:
    """Explicit cache behavior so adapters cannot silently reuse stale data."""

    mode: Literal["disabled", "read_through", "fixture"] = "disabled"
    ttl_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"disabled", "read_through", "fixture"}:
            raise ValueError("invalid cache mode")
        if self.ttl_seconds is not None and (
            not math.isfinite(self.ttl_seconds) or self.ttl_seconds < 0
        ):
            raise ValueError("ttl_seconds must be non-negative")


@dataclass(frozen=True)
class DeterministicFixture:
    """Identity and checksum for a replayable, no-network provider fixture."""

    fixture_id: str
    checksum: str
    seed: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id.strip() or not self.checksum.strip():
            raise ValueError("fixture_id and checksum are required")


@dataclass(frozen=True)
class MarketBar:
    """Normalized OHLCV bar returned by a market-data adapter."""

    symbol: str
    venue: str
    currency: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    adjustment_basis: str
    provider: str
    retrieval_timestamp: str
    provenance: Provenance

    def __post_init__(self) -> None:
        for value, field in (
            (self.symbol, "symbol"),
            (self.venue, "venue"),
            (self.currency, "currency"),
            (self.adjustment_basis, "adjustment_basis"),
            (self.provider, "provider"),
        ):
            if not value.strip():
                raise ValueError(f"{field} is required")
        _utc_timestamp(self.timestamp, "timestamp")
        _utc_timestamp(self.retrieval_timestamp, "retrieval_timestamp")
        for value, field in (
            (self.open, "open"),
            (self.high, "high"),
            (self.low, "low"),
            (self.close, "close"),
            (self.volume, "volume"),
        ):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{field} must be finite and non-negative")


@dataclass(frozen=True)
class DocumentRecord:
    """Normalized research document with licensing and source lineage."""

    document_id: str
    title: str
    publisher: str
    source_ref: str
    published_at: str
    retrieved_at: str
    symbols: tuple[str, ...]
    media_type: str
    content_hash: str
    license: LicenseMetadata
    provenance: Provenance

    def __post_init__(self) -> None:
        for value, field in (
            (self.document_id, "document_id"),
            (self.title, "title"),
            (self.publisher, "publisher"),
            (self.source_ref, "source_ref"),
            (self.media_type, "media_type"),
            (self.content_hash, "content_hash"),
        ):
            if not value.strip():
                raise ValueError(f"{field} is required")
        _utc_timestamp(self.published_at, "published_at")
        _utc_timestamp(self.retrieved_at, "retrieved_at")


class MarketDataProvider(Protocol):
    def health(self) -> ProviderHealth: ...

    def capabilities(self) -> tuple[ProviderCapability, ...]: ...

    def bars(
        self,
        symbols: tuple[str, ...],
        start: str,
        end: str,
        *,
        deadline: ProviderDeadline,
        cache: CachePolicy,
    ) -> tuple[MarketBar, ...]: ...


class DocumentProvider(Protocol):
    def documents(
        self,
        query: str,
        symbols: tuple[str, ...],
        *,
        deadline: ProviderDeadline,
        cache: CachePolicy,
    ) -> tuple[DocumentRecord, ...]: ...


class ResearchProvider(Protocol):
    def research(
        self,
        objective: str,
        evidence: tuple[Evidence, ...],
        *,
        deadline: ProviderDeadline,
    ) -> ResearchResult: ...


class EvidenceProvider(Protocol):
    def retrieve(self, objective: str, symbols: tuple[str, ...], start: str, end: str) -> list[Evidence]: ...

class BacktestProvider(Protocol):
    def run(self, symbols: tuple[str, ...], start: str, end: str, initial_cash: float) -> BacktestResult: ...


@dataclass(frozen=True)
class FixtureMarketProvider:
    prices: dict[str, tuple[tuple[str, float], ...]]

    def retrieve(self, objective: str, symbols: tuple[str, ...], start: str, end: str) -> list[Evidence]:
        result: list[Evidence] = []
        for symbol in symbols:
            rows = tuple((day, price) for day, price in self.prices[symbol] if start <= day <= end)
            if not rows:
                raise ValueError(f"no market evidence for {symbol} in {start}:{end}")
            content = ", ".join(f"{day}={price:.2f}" for day, price in rows)
            result.append(Evidence(f"market-{symbol}", "market", f"{symbol} daily bars", "fixture:market", f"{rows[-1][0]}T00:00:00+00:00", content, (symbol,)))
        result.append(Evidence("document-policy", "document", "Paper trading policy", "fixture:policy", f"{end}T00:00:00+00:00", "All generated orders remain paper-only and require risk approval."))
        return result

@dataclass(frozen=True)
class DeterministicBacktestProvider:
    prices: dict[str, tuple[tuple[str, float], ...]]

    def run(self, symbols: tuple[str, ...], start: str, end: str, initial_cash: float) -> BacktestResult:
        selected = {s: tuple((d, p) for d, p in self.prices[s] if start <= d <= end) for s in symbols}
        if any(not rows for rows in selected.values()):
            raise ValueError("backtest requires at least one price row per symbol")
        first = {s: rows[0][1] for s, rows in selected.items()}
        last = {s: rows[-1][1] for s, rows in selected.items()}
        allocation = initial_cash / len(symbols)
        final_cash = sum(allocation * last[s] / first[s] for s in symbols)
        curve = tuple({"symbol": s, "start": first[s], "end": last[s]} for s in symbols)
        fingerprint = sha256(repr((symbols, start, end, initial_cash, curve)).encode()).hexdigest()
        return BacktestResult(initial_cash, final_cash, (final_cash / initial_cash - 1) * 100, curve, fingerprint)

def default_providers() -> tuple[FixtureMarketProvider, DeterministicBacktestProvider]:
    prices = {
        "SPY": (("2026-01-02", 100.0), ("2026-01-05", 101.0), ("2026-01-06", 102.0)),
        "QQQ": (("2026-01-02", 100.0), ("2026-01-05", 99.0), ("2026-01-06", 101.0)),
        "IWM": (("2026-01-02", 100.0), ("2026-01-05", 100.5), ("2026-01-06", 100.8)),
    }
    market = FixtureMarketProvider(prices)
    return market, DeterministicBacktestProvider(prices)
