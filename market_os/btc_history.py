"""Offline-capable BTC history ingestion, Parquet snapshots, and DuckDB catalog.

The Binance transport is intentionally disabled until source/legal review and
explicit user authorization are complete. All other layers accept fixture or
injected transport pages and perform no network I/O themselves.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any, Callable, Protocol

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from .btc_paper import BTC_API_VERSION, BTC_SYMBOL, ClosedCandle
from .contracts import ContractError, _timestamp

HISTORY_VERSION = "market-os.btc-history.v1"
FIXTURE_SCHEMA = "market-os.btc-history-fixture.v1"
READINESS_VERSION = "market-os.btc-history-readiness.v1"
AUTHORIZATION_VERSION = "market-os.btc-history-authorization.v1"
SOURCE_ID = "binance.spot.rest.klines"
SOURCE_HOST = "data-api.binance.vision"
SOURCE_PATH = "/api/v3/klines"
SOURCE_METHOD = "GET"
SOURCE_INTERVAL = "1m"
SOURCE_REQUEST_WEIGHT = 2
MAX_PAGE_SIZE = 1000
DEFAULT_PAGE_SIZE = 1000
MAX_PAGES = 100
MAX_CANDLES = 100_000
MAX_ATTEMPTS = 3
MAX_RETRY_AFTER_SECONDS = 60
HISTORY_MAX_RESPONSE_BYTES = 256 * 1024
READINESS_DAYS = 30
READINESS_MAX_PAGES = 44
READINESS_MAX_ROWS = 43_200
READINESS_MAX_REQUESTS = 44
READINESS_MAX_RUNTIME_SECONDS = 900
_DATASET_ID_RE = re.compile(r"^(?:btc-history-[0-9a-f]{20}|btc-history-manifest-[0-9a-f]{20})$")


class HistoryError(ValueError):
    def __init__(self, code: str, message: str, *, retry_after: float | None = None) -> None:
        self.code = code
        self.retry_after = retry_after
        super().__init__(message)


def _require_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise HistoryError("invalid_range", f"{field} must be an integer")
    return value


def validate_historical_budget(
    start_time_ms: int,
    end_time_ms_exclusive: int,
    *,
    page_size: int,
    max_pages: int,
    max_requests: int,
    max_rows: int,
    max_runtime_seconds: int,
    max_attempts: int,
) -> dict[str, int]:
    """Validate the bounded first run without opening a transport."""
    for name, value in {
        "page_size": page_size,
        "max_pages": max_pages,
        "max_requests": max_requests,
        "max_rows": max_rows,
        "max_runtime_seconds": max_runtime_seconds,
        "max_attempts": max_attempts,
    }.items():
        _require_int(value, name)
    requests = plan_pages(start_time_ms, end_time_ms_exclusive, page_size=page_size, max_pages=max_pages)
    expected_rows = (end_time_ms_exclusive - start_time_ms) // 60_000
    expected_pages = len(requests)
    expected_requests = expected_pages * max_attempts
    if expected_rows > max_rows or expected_requests > max_requests:
        raise HistoryError("request_budget", "requested range exceeds the configured request budget")
    if max_pages > READINESS_MAX_PAGES or max_rows > READINESS_MAX_ROWS or max_requests > READINESS_MAX_REQUESTS:
        raise HistoryError("request_budget", "historical caps exceed the readiness proposal")
    if max_runtime_seconds <= 0 or max_runtime_seconds > READINESS_MAX_RUNTIME_SECONDS:
        raise HistoryError("runtime_cap", "historical runtime cap must be between 1 and 900 seconds")
    if max_attempts != 1:
        raise HistoryError("retry_policy", "the bounded historical run permits exactly one attempt per page")
    return {
        "expected_rows": expected_rows,
        "expected_pages": expected_pages,
        "expected_requests": expected_requests,
        "page_size": page_size,
        "max_pages": max_pages,
        "max_requests": max_requests,
        "max_rows": max_rows,
        "max_runtime_seconds": max_runtime_seconds,
        "max_attempts": max_attempts,
    }


def plan_historical_readiness(cutoff_ms: int) -> dict[str, Any]:
    """Return the offline proposal for the first separately approved run.

    ``cutoff_ms`` is the explicit UTC minute boundary for the first excluded
    candle. The half-open range therefore contains exactly the preceding 30
    days and never treats the current/open candle as finalized data.
    """
    cutoff_ms = _require_int(cutoff_ms, "cutoff_ms")
    if cutoff_ms <= 0 or cutoff_ms % 60_000:
        raise HistoryError("invalid_range", "cutoff_ms must be a positive minute-aligned UTC timestamp")
    end_ms = cutoff_ms
    start_ms = end_ms - READINESS_DAYS * 24 * 60 * 60 * 1000
    budget = validate_historical_budget(
        start_ms,
        end_ms,
        page_size=DEFAULT_PAGE_SIZE,
        max_pages=READINESS_MAX_PAGES,
        max_requests=READINESS_MAX_REQUESTS,
        max_rows=READINESS_MAX_ROWS,
        max_runtime_seconds=READINESS_MAX_RUNTIME_SECONDS,
        max_attempts=1,
    )
    return {
        "schema": READINESS_VERSION,
        "status": "proposal-blocked-pending-authorization",
        "ingestion_allowed": False,
        "network_requests": 0,
        "provider_requests": 0,
        "credentials_used": False,
        "instrument": {"venue": "BINANCE_SPOT", "symbol": BTC_SYMBOL, "interval": SOURCE_INTERVAL},
        "source": {"host": SOURCE_HOST, "method": SOURCE_METHOD, "path": SOURCE_PATH, "security": "NONE", "request_weight": SOURCE_REQUEST_WEIGHT},
        "requested_start_ms": start_ms,
        "requested_end_ms_exclusive": end_ms,
        "cutoff_ms": cutoff_ms,
        "excluded_final_candle_open_ms": cutoff_ms,
        "max_response_bytes": HISTORY_MAX_RESPONSE_BYTES,
        "authorization": {
            "explicit_runtime_flag": "--allow-historical-ingest",
            "authorization_file_required": True,
            "terms_verified": False,
            "regional_eligibility_verified": False,
            "retention_rights_verified": False,
            "refusal_reason": "source terms, regional eligibility, and retention rights are unresolved",
        },
        "purpose": "local BTC quantitative research and paper-only simulation",
        "storage": {
            "root": "user-selected B1 HistoryStore root",
            "raw_pages": "immutable SHA-256 JSON pages",
            "raw_page_retention": "local-only-until-explicit-deletion",
            "canonical": "Parquet snapshot with DuckDB catalog and manifest lineage",
            "retention": "local-only-until-explicit-deletion",
            "backup": "none by default",
            "access": "local operator only; no upload or redistribution",
        },
        "retry_policy": {
            "max_attempts_per_page": 1,
            "retry_after": "record and stop on 429/418; no automatic retry in initial run",
            "timeouts": "bounded transport connect/read timeouts",
            "checkpoint": "persist completed raw pages before each next page; resume requires fresh approval",
        },
        "safety": {
            "websocket": False,
            "credentials": False,
            "authenticated_endpoints": False,
            "orders": False,
            "account_access": False,
            "trading": False,
        },
        **budget,
    }


def validate_historical_authorization(
    value: dict[str, Any] | None,
    *,
    requested: dict[str, int] | None = None,
) -> None:
    if not isinstance(value, dict) or value.get("schema") != AUTHORIZATION_VERSION:
        raise HistoryError("source_not_authorized", "a matching historical authorization record is required")
    expected = {
        "explicit_approval": True,
        "terms_verified": True,
        "regional_eligibility_verified": True,
        "retention_rights_verified": True,
        "host": SOURCE_HOST,
        "method": SOURCE_METHOD,
        "path": SOURCE_PATH,
        "symbol": BTC_SYMBOL,
        "interval": SOURCE_INTERVAL,
        "request_weight": SOURCE_REQUEST_WEIGHT,
        "authenticated": False,
        "trading": False,
        "purpose": "local BTC quantitative research and paper-only simulation",
        "retention": "local-only-until-explicit-deletion",
    }
    if any(value.get(key) != expected_value for key, expected_value in expected.items()):
        raise HistoryError("source_not_authorized", "historical authorization does not match the bounded source policy")
    for key, expected_value in (requested or {}).items():
        if value.get(key) != expected_value:
            raise HistoryError("source_not_authorized", f"historical authorization does not match requested {key}")


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _iso_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat(timespec="milliseconds")


def _epoch_ms(value: str) -> int:
    parsed = _parse_utc(value, "timestamp")
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = parsed - epoch
    return delta.days * 86_400_000 + delta.seconds * 1_000 + delta.microseconds // 1_000


def _parse_utc(value: str, field: str) -> datetime:
    _timestamp(value, field)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _decimal(value: Any, field: str, *, minimum: Decimal | None = None) -> Decimal:
    if isinstance(value, bool):
        raise HistoryError("invalid_record", f"{field} must be numeric")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise HistoryError("invalid_record", f"{field} must be numeric") from exc
    if not result.is_finite() or (minimum is not None and result < minimum):
        raise HistoryError("invalid_record", f"{field} is outside its valid range")
    return result


@dataclass(frozen=True)
class PageRequest:
    page_index: int
    start_time_ms: int
    end_time_ms: int  # Binance uses inclusive endTime.
    limit: int


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes
    received_at: str


class HistoricalTransport(Protocol):
    approved: bool

    def fetch_page(self, request: PageRequest) -> HttpResponse: ...


class BinanceHistoricalTransport:
    """Disabled public transport seam. This class intentionally opens no sockets."""

    approved = False
    host = SOURCE_HOST
    path = "/api/v3/klines"

    def fetch_page(self, request: PageRequest) -> HttpResponse:
        raise HistoryError("source_not_approved", "public Binance market-data transport is disabled pending explicit approval")


def plan_pages(
    start_time_ms: int,
    end_time_ms_exclusive: int,
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = MAX_PAGES,
) -> tuple[PageRequest, ...]:
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (start_time_ms, end_time_ms_exclusive, page_size, max_pages)):
        raise HistoryError("invalid_range", "range and page limits must be integers")
    if start_time_ms < 0 or end_time_ms_exclusive <= start_time_ms:
        raise HistoryError("invalid_range", "range must be a positive half-open UTC millisecond interval")
    if start_time_ms % 60_000 or end_time_ms_exclusive % 60_000:
        raise HistoryError("invalid_range", "one-minute range endpoints must be minute-aligned")
    if not 1 <= page_size <= MAX_PAGE_SIZE or max_pages <= 0:
        raise HistoryError("invalid_page_limit", f"page_size must be 1..{MAX_PAGE_SIZE} and max_pages positive")
    page_count = (end_time_ms_exclusive - start_time_ms + page_size * 60_000 - 1) // (page_size * 60_000)
    if page_count > max_pages or page_count * page_size > MAX_CANDLES:
        raise HistoryError("page_limit", f"requested range exceeds the bounded {max_pages}-page acquisition limit")
    return tuple(
        PageRequest(index, page_start, min(page_start + page_size * 60_000, end_time_ms_exclusive) - 1, page_size)
        for index, page_start in enumerate(range(start_time_ms, end_time_ms_exclusive, page_size * 60_000))
    )


def classify_http_failure(status: int, headers: dict[str, str] | None = None) -> HistoryError:
    headers = {key.lower(): value for key, value in (headers or {}).items()}
    retry_after = None
    if "retry-after" in headers:
        try:
            retry_after = max(0.0, float(headers["retry-after"]))
        except ValueError:
            retry_after = None
    if status == 429:
        return HistoryError("rate_limited", "source returned HTTP 429; backoff required", retry_after=retry_after)
    if status == 418:
        return HistoryError("ip_banned", "source returned HTTP 418; automatic retry forbidden", retry_after=retry_after)
    if status >= 500:
        return HistoryError("server_error", f"source returned HTTP {status}")
    if status >= 400:
        return HistoryError("source_rejected", f"source returned HTTP {status}")
    return HistoryError("unexpected_status", f"unexpected source status {status}")


def fetch_pages(
    transport: HistoricalTransport,
    requests: tuple[PageRequest, ...],
    *,
    max_attempts: int = MAX_ATTEMPTS,
    max_retry_after_seconds: int = MAX_RETRY_AFTER_SECONDS,
    wait: Callable[[float], None] = time.sleep,
) -> tuple[HttpResponse, ...]:
    if not getattr(transport, "approved", False):
        raise HistoryError("source_not_approved", "historical source transport is disabled pending explicit approval")
    if not 1 <= max_attempts <= MAX_ATTEMPTS:
        raise HistoryError("invalid_retry_policy", f"max_attempts must be between 1 and {MAX_ATTEMPTS}")
    responses: list[HttpResponse] = []
    for request in requests:
        for attempt in range(max_attempts):
            try:
                response = transport.fetch_page(request)
            except (TimeoutError, OSError) as exc:
                error = HistoryError("timeout", "historical request timed out")
                if attempt + 1 == max_attempts:
                    raise error from exc
                continue
            if 200 <= response.status < 300:
                responses.append(response)
                break
            error = classify_http_failure(response.status, response.headers)
            if error.code == "ip_banned" or error.code == "source_rejected":
                raise error
            if attempt + 1 == max_attempts:
                raise HistoryError("retry_exhausted", f"historical request retry limit exhausted after {error.code}") from error
            if error.code == "rate_limited":
                if error.retry_after is None or error.retry_after > max_retry_after_seconds:
                    raise HistoryError("retry_after_exceeds_policy", "rate-limit delay missing or exceeds local cap", retry_after=error.retry_after)
                wait(error.retry_after)
        else:
            raise HistoryError("retry_exhausted", "historical request retry limit exhausted")
    return tuple(responses)


def parse_kline_row(
    row: Any,
    *,
    received_at: str,
    as_of_ms: int | None = None,
    source_record_fingerprint: str | None = None,
) -> tuple[ClosedCandle, dict[str, Any]]:
    """Parse Binance's documented 12-field REST row into the B0 candle contract."""
    _parse_utc(received_at, "received_at")
    if not isinstance(row, (list, tuple)) or len(row) != 12:
        raise HistoryError("invalid_record", "kline row must contain exactly 12 fields")
    open_ms, open_raw, high_raw, low_raw, close_raw, volume_raw, source_close_ms = row[:7]
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (open_ms, source_close_ms)):
        raise HistoryError("invalid_record", "kline open and close timestamps must be integer milliseconds")
    if open_ms % 60_000 or source_close_ms != open_ms + 60_000 - 1:
        raise HistoryError("invalid_record", "row is not an aligned one-minute kline")
    if as_of_ms is None:
        as_of_ms = source_close_ms + 1
    if source_close_ms >= as_of_ms:
        raise HistoryError("not_closed", "kline close timestamp has not passed the explicit as_of cutoff")
    opened = _decimal(open_raw, "open", minimum=Decimal("0.0000000001"))
    high = _decimal(high_raw, "high", minimum=Decimal("0.0000000001"))
    low = _decimal(low_raw, "low", minimum=Decimal("0.0000000001"))
    closed = _decimal(close_raw, "close", minimum=Decimal("0.0000000001"))
    volume = _decimal(volume_raw, "volume", minimum=Decimal(0))
    if high < max(opened, closed, low) or low > min(opened, closed, high):
        raise HistoryError("invalid_record", "OHLC range does not contain open and close")
    close_boundary_ms = open_ms + 60_000
    close_time = _iso_ms(close_boundary_ms)
    # Binance's inclusive final millisecond represents the candle close boundary.
    source_timestamp = close_time
    received = _parse_utc(received_at, "received_at")
    # Historical responses arrive after the source close boundary. Keep the
    # receipt timestamp in provenance while making availability point-in-time
    # safe for the B0 ordering rule.
    availability = max(received, datetime.fromtimestamp(close_boundary_ms / 1000, timezone.utc))
    raw_fp = source_record_fingerprint or _sha(_json_bytes(row))
    candle_values = {
        "open_time": _iso_ms(open_ms), "close_time": close_time,
        "open": float(opened), "high": float(high), "low": float(low),
        "close": float(closed), "volume": float(volume),
    }
    canonical_fp = _sha(_json_bytes(candle_values))
    candle = ClosedCandle(
        BTC_SYMBOL, "1m", candle_values["open_time"], close_time,
        candle_values["open"], candle_values["high"], candle_values["low"],
        candle_values["close"], candle_values["volume"], source_timestamp,
        received_at, availability.isoformat(timespec="milliseconds"), raw_fp,
        canonical_fp,
    )
    ancillary = {
        "quote_volume": str(_decimal(row[7], "quote_volume", minimum=Decimal(0))),
        "trade_count": _parse_trade_count(row[8]),
        "taker_buy_base_volume": str(_decimal(row[9], "taker_buy_base_volume", minimum=Decimal(0))),
        "taker_buy_quote_volume": str(_decimal(row[10], "taker_buy_quote_volume", minimum=Decimal(0))),
        "ignored": str(row[11]),
    }
    return candle, ancillary


def _parse_trade_count(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise HistoryError("invalid_record", "trade_count must be a non-negative integer")
    return value


@dataclass(frozen=True)
class IngestResult:
    dataset_revision: str
    manifest_id: str
    canonical_fingerprint: str
    canonical_count: int


class HistoryStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.raw_dir = self.root / "raw"
        self.dataset_dir = self.root / "datasets"
        self.manifest_dir = self.root / "manifests"
        self.checkpoint_dir = self.root / "checkpoints"
        for path in (self.raw_dir, self.dataset_dir, self.manifest_dir, self.checkpoint_dir):
            path.mkdir(parents=True, exist_ok=True)
        self.catalog_path = self.root / "catalog.duckdb"
        self._initialize()

    def _connect(self):
        return duckdb.connect(str(self.catalog_path))

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS datasets (
                    dataset_revision VARCHAR PRIMARY KEY,
                    symbol VARCHAR NOT NULL,
                    venue VARCHAR NOT NULL,
                    interval VARCHAR NOT NULL,
                    canonical_fingerprint VARCHAR NOT NULL,
                    parquet_path VARCHAR NOT NULL,
                    parquet_sha256 VARCHAR NOT NULL,
                    candle_count BIGINT NOT NULL,
                    first_open_time_ms BIGINT NOT NULL,
                    last_close_time_ms BIGINT NOT NULL,
                    contract_version VARCHAR NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS raw_pages (
                    page_sha256 VARCHAR PRIMARY KEY,
                    path VARCHAR NOT NULL,
                    size_bytes BIGINT NOT NULL,
                    source_identity VARCHAR NOT NULL,
                    captured_at VARCHAR NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS ingestion_runs (
                    manifest_id VARCHAR PRIMARY KEY,
                    dataset_revision VARCHAR NOT NULL,
                    run_id VARCHAR NOT NULL,
                    raw_fingerprint VARCHAR NOT NULL,
                    manifest_path VARCHAR NOT NULL,
                    manifest_sha256 VARCHAR NOT NULL,
                    requested_start_ms BIGINT NOT NULL,
                    requested_end_ms BIGINT NOT NULL,
                    network_requests BIGINT NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS run_outcomes (
                    manifest_id VARCHAR NOT NULL,
                    outcome_index BIGINT NOT NULL,
                    raw_page_sha256 VARCHAR NOT NULL,
                    row_index BIGINT NOT NULL,
                    source_record_fingerprint VARCHAR NOT NULL,
                    open_time_ms BIGINT,
                    status VARCHAR NOT NULL,
                    reason VARCHAR,
                    accepted_canonical BOOLEAN NOT NULL,
                    PRIMARY KEY (manifest_id, outcome_index)
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS run_provenance (
                    manifest_id VARCHAR NOT NULL,
                    raw_page_sha256 VARCHAR NOT NULL,
                    row_index BIGINT NOT NULL,
                    source_record_fingerprint VARCHAR NOT NULL,
                    payload_json VARCHAR NOT NULL,
                    PRIMARY KEY (manifest_id, raw_page_sha256, row_index)
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS dataset_provenance (
                    dataset_revision VARCHAR NOT NULL,
                    open_time_ms BIGINT NOT NULL,
                    source_record_fingerprint VARCHAR NOT NULL,
                    raw_page_sha256 VARCHAR NOT NULL,
                    PRIMARY KEY (dataset_revision, open_time_ms, source_record_fingerprint)
                )
            """)

    def ingest_fixture(self, fixture: dict[str, Any]) -> IngestResult:
        if fixture.get("schema") != FIXTURE_SCHEMA:
            raise HistoryError("invalid_fixture", f"expected fixture schema {FIXTURE_SCHEMA}")
        start = fixture.get("requested_start_ms")
        end = fixture.get("requested_end_ms_exclusive")
        as_of = fixture.get("as_of_ms")
        captured_at = fixture.get("received_at")
        if any(isinstance(value, bool) or not isinstance(value, int) for value in (start, end, as_of)):
            raise HistoryError("invalid_fixture", "requested range and as_of_ms must be integer milliseconds")
        pages = fixture.get("pages")
        if not isinstance(pages, list) or len(pages) > MAX_PAGES:
            raise HistoryError("page_limit", f"fixture must contain at most {MAX_PAGES} pages")
        if end <= start or start % 60_000 or end % 60_000 or end - start > MAX_CANDLES * 60_000:
            raise HistoryError("invalid_range", "fixture range must be aligned, positive, and within local candle cap")
        _parse_utc(captured_at, "received_at")
        return self._ingest_pages(
            pages, captured_at=captured_at, as_of_ms=as_of,
            requested_start_ms=start, requested_end_ms=end,
            endpoint_class="synthetic-fixture", source_identity=f"{SOURCE_ID}.synthetic-fixture",
        )

    def acquire(
        self,
        start_time_ms: int,
        end_time_ms_exclusive: int,
        *,
        transport: HistoricalTransport | None = None,
        resume: bool = True,
        page_size: int = DEFAULT_PAGE_SIZE,
        max_pages: int = READINESS_MAX_PAGES,
        max_requests: int = READINESS_MAX_REQUESTS,
        max_rows: int = READINESS_MAX_ROWS,
        max_runtime_seconds: int = READINESS_MAX_RUNTIME_SECONDS,
        max_attempts: int = 1,
        allow_historical_ingest: bool = False,
        authorization: dict[str, Any] | None = None,
        wait: Callable[[float], None] = time.sleep,
    ) -> IngestResult:
        if not allow_historical_ingest:
            raise HistoryError("source_not_approved", "source/legal review is incomplete; --allow-historical-ingest is required before historical acquisition")
        validate_historical_authorization(
            authorization,
            requested={
                "requested_start_ms": start_time_ms,
                "requested_end_ms_exclusive": end_time_ms_exclusive,
                "page_size": page_size,
                "max_pages": max_pages,
                "max_requests": max_requests,
                "max_rows": max_rows,
                "max_runtime_seconds": max_runtime_seconds,
                "max_attempts": max_attempts,
            },
        )
        transport = transport or BinanceHistoricalTransport()
        if not getattr(transport, "approved", False):
            raise HistoryError("source_not_approved", "source/legal review and explicit user approval are required before transport")
        requests = plan_pages(start_time_ms, end_time_ms_exclusive, page_size=page_size, max_pages=max_pages)
        validate_historical_budget(
            start_time_ms,
            end_time_ms_exclusive,
            page_size=page_size,
            max_pages=max_pages,
            max_requests=max_requests,
            max_rows=max_rows,
            max_runtime_seconds=max_runtime_seconds,
            max_attempts=max_attempts,
        )
        as_of_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        deadline = time.monotonic() + max_runtime_seconds
        checkpoint_id = _sha(_json_bytes({"source": SOURCE_ID, "start": start_time_ms, "end": end_time_ms_exclusive, "page_size": page_size, "max_pages": max_pages, "max_requests": max_requests, "max_rows": max_rows, "max_attempts": max_attempts}))
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
        checkpoint = self._read_checkpoint(checkpoint_path, checkpoint_id, requests, page_size) if resume else self._new_checkpoint(checkpoint_id, requests, page_size)
        if checkpoint["status"] == "complete":
            pages = []
            for page in checkpoint["pages"]:
                raw_rows = json.loads((self.raw_dir / f"{page['sha256']}.json").read_bytes())
                pages.append({"rows": raw_rows, "captured_at": page["captured_at"], "page_sha256": page["sha256"]})
            return self._ingest_pages(
                pages, captured_at=None, as_of_ms=as_of_ms,
                requested_start_ms=start_time_ms, requested_end_ms=end_time_ms_exclusive,
                endpoint_class="public-market-data", source_identity=SOURCE_ID,
                network_requests=0,
            )
        completed = checkpoint["pages"]
        if len(completed) * max_attempts > max_requests:
            raise HistoryError("request_budget", "checkpoint exceeds the configured request budget")
        fetched_rows = 0
        for page in completed:
            try:
                fetched_rows += len(json.loads((self.raw_dir / f"{page['sha256']}.json").read_bytes()))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise HistoryError("invalid_checkpoint", "checkpoint raw page is unreadable") from exc
        if fetched_rows > max_rows:
            raise HistoryError("row_budget", "checkpoint exceeds the configured row budget")
        for request in requests[len(completed):]:
            if time.monotonic() > deadline:
                raise HistoryError("runtime_cap", "historical acquisition exceeded the runtime cap")
            response = self._fetch_page(
                transport,
                request,
                wait=wait,
                max_attempts=max_attempts,
                max_response_bytes=HISTORY_MAX_RESPONSE_BYTES,
                deadline=deadline,
            )
            try:
                rows = json.loads(response.body)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise HistoryError("invalid_response", "source page is not UTF-8 JSON") from exc
            if not isinstance(rows, list):
                raise HistoryError("invalid_response", "kline page must be a JSON array")
            if len(rows) > request.limit:
                raise HistoryError("invalid_response", "source returned more rows than the requested page limit")
            fetched_rows += len(rows)
            if fetched_rows > max_rows:
                raise HistoryError("row_budget", "historical response exceeds the configured row budget")
            page_hash = self._write_raw_page(response.body)
            completed.append({"page_index": request.page_index, "sha256": page_hash, "captured_at": response.received_at})
            checkpoint["pages"] = completed
            self._write_json_atomic(checkpoint_path, checkpoint)
        if time.monotonic() > deadline:
            raise HistoryError("runtime_cap", "historical acquisition exceeded the runtime cap")
        page_rows = []
        for item in completed:
            raw = (self.raw_dir / f"{item['sha256']}.json").read_bytes()
            page_rows.append({"rows": json.loads(raw), "captured_at": item["captured_at"], "page_sha256": item["sha256"]})
        result = self._ingest_pages(
            page_rows, captured_at=None, as_of_ms=as_of_ms,
            requested_start_ms=start_time_ms, requested_end_ms=end_time_ms_exclusive,
            endpoint_class="public-market-data", source_identity=SOURCE_ID, network_requests=len(completed),
        )
        checkpoint["status"] = "complete"
        checkpoint["manifest_id"] = result.manifest_id
        self._write_json_atomic(checkpoint_path, checkpoint)
        return result

    def _new_checkpoint(self, checkpoint_id: str, requests: tuple[PageRequest, ...], page_size: int) -> dict[str, Any]:
        return {
            "schema": "market-os.btc-history-checkpoint.v1",
            "checkpoint_id": checkpoint_id,
            "requested_start_ms": requests[0].start_time_ms,
            "requested_end_ms_exclusive": requests[-1].end_time_ms + 1,
            "page_size": page_size,
            "pages": [],
            "status": "in_progress",
        }

    def _read_checkpoint(self, path: Path, checkpoint_id: str, requests: tuple[PageRequest, ...], page_size: int) -> dict[str, Any]:
        if not path.exists():
            return self._new_checkpoint(checkpoint_id, requests, page_size)
        value = json.loads(path.read_text(encoding="utf-8"))
        expected = self._new_checkpoint(checkpoint_id, requests, page_size)
        if value.get("checkpoint_id") != checkpoint_id or value.get("requested_start_ms") != expected["requested_start_ms"] or value.get("requested_end_ms_exclusive") != expected["requested_end_ms_exclusive"] or value.get("page_size") != page_size:
            raise HistoryError("checkpoint_mismatch", "checkpoint does not match requested range")
        if value.get("status") not in {"in_progress", "complete"} or not isinstance(value.get("pages"), list) or len(value["pages"]) > len(requests):
            raise HistoryError("invalid_checkpoint", "checkpoint content is invalid")
        for page in value["pages"]:
            if not (self.raw_dir / f"{page['sha256']}.json").is_file():
                raise HistoryError("invalid_checkpoint", "checkpoint references a missing raw page")
        return value

    @staticmethod
    def _fetch_page(
        transport: HistoricalTransport,
        request: PageRequest,
        *,
        wait: Callable[[float], None],
        max_attempts: int = MAX_ATTEMPTS,
        max_response_bytes: int = HISTORY_MAX_RESPONSE_BYTES,
        deadline: float | None = None,
    ) -> HttpResponse:
        for attempt in range(max_attempts):
            if deadline is not None and time.monotonic() > deadline:
                raise HistoryError("runtime_cap", "historical acquisition exceeded the runtime cap")
            try:
                response = transport.fetch_page(request)
            except (TimeoutError, OSError) as exc:
                if attempt + 1 == max_attempts:
                    raise HistoryError("retry_exhausted", "historical page retry limit exhausted") from exc
                continue
            if len(response.body) > max_response_bytes:
                raise HistoryError("response_too_large", "historical response exceeds the bounded byte limit")
            if 200 <= response.status < 300:
                _parse_utc(response.received_at, "received_at")
                return response
            error = classify_http_failure(response.status, response.headers)
            if error.code == "ip_banned" or error.code == "source_rejected":
                raise error
            if attempt + 1 == max_attempts:
                raise HistoryError(
                    "retry_exhausted",
                    f"historical page retry limit exhausted after {error.code}",
                    retry_after=error.retry_after,
                ) from error
            if error.code == "rate_limited":
                if error.retry_after is None or error.retry_after > MAX_RETRY_AFTER_SECONDS:
                    raise HistoryError("retry_after_exceeds_policy", "Retry-After missing or exceeds 60-second local cap", retry_after=error.retry_after)
                wait(error.retry_after)
        raise HistoryError("retry_exhausted", "historical page retry limit exhausted")

    def _ingest_pages(
        self,
        pages: list[Any],
        *,
        captured_at: str | None,
        as_of_ms: int,
        requested_start_ms: int,
        requested_end_ms: int,
        endpoint_class: str,
        source_identity: str,
        network_requests: int = 0,
    ) -> IngestResult:
        if len(pages) > MAX_PAGES:
            raise HistoryError("page_limit", f"ingestion exceeds {MAX_PAGES} pages")
        page_refs: list[dict[str, Any]] = []
        rows_for_classification: list[dict[str, Any]] = []
        raw_records: list[dict[str, Any]] = []
        for page_index, page in enumerate(pages):
            if isinstance(page, dict) and "rows" in page:
                rows = page["rows"]
                received_at = page.get("captured_at") or captured_at
                raw_bytes = (self.raw_dir / f"{page['page_sha256']}.json").read_bytes() if "page_sha256" in page else _json_bytes(rows)
            else:
                rows = page
                received_at = captured_at
                raw_bytes = _json_bytes(rows)
            if not isinstance(rows, list) or len(rows) > MAX_PAGE_SIZE:
                raise HistoryError("invalid_page", f"page {page_index} must be an array of at most {MAX_PAGE_SIZE} rows")
            _parse_utc(received_at, "received_at")
            page_hash = self._write_raw_page(raw_bytes)
            page_refs.append({"page_index": page_index, "sha256": page_hash, "captured_at": received_at, "row_count": len(rows)})
            for row_index, row in enumerate(rows):
                record_fp = _sha(_json_bytes(row))
                raw_records.append({
                    "page_index": page_index, "row_index": row_index, "page_sha256": page_hash,
                    "record_fingerprint": record_fp, "payload_json": _json_bytes(row).decode(),
                    "received_at": received_at,
                })
                item: dict[str, Any] = {"record": row, "record_fingerprint": record_fp, "page_sha256": page_hash, "page_index": page_index, "row_index": row_index, "received_at": received_at}
                try:
                    candle, ancillary = parse_kline_row(row, received_at=received_at, as_of_ms=as_of_ms, source_record_fingerprint=record_fp)
                    item.update(status="eligible", candle=candle, ancillary=ancillary)
                    if candle.open_time:
                        open_ms = _epoch_ms(candle.open_time)
                        item["open_time_ms"] = open_ms
                        if not requested_start_ms <= open_ms < requested_end_ms:
                            item["status"] = "outside_range"
                    else:
                        item["status"] = "invalid"
                except HistoryError as exc:
                    item.update(status=exc.code, reason=str(exc), open_time_ms=_row_open_ms(row))
                except (ContractError, ValueError, TypeError) as exc:
                    item.update(status="invalid", reason=str(exc), open_time_ms=_row_open_ms(row))
                rows_for_classification.append(item)

        canonical, outcomes = _classify_rows(rows_for_classification)
        existing = self._find_superset_dataset(canonical)
        if existing is not None:
            canonical_fingerprint = existing["canonical_fingerprint"]
            dataset_revision = existing["dataset_revision"]
            canonical = [{"candle": _candle_from_row(row), "open_time_ms": row["open_time_ms"], "record_fingerprint": row["canonical_fingerprint"], "page_sha256": "existing"} for row in self.inspect_candles(dataset_revision)]
        else:
            canonical_fingerprint = _sha(_json_bytes([_canonical_content(item["candle"]) for item in canonical]))
            dataset_revision = f"btc-history-{canonical_fingerprint[:20]}"
        run_raw_fingerprint = _sha(_json_bytes(sorted(item["sha256"] for item in page_refs)))
        outcome_fingerprint = _sha(_json_bytes(outcomes))
        run_id = _sha(_json_bytes({
            "source": source_identity, "start": requested_start_ms,
            "end": requested_end_ms, "raw": run_raw_fingerprint,
            "outcomes": outcome_fingerprint,
        }))
        manifest_id = f"btc-history-manifest-{_sha(_json_bytes({'run': run_id, 'dataset': dataset_revision}))[:20]}"
        first_open = min((item["open_time_ms"] for item in canonical), default=None)
        last_close = max((_epoch_ms(item["candle"].close_time) for item in canonical), default=None)
        gaps = _gaps(canonical)
        canonicalized_at = max((item["candle"].availability_timestamp for item in canonical), default=(captured_at or "1970-01-01T00:00:00+00:00"))
        parents = self._parent_revisions(canonical)
        parquet_path = f"datasets/{dataset_revision}/candles.parquet"
        absolute_parquet_path = self.root / parquet_path
        absolute_parquet_path.parent.mkdir(parents=True, exist_ok=True)
        if not absolute_parquet_path.exists():
            table = _parquet_table(canonical)
            self._atomic_parquet(absolute_parquet_path, table)
        parquet_sha256 = _sha(absolute_parquet_path.read_bytes())
        manifest = {
            "schema": "market-os.btc-history-manifest.v1",
            "api_version": HISTORY_VERSION,
            "contract_version": BTC_API_VERSION,
            "manifest_id": manifest_id,
            "run_id": run_id,
            "dataset_revision": dataset_revision,
            "symbol": BTC_SYMBOL,
            "venue": "BINANCE_SPOT",
            "interval": "1m",
            "source_identity": source_identity,
            "endpoint_class": endpoint_class,
            "endpoint_host": SOURCE_HOST if endpoint_class == "public-market-data" else None,
            "network_requests": network_requests,
            "requested_start_ms": requested_start_ms,
            "requested_end_ms_exclusive": requested_end_ms,
            "observed_start_ms": first_open,
            "observed_end_ms_exclusive": last_close + 1 if last_close is not None else None,
            "source_timestamp_min": min((item["candle"].source_timestamp for item in canonical), default=None),
            "source_timestamp_max": max((item["candle"].source_timestamp for item in canonical), default=None),
            "receipt_timestamp_min": min((item["received_at"] for item in rows_for_classification), default=None),
            "receipt_timestamp_max": max((item["received_at"] for item in rows_for_classification), default=None),
            "availability_timestamp_max": max((item["candle"].availability_timestamp for item in canonical), default=None),
            "canonicalization_timestamp": canonicalized_at,
            "raw_fingerprint": run_raw_fingerprint,
            "raw_page_fingerprints": [item["sha256"] for item in page_refs],
            "canonical_fingerprint": canonical_fingerprint,
            "outcome_fingerprint": outcome_fingerprint,
            "canonical_candle_count": len(canonical),
            "raw_record_count": len(raw_records),
            "outcome_counts": _count_outcomes(outcomes),
            "gaps": gaps,
            "parent_revisions": parents,
            "parquet_path": parquet_path,
            "parquet_sha256": parquet_sha256,
            "package_versions": {"duckdb": duckdb.__version__, "pyarrow": pa.__version__},
            "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
        }
        manifest_raw = _json_bytes(manifest)
        manifest_path = self.manifest_dir / f"{manifest_id}.json"
        self._write_immutable_bytes(manifest_path, manifest_raw)
        self._commit_catalog(
            dataset_revision, canonical_fingerprint, parquet_path, parquet_sha256,
            canonical, page_refs, raw_records, outcomes, manifest, _sha(manifest_raw),
        )
        return IngestResult(dataset_revision, manifest_id, canonical_fingerprint, len(canonical))

    def _commit_catalog(self, revision: str, canonical_fp: str, parquet_path: str, parquet_sha: str, canonical: list[dict[str, Any]], pages: list[dict[str, Any]], raw_records: list[dict[str, Any]], outcomes: list[dict[str, Any]], manifest: dict[str, Any], manifest_sha: str) -> None:
        with self._connect() as db:
            db.execute("BEGIN TRANSACTION")
            try:
                db.execute("""
                    INSERT INTO datasets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (dataset_revision) DO NOTHING
                """, [revision, BTC_SYMBOL, "BINANCE_SPOT", "1m", canonical_fp, parquet_path, parquet_sha, len(canonical), manifest["observed_start_ms"] or 0, manifest["observed_end_ms_exclusive"] or 0, BTC_API_VERSION])
                catalog = db.execute("SELECT canonical_fingerprint, parquet_sha256 FROM datasets WHERE dataset_revision=?", [revision]).fetchone()
                if catalog != (canonical_fp, parquet_sha):
                    raise HistoryError("dataset_revision_conflict", "existing dataset revision points to different canonical bytes")
                for page in pages:
                    db.execute("INSERT INTO raw_pages VALUES (?, ?, ?, ?, ?) ON CONFLICT (page_sha256) DO NOTHING", [page["sha256"], str(self.raw_dir / f"{page['sha256']}.json"), (self.raw_dir / f"{page['sha256']}.json").stat().st_size, manifest["source_identity"], page["captured_at"]])
                db.execute("""
                    INSERT INTO ingestion_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (manifest_id) DO NOTHING
                """, [manifest["manifest_id"], revision, manifest["run_id"], manifest["raw_fingerprint"], str(self.manifest_dir / f"{manifest['manifest_id']}.json"), manifest_sha, manifest["requested_start_ms"], manifest["requested_end_ms_exclusive"], manifest["network_requests"]])
                for index, record in enumerate(raw_records):
                    db.execute("""
                        INSERT INTO run_provenance VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT (manifest_id, raw_page_sha256, row_index) DO NOTHING
                    """, [manifest["manifest_id"], record["page_sha256"], record["row_index"], record["record_fingerprint"], record["payload_json"]])
                    outcome = outcomes[index]
                    db.execute("""
                        INSERT INTO run_outcomes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (manifest_id, outcome_index) DO NOTHING
                    """, [manifest["manifest_id"], index, record["page_sha256"], record["row_index"], record["record_fingerprint"], outcome["open_time_ms"], outcome["status"], outcome.get("reason"), outcome["accepted_canonical"]])
                for item in canonical:
                    if item["page_sha256"] == "existing":
                        continue
                    db.execute("""
                        INSERT INTO dataset_provenance VALUES (?, ?, ?, ?)
                        ON CONFLICT DO NOTHING
                    """, [revision, item["open_time_ms"], item["record_fingerprint"], item["page_sha256"]])
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise

    def inspect_datasets(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT dataset_revision, symbol, venue, interval, canonical_fingerprint, parquet_path, parquet_sha256, candle_count, first_open_time_ms, last_close_time_ms FROM datasets ORDER BY dataset_revision").fetchall()
        names = ("dataset_revision", "symbol", "venue", "interval", "canonical_fingerprint", "parquet_path", "parquet_sha256", "candle_count", "first_open_time_ms", "last_close_time_ms")
        return [dict(zip(names, row)) for row in rows]

    def inspect_manifest(self, dataset_or_manifest_id: str) -> dict[str, Any]:
        if not _DATASET_ID_RE.fullmatch(dataset_or_manifest_id):
            raise KeyError(dataset_or_manifest_id)
        path = self.manifest_dir / f"{dataset_or_manifest_id}.json"
        if path.is_file():
            return self._read_manifest(path)
        dataset = next((item for item in self.inspect_datasets() if item["dataset_revision"] == dataset_or_manifest_id), None)
        with self._connect() as db:
            rows = db.execute("SELECT manifest_path, manifest_sha256 FROM ingestion_runs WHERE dataset_revision=? ORDER BY manifest_id", [dataset_or_manifest_id]).fetchall()
        if not rows:
            raise KeyError(dataset_or_manifest_id)
        manifests = []
        for path_string, digest in rows:
            payload = self._read_manifest(Path(path_string))
            if _sha(_json_bytes(payload)) != digest:
                raise HistoryError("manifest_integrity_error", "manifest hash mismatch")
            manifests.append(payload)
        latest = dict(manifests[-1])
        if dataset is not None:
            latest.update({key: value for key, value in dataset.items() if key not in latest})
        latest["dataset"] = dataset
        latest["ingestion_manifests"] = manifests
        return latest

    @staticmethod
    def _read_manifest(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HistoryError("manifest_integrity_error", f"cannot read manifest: {path.name}") from exc

    def inspect_candles(self, dataset_revision: str, *, start_time_ms: int | None = None, end_time_ms: int | None = None) -> list[dict[str, Any]]:
        dataset = self._dataset_row(dataset_revision)
        path = (self.root / dataset["parquet_path"]).resolve()
        if not path.is_relative_to(self.dataset_dir.resolve()) or not path.is_file():
            raise HistoryError("dataset_integrity_error", "Parquet path is missing or outside dataset storage")
        if _sha(path.read_bytes()) != dataset["parquet_sha256"]:
            raise HistoryError("dataset_integrity_error", "Parquet file hash mismatch")
        query = "SELECT open_time_ms, close_time_ms, open, high, low, close, volume, source_timestamp, received_at, availability_timestamp, canonical_fingerprint FROM read_parquet(?) WHERE 1=1"
        parquet_params: list[Any] = [str(path)]
        if start_time_ms is not None:
            query += " AND open_time_ms >= ?"
            parquet_params.append(start_time_ms)
        if end_time_ms is not None:
            query += " AND open_time_ms < ?"
            parquet_params.append(end_time_ms)
        query += " ORDER BY open_time_ms"
        with self._connect() as db:
            rows = db.execute(query, parquet_params).fetchall()
        fields = ("open_time_ms", "close_time_ms", "open", "high", "low", "close", "volume", "source_timestamp", "received_at", "availability_timestamp", "canonical_fingerprint")
        return [dict(zip(fields, row)) for row in rows]

    def inspect_outcomes(self, dataset_or_manifest_id: str) -> list[dict[str, Any]]:
        manifest_ids = self._manifest_ids(dataset_or_manifest_id)
        with self._connect() as db:
            rows = db.execute("SELECT o.manifest_id, o.outcome_index, o.raw_page_sha256, o.row_index, o.source_record_fingerprint, o.open_time_ms, o.status, o.reason, o.accepted_canonical FROM run_outcomes o WHERE o.manifest_id IN (SELECT * FROM UNNEST(?)) ORDER BY o.manifest_id, o.outcome_index", [manifest_ids]).fetchall()
        fields = ("manifest_id", "outcome_index", "raw_page_sha256", "row_index", "source_record_fingerprint", "open_time_ms", "status", "reason", "accepted_canonical")
        return [dict(zip(fields, row)) for row in rows]

    def inspect_provenance(self, dataset_or_manifest_id: str) -> list[dict[str, Any]]:
        manifest_ids = self._manifest_ids(dataset_or_manifest_id)
        with self._connect() as db:
            rows = db.execute("SELECT p.manifest_id, p.raw_page_sha256, p.row_index, p.source_record_fingerprint, p.payload_json FROM run_provenance p WHERE p.manifest_id IN (SELECT * FROM UNNEST(?)) ORDER BY p.manifest_id, p.raw_page_sha256, p.row_index", [manifest_ids]).fetchall()
        return [{"manifest_id": row[0], "raw_page_sha256": row[1], "row_index": row[2], "source_record_fingerprint": row[3], "payload": json.loads(row[4])} for row in rows]

    def inspect_gaps(self, dataset_or_manifest_id: str) -> list[dict[str, int]]:
        value = self.inspect_manifest(dataset_or_manifest_id)
        manifests = value.get("ingestion_manifests", [value])
        unique = {tuple(gap) for manifest in manifests for gap in manifest["gaps"]}
        return [{"start_time_ms": start, "end_time_ms": end} for start, end in sorted(unique)]

    def replay(self, dataset_revision: str) -> dict[str, Any]:
        dataset = self._dataset_row(dataset_revision)
        path = self.root / dataset["parquet_path"]
        if _sha(path.read_bytes()) != dataset["parquet_sha256"]:
            raise HistoryError("dataset_integrity_error", "Parquet file hash mismatch")
        rows = pq.read_table(path).to_pylist()
        canonical_fp = _sha(_json_bytes([_canonical_from_parquet(row) for row in rows]))
        if canonical_fp != dataset["canonical_fingerprint"]:
            raise HistoryError("dataset_integrity_error", "canonical replay fingerprint mismatch")
        return {"dataset_revision": dataset_revision, "canonical_fingerprint": canonical_fp, "candle_count": len(rows), "replayed": True, "network_requests": 0}

    def _dataset_row(self, revision: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT dataset_revision, symbol, venue, interval, canonical_fingerprint, parquet_path, parquet_sha256, candle_count, first_open_time_ms, last_close_time_ms FROM datasets WHERE dataset_revision=?", [revision]).fetchone()
        if row is None:
            raise KeyError(revision)
        names = ("dataset_revision", "symbol", "venue", "interval", "canonical_fingerprint", "parquet_path", "parquet_sha256", "candle_count", "first_open_time_ms", "last_close_time_ms")
        return dict(zip(names, row))

    def _manifest_ids(self, dataset_or_manifest_id: str) -> list[str]:
        with self._connect() as db:
            rows = db.execute("SELECT manifest_id FROM ingestion_runs WHERE dataset_revision=? OR manifest_id=? ORDER BY manifest_id", [dataset_or_manifest_id, dataset_or_manifest_id]).fetchall()
        ids = [row[0] for row in rows]
        if not ids:
            raise KeyError(dataset_or_manifest_id)
        return ids

    def _parent_revisions(self, canonical: list[dict[str, Any]]) -> list[str]:
        current = {item["open_time_ms"] for item in canonical}
        parents = []
        for dataset in self.inspect_datasets():
            if dataset["candle_count"] >= len(current):
                continue
            try:
                old = {row["open_time_ms"] for row in self.inspect_candles(dataset["dataset_revision"])}
            except HistoryError:
                continue
            if old and old < current:
                parents.append(dataset["dataset_revision"])
        return sorted(parents)

    def _find_superset_dataset(self, canonical: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not canonical:
            return None
        requested = {item["open_time_ms"]: _canonical_content(item["candle"]) for item in canonical}
        for dataset in self.inspect_datasets():
            try:
                stored = {row["open_time_ms"]: _canonical_from_parquet(row) for row in self.inspect_candles(dataset["dataset_revision"])}
            except (KeyError, HistoryError):
                continue
            if all(stored.get(open_time) == value for open_time, value in requested.items()):
                return dataset
        return None

    def _write_raw_page(self, raw: bytes) -> str:
        digest = _sha(raw)
        path = self.raw_dir / f"{digest}.json"
        self._write_immutable_bytes(path, raw)
        return digest

    @staticmethod
    def _write_immutable_bytes(path: Path, raw: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != raw:
                raise HistoryError("immutable_file_conflict", f"immutable path collision: {path.name}")
            return
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
                temp_path = Path(handle.name)
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temp_path, path)
            except FileExistsError:
                if path.read_bytes() != raw:
                    raise HistoryError("immutable_file_conflict", f"immutable path collision: {path.name}")
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    @staticmethod
    def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = _json_bytes(value)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
                temp_path = Path(handle.name)
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            temp_path.replace(path)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    @staticmethod
    def _atomic_parquet(path: Path, table: pa.Table) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".parquet", delete=False) as handle:
            temp_path = Path(handle.name)
        try:
            pq.write_table(table, temp_path, compression="zstd", version="2.6", write_statistics=True)
            try:
                os.link(temp_path, path)
            except FileExistsError:
                if _sha(temp_path.read_bytes()) != _sha(path.read_bytes()):
                    raise HistoryError("immutable_file_conflict", f"Parquet revision collision: {path.name}")
        finally:
            temp_path.unlink(missing_ok=True)


def _row_open_ms(row: Any) -> int | None:
    if isinstance(row, (list, tuple)) and row and isinstance(row[0], int) and not isinstance(row[0], bool):
        return row[0]
    return None


def _canonical_dict(candle: ClosedCandle) -> dict[str, Any]:
    return {
        "open_time_ms": _epoch_ms(candle.open_time),
        "close_time_ms": _epoch_ms(candle.close_time),
        "open": candle.open, "high": candle.high, "low": candle.low,
        "close": candle.close, "volume": candle.volume,
        "source_timestamp": candle.source_timestamp,
        "received_at": candle.received_at,
        "availability_timestamp": candle.availability_timestamp,
        "canonical_fingerprint": candle.candle_fingerprint,
    }


def _canonical_content(candle: ClosedCandle) -> dict[str, Any]:
    value = _canonical_dict(candle)
    return {key: value[key] for key in ("open_time_ms", "close_time_ms", "open", "high", "low", "close", "volume")}


def _canonical_from_parquet(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in ("open_time_ms", "close_time_ms", "open", "high", "low", "close", "volume")}


def _candle_from_row(row: dict[str, Any]) -> ClosedCandle:
    return ClosedCandle(
        BTC_SYMBOL, "1m", _iso_ms(row["open_time_ms"]), _iso_ms(row["close_time_ms"]),
        row["open"], row["high"], row["low"], row["close"], row["volume"],
        row["source_timestamp"], row["received_at"], row["availability_timestamp"],
        row["canonical_fingerprint"], row["canonical_fingerprint"],
    )


def _parquet_table(canonical: list[dict[str, Any]]) -> pa.Table:
    rows = [_canonical_dict(item["candle"]) for item in canonical]
    schema = pa.schema([
        ("open_time_ms", pa.int64()), ("close_time_ms", pa.int64()),
        ("open", pa.float64()), ("high", pa.float64()), ("low", pa.float64()),
        ("close", pa.float64()), ("volume", pa.float64()),
        ("source_timestamp", pa.string()), ("received_at", pa.string()),
        ("availability_timestamp", pa.string()), ("canonical_fingerprint", pa.string()),
    ])
    return pa.Table.from_pylist(rows, schema=schema)


def _classify_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid_by_open: dict[int, list[dict[str, Any]]] = {}
    outcomes: list[dict[str, Any]] = []
    for item in rows:
        status = item["status"]
        open_ms = item.get("open_time_ms")
        outcome_item = {key: value for key, value in item.items() if key not in {"record", "candle", "ancillary"}}
        if status == "eligible":
            valid_by_open.setdefault(open_ms, []).append(item)
            outcomes.append({**outcome_item, "status": "pending", "accepted_canonical": False})
        else:
            outcomes.append({**outcome_item, "accepted_canonical": False})
    outcome_by_key = {(item["page_sha256"], item["row_index"]): index for index, item in enumerate(outcomes)}
    canonical = []
    for open_ms, records in sorted(valid_by_open.items()):
        sorted_records = sorted(records, key=lambda item: (item["candle"].candle_fingerprint, item["record_fingerprint"], item["page_sha256"], item["row_index"]))
        chosen = sorted_records[0]
        canonical.append(chosen)
        for item in records:
            index = outcome_by_key[(item["page_sha256"], item["row_index"])]
            outcome = outcomes[index]
            if item is chosen:
                outcome.update(status="accepted", accepted_canonical=True)
            elif item["candle"].candle_fingerprint == chosen["candle"].candle_fingerprint:
                outcome["status"] = "duplicate"
            else:
                outcome["status"] = "conflict"
                outcome["reason"] = "different canonical OHLCV shares an open time"
    accepted_order = sorted(canonical, key=lambda item: (item["page_index"], item["row_index"]))
    prior = None
    for item in accepted_order:
        if prior is not None and item["open_time_ms"] < prior:
            index = outcome_by_key[(item["page_sha256"], item["row_index"])]
            outcomes[index]["status"] = "out_of_order"
            outcomes[index]["accepted_canonical"] = True
        prior = item["open_time_ms"]
    return canonical, outcomes


def _gaps(canonical: list[dict[str, Any]]) -> list[dict[str, int]]:
    gaps = []
    for previous, current in zip(canonical, canonical[1:]):
        expected = previous["open_time_ms"] + 60_000
        if current["open_time_ms"] > expected:
            gaps.append({"start_time_ms": expected, "end_time_ms": current["open_time_ms"]})
    return gaps


def _count_outcomes(outcomes: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in outcomes:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return dict(sorted(counts.items()))
