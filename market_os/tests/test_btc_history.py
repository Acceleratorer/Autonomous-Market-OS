from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import threading
from http.server import ThreadingHTTPServer
import urllib.request
import urllib.parse

from market_os.btc_history import (
    BinanceHistoricalTransport,
    EXECUTION_APPROVAL_PHRASE,
    HISTORY_MAX_RESPONSE_BYTES,
    HistoryError,
    HistoryStore,
    HttpResponse,
    classify_http_failure,
    fetch_pages,
    plan_historical_readiness,
    plan_pages,
    parse_kline_row,
    validate_historical_authorization,
    validate_historical_budget,
)
from market_os.api import make_handler
from market_os.store import RunStore
from market_os.workflow import MarketWorkflow

FIXTURE = Path(__file__).parent / "fixtures" / "btc_paper" / "history.json"
MINUTE = 60_000
START = 1_767_225_600_000


def authorized(**overrides):
    value = {
        "schema": "market-os.btc-history-authorization.v1",
        "explicit_approval": True,
        "terms_verified": True,
        "regional_eligibility_verified": True,
        "retention_rights_verified": True,
        "host": "data-api.binance.vision",
        "method": "GET",
        "path": "/api/v3/klines",
        "symbol": "BTCUSDT",
        "interval": "1m",
        "request_weight": 2,
        "authenticated": False,
        "trading": False,
        "websocket": False,
        "account_access": False,
        "orders": False,
        "futures": False,
        "margin": False,
        "credentials": False,
        "max_response_bytes": 256 * 1024,
        "purpose": "local BTC quantitative research and paper-only simulation",
        "retention": "local-only-until-explicit-deletion",
        "expires_at": "2099-01-01T00:00:00+00:00",
    }
    value.update(overrides)
    return value


def test_kline_parser_normalizes_closed_row_and_preserves_raw_fingerprint() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    candle, _ = parse_kline_row(fixture["pages"][0][0], received_at=fixture["received_at"], as_of_ms=fixture["as_of_ms"])
    assert candle.open_time == "2026-01-01T00:00:00.000+00:00"
    assert candle.close_time == "2026-01-01T00:01:00.000+00:00"
    assert candle.source_timestamp == candle.close_time
    assert candle.received_at == fixture["received_at"]
    assert candle.availability_timestamp == "2026-01-01T00:30:01.000+00:00"
    assert len(candle.candle_fingerprint) == 64


def test_kline_parser_rejects_bad_shape_numbers_and_open_candle() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    row = fixture["pages"][0][0]
    with pytest.raises(HistoryError, match="12 fields"):
        parse_kline_row(row[:-1], received_at=fixture["received_at"], as_of_ms=fixture["as_of_ms"])
    invalid = list(row)
    invalid[5] = "-1"
    with pytest.raises(HistoryError, match="volume"):
        parse_kline_row(invalid, received_at=fixture["received_at"], as_of_ms=fixture["as_of_ms"])
    open_row = list(fixture["pages"][0][0])
    open_row[0] = START + 12 * MINUTE
    open_row[6] = open_row[0] + MINUTE - 1
    with pytest.raises(HistoryError, match="has not passed"):
        parse_kline_row(open_row, received_at="2026-01-01T00:12:30+00:00", as_of_ms=START + 12 * MINUTE + 30_000)


def test_page_planner_is_bounded_and_uses_exclusive_end() -> None:
    pages = plan_pages(START, START + 2001 * MINUTE)
    assert len(pages) == 3
    assert pages[0].start_time_ms == START
    assert pages[0].end_time_ms == START + 1000 * MINUTE - 1
    assert pages[-1].end_time_ms == START + 2001 * MINUTE - 1
    with pytest.raises(HistoryError, match="acquisition limit"):
        plan_pages(START, START + 101 * MINUTE, page_size=100, max_pages=1)


def test_historical_readiness_calculates_conservative_30_day_range_and_caps() -> None:
    cutoff = START + 31 * 24 * 60 * MINUTE
    readiness = plan_historical_readiness(cutoff)

    assert readiness["ingestion_allowed"] is False
    assert readiness["requested_end_ms_exclusive"] == cutoff
    assert readiness["excluded_final_candle_open_ms"] == cutoff
    assert readiness["expected_rows"] == 30 * 24 * 60
    assert readiness["expected_pages"] == 44
    assert readiness["max_requests"] == 44
    assert readiness["max_runtime_seconds"] == 900
    assert readiness["storage"]["raw_page_retention"] == "local-only-until-explicit-deletion"
    assert readiness["authorization"]["terms_verified"] is False


def test_historical_budget_rejects_unbounded_or_mismatched_caps() -> None:
    end = START + 30 * 24 * 60 * MINUTE
    plan = validate_historical_budget(
        START,
        end,
        page_size=1000,
        max_pages=44,
        max_requests=44,
        max_rows=43_200,
        max_runtime_seconds=900,
        max_attempts=1,
    )
    assert plan["expected_pages"] == 44
    assert plan["expected_requests"] == 44
    with pytest.raises(HistoryError, match="request budget"):
        validate_historical_budget(
            START,
            end,
            page_size=1000,
            max_pages=44,
            max_requests=43,
            max_rows=43_200,
            max_runtime_seconds=900,
            max_attempts=1,
        )
    with pytest.raises(HistoryError, match="runtime cap"):
        validate_historical_budget(
            START,
            end,
            page_size=1000,
            max_pages=44,
            max_requests=44,
            max_rows=43_200,
            max_runtime_seconds=901,
            max_attempts=1,
        )


def test_historical_acquisition_requires_runtime_approval_before_transport(tmp_path: Path) -> None:
    class CountingTransport:
        approved = True
        calls = 0

        def fetch_page(self, _request):
            self.calls += 1
            raise AssertionError("transport must not be called without approval")

    transport = CountingTransport()
    with pytest.raises(HistoryError, match="allow-historical-ingest"):
        HistoryStore(tmp_path).acquire(START, START + MINUTE, transport=transport)
    assert transport.calls == 0


def test_historical_acquisition_refuses_unverified_source_policy_before_transport(tmp_path: Path) -> None:
    class CountingTransport:
        approved = True
        calls = 0

        def fetch_page(self, _request):
            self.calls += 1
            raise AssertionError("transport must not be called with an unverified policy")

    transport = CountingTransport()
    with pytest.raises(HistoryError, match="authorization"):
        HistoryStore(tmp_path).acquire(
            START,
            START + MINUTE,
            transport=transport,
            allow_historical_ingest=True,
            authorization=authorized(
                requested_start_ms=START,
                requested_end_ms_exclusive=START + MINUTE,
                page_size=1000,
                max_pages=44,
                max_requests=1,
                max_rows=1,
                max_runtime_seconds=900,
                max_attempts=1,
                terms_verified=False,
            ),
            max_requests=1,
            max_rows=1,
            max_runtime_seconds=900,
            max_attempts=1,
        )
    assert transport.calls == 0


def test_valid_policy_is_accepted_without_network() -> None:
    requested = {
        "requested_start_ms": START,
        "requested_end_ms_exclusive": START + MINUTE,
        "page_size": 1000,
        "max_pages": 44,
        "max_requests": 1,
        "max_rows": 1,
        "max_runtime_seconds": 900,
        "max_attempts": 1,
    }
    validate_historical_authorization(authorized(**requested), requested=requested)


def test_valid_policy_creates_approved_transport_without_network(tmp_path: Path) -> None:
    requested = {
        "requested_start_ms": START,
        "requested_end_ms_exclusive": START + MINUTE,
        "page_size": 1000,
        "max_pages": 44,
        "max_requests": 1,
        "max_rows": 1,
        "max_runtime_seconds": 900,
        "max_attempts": 1,
    }
    transport = BinanceHistoricalTransport(
        authorized(**requested),
        EXECUTION_APPROVAL_PHRASE,
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert transport.approved is True
    assert transport.request_count == 0

    with pytest.raises(HistoryError, match="exact B1 historical execution approval"):
        BinanceHistoricalTransport(authorized(**requested), "wrong approval", now=datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_default_transport_requires_exact_execution_approval(tmp_path: Path) -> None:
    requested = {
        "requested_start_ms": START,
        "requested_end_ms_exclusive": START + MINUTE,
        "page_size": 1000,
        "max_pages": 44,
        "max_requests": 1,
        "max_rows": 1,
        "max_runtime_seconds": 900,
        "max_attempts": 1,
    }
    with pytest.raises(HistoryError, match="exact B1 historical execution approval"):
        HistoryStore(tmp_path).acquire(
            START, START + MINUTE,
            allow_historical_ingest=True,
            authorization=authorized(**requested),
            max_requests=1,
            max_rows=1,
        )
    with pytest.raises(HistoryError, match="exact B1 historical execution approval"):
        HistoryStore(tmp_path).acquire(
            START, START + MINUTE,
            allow_historical_ingest=True,
            authorization=authorized(**requested),
            execution_approval=EXECUTION_APPROVAL_PHRASE + " ",
            max_requests=1,
            max_rows=1,
        )


def test_authorization_rejects_unsupported_fields() -> None:
    with pytest.raises(HistoryError, match="unsupported"):
        validate_historical_authorization(authorized(unexpected="value"))


def test_historical_acquisition_enforces_response_size_and_runtime_request_caps(tmp_path: Path) -> None:
    request = plan_pages(START, START + MINUTE)[0]

    class Oversized:
        approved = True

        def fetch_page(self, _request):
            return HttpResponse(200, {}, b"x" * (HISTORY_MAX_RESPONSE_BYTES + 1), "2026-01-01T00:30:00+00:00")

    with pytest.raises(HistoryError, match="response exceeds"):
        HistoryStore(tmp_path / "oversized").acquire(
            START,
            START + MINUTE,
            transport=Oversized(),
            allow_historical_ingest=True,
            authorization=authorized(
                requested_start_ms=START,
                requested_end_ms_exclusive=START + MINUTE,
                page_size=1000,
                max_pages=44,
                max_requests=1,
                max_rows=1,
                max_runtime_seconds=900,
                max_attempts=1,
            ),
            max_requests=1,
            max_rows=1,
            max_runtime_seconds=900,
            max_attempts=1,
        )

    with pytest.raises(HistoryError, match="authorization"):
        HistoryStore(tmp_path / "budget").acquire(
            START,
            START + MINUTE,
            transport=Oversized(),
            allow_historical_ingest=True,
            authorization=authorized(
                requested_start_ms=START,
                requested_end_ms_exclusive=START + MINUTE,
                page_size=1000,
                max_pages=44,
                max_requests=0,
                max_rows=1,
                max_runtime_seconds=900,
                max_attempts=1,
            ),
            max_requests=0,
            max_rows=1,
            max_runtime_seconds=900,
            max_attempts=1,
        )


def test_authorization_requires_future_expiry() -> None:
    with pytest.raises(HistoryError, match="passed|authorization"):
        validate_historical_authorization(authorized(expires_at="2020-01-01T00:00:00+00:00"), now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(HistoryError, match="authorization"):
        validate_historical_authorization({"schema": "market-os.btc-history-authorization.v1"})


def test_transport_builds_only_allowlisted_public_kline_requests() -> None:
    transport = BinanceHistoricalTransport(
        authorized(
            requested_start_ms=START,
            requested_end_ms_exclusive=START + MINUTE,
            page_size=1000,
            max_pages=44,
            max_requests=1,
            max_rows=1,
            max_runtime_seconds=900,
            max_attempts=1,
        ),
        EXECUTION_APPROVAL_PHRASE,
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    request = transport.build_request(plan_pages(START, START + MINUTE)[0])
    assert request.method == "GET"
    assert request.full_url == (
        "https://data-api.binance.vision/api/v3/klines?"
        "symbol=BTCUSDT&interval=1m&startTime=1767225600000&endTime=1767225659999&limit=1000"
    )
    assert all("authorization" not in key.lower() for key in request.headers)

    for attribute, value in (("host", "api.binance.com"), ("path", "/api/v3/ticker/price"), ("method", "POST")):
        altered = BinanceHistoricalTransport(
            authorized(
                requested_start_ms=START,
                requested_end_ms_exclusive=START + MINUTE,
                page_size=1000,
                max_pages=44,
                max_requests=1,
                max_rows=1,
                max_runtime_seconds=900,
                max_attempts=1,
            ),
            EXECUTION_APPROVAL_PHRASE,
            now=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        setattr(altered, attribute, value)
        with pytest.raises(HistoryError, match="allowlist"):
            altered.build_request(plan_pages(START, START + MINUTE)[0])


def test_rate_limit_and_timeout_errors_classify_without_transport() -> None:
    assert classify_http_failure(429, {"Retry-After": "3"}).code == "rate_limited"
    assert classify_http_failure(418, {"Retry-After": "60"}).code == "ip_banned"
    assert classify_http_failure(503, {}).code == "server_error"
    with pytest.raises(HistoryError, match="authorization"):
        BinanceHistoricalTransport({"schema": "market-os.btc-history-authorization.v1"}, EXECUTION_APPROVAL_PHRASE)


def test_bounded_historical_run_stops_on_rate_limit_without_retry_or_wait(tmp_path: Path) -> None:
    class RateLimited:
        approved = True
        calls = 0

        def fetch_page(self, _request):
            self.calls += 1
            return HttpResponse(429, {"Retry-After": "2"}, b"{}", "2026-01-01T00:30:00+00:00")

    transport = RateLimited()
    waits: list[float] = []
    with pytest.raises(HistoryError, match="retry limit exhausted") as failure:
        HistoryStore(tmp_path).acquire(
            START,
            START + MINUTE,
            transport=transport,
            allow_historical_ingest=True,
            authorization=authorized(
                requested_start_ms=START,
                requested_end_ms_exclusive=START + MINUTE,
                page_size=1000,
                max_pages=44,
                max_requests=1,
                max_rows=1,
                max_runtime_seconds=900,
                max_attempts=1,
            ),
            max_requests=1,
            max_rows=1,
            max_runtime_seconds=900,
            max_attempts=1,
            wait=waits.append,
        )
    assert failure.value.retry_after == 2.0
    assert transport.calls == 1
    assert waits == []


def test_injected_transport_retries_5xx_and_rate_limits_but_stops_at_retry_cap() -> None:
    request = plan_pages(START, START + MINUTE)[0]
    waits: list[float] = []

    class Recovering:
        approved = True
        calls = 0

        def fetch_page(self, _request):
            self.calls += 1
            if self.calls == 1:
                return HttpResponse(503, {}, b"{}", "2026-01-01T00:30:00+00:00")
            if self.calls == 2:
                return HttpResponse(429, {"Retry-After": "2"}, b"{}", "2026-01-01T00:30:02+00:00")
            return HttpResponse(200, {}, b"[]", "2026-01-01T00:30:04+00:00")

    result = fetch_pages(Recovering(), (request,), wait=waits.append)
    assert result[0].status == 200
    assert waits == [2.0]

    class AlwaysFail:
        approved = True

        def fetch_page(self, _request):
            return HttpResponse(503, {}, b"{}", "2026-01-01T00:30:00+00:00")

    with pytest.raises(HistoryError) as failure:
        fetch_pages(AlwaysFail(), (request,))
    assert failure.value.code == "retry_exhausted"


def test_fixture_ingestion_persists_parquet_raw_pages_catalog_and_manifest(tmp_path: Path) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    store = HistoryStore(tmp_path)
    result = store.ingest_fixture(fixture)
    manifest = store.inspect_manifest(result.dataset_revision)

    assert result.dataset_revision == manifest["dataset_revision"]
    assert manifest["canonical_candle_count"] == 10
    assert manifest["raw_record_count"] == len(fixture["pages"][0])
    assert manifest["network_requests"] == 0
    assert manifest["source_identity"] == "binance.spot.rest.klines.synthetic-fixture"
    assert manifest["parent_revisions"] == []
    assert (tmp_path / manifest["parquet_path"]).is_file()
    assert len(list((tmp_path / "raw").glob("*.json"))) == 1
    assert store.inspect_outcomes(result.dataset_revision)
    assert len(store.inspect_candles(result.dataset_revision)) == 10
    assert store.replay(result.dataset_revision)["canonical_fingerprint"] == manifest["canonical_fingerprint"]
    assert manifest["observed_end_ms_exclusive"] == START + 12 * MINUTE
    assert store.inspect_candles(result.dataset_revision)[0]["open_decimal"] == "100"


def test_canonical_storage_preserves_source_decimal_lexemes(tmp_path: Path) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    baseline = HistoryStore(tmp_path / "baseline").ingest_fixture(fixture)
    row = fixture["pages"][0][0]
    row[1:6] = [
        "1.0000000000000001",
        "1.0000000000000002",
        "0.9999999999999999",
        "1.0000000000000001",
        "0.0000000000000001",
    ]
    store = HistoryStore(tmp_path)
    result = store.ingest_fixture(fixture)
    candle = store.inspect_candles(result.dataset_revision)[0]
    assert candle["open_decimal"] == "1.0000000000000001"
    assert candle["high_decimal"] == "1.0000000000000002"
    assert candle["low_decimal"] == "0.9999999999999999"
    assert candle["close_decimal"] == "1.0000000000000001"
    assert candle["volume_decimal"] == "0.0000000000000001"
    assert result.canonical_fingerprint != baseline.canonical_fingerprint
    assert store.replay(result.dataset_revision)["replayed"] is True


def test_reingest_and_overlapping_page_are_idempotent_and_keep_raw_immutable(tmp_path: Path) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    store = HistoryStore(tmp_path)
    first = store.ingest_fixture(fixture)
    raw_files_before = sorted(p.name for p in (tmp_path / "raw").glob("*.json"))
    repeated = store.ingest_fixture(fixture)
    assert repeated.dataset_revision == first.dataset_revision
    assert sorted(p.name for p in (tmp_path / "raw").glob("*.json")) == raw_files_before

    overlap = {**fixture, "pages": [[fixture["pages"][0][0]]]}
    overlap["requested_start_ms"] = START
    overlap["requested_end_ms_exclusive"] = START + MINUTE
    overlapped = store.ingest_fixture(overlap)
    assert overlapped.dataset_revision == first.dataset_revision
    assert len(store.inspect_candles(first.dataset_revision)) == 10
    assert len(list((tmp_path / "raw").glob("*.json"))) == len(raw_files_before) + 1


def test_inspection_range_and_no_network_replay(tmp_path: Path) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    store = HistoryStore(tmp_path)
    result = store.ingest_fixture(fixture)
    ranged = store.inspect_candles(result.dataset_revision, start_time_ms=START, end_time_ms=START + 2 * MINUTE)
    assert [row["open_time_ms"] for row in ranged] == [START, START + MINUTE]
    before = list(tmp_path.rglob("*"))
    assert store.replay(result.dataset_revision)["replayed"] is True
    assert list(tmp_path.rglob("*")) == before


def test_pre_closure_parquet_without_decimal_columns_remains_readable(tmp_path: Path) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    store = HistoryStore(tmp_path)
    ingested = store.ingest_fixture(fixture)
    import hashlib
    import pyarrow.parquet as pq
    from market_os.btc_history import _canonical_from_parquet

    dataset = store._dataset_row(ingested.dataset_revision)
    parquet_path = store.root / dataset["parquet_path"]
    table = pq.read_table(parquet_path).drop_columns(
        ["open_decimal", "high_decimal", "low_decimal", "close_decimal", "volume_decimal"]
    )
    pq.write_table(table, parquet_path)
    rows = table.to_pylist()
    canonical = hashlib.sha256(
        json.dumps(
            [
                {
                    key: row[key]
                    for key in ("open_time_ms", "close_time_ms", "open", "high", "low", "close", "volume")
                }
                for row in rows
            ],
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    parquet_sha256 = hashlib.sha256(parquet_path.read_bytes()).hexdigest()
    with store._connect() as db:
        db.execute(
            "UPDATE datasets SET canonical_fingerprint=?, parquet_sha256=? WHERE dataset_revision=?",
            [canonical, parquet_sha256, ingested.dataset_revision],
        )
    candles = store.inspect_candles(ingested.dataset_revision)
    assert candles
    assert candles[0]["open_decimal"] is None
    assert store.replay(ingested.dataset_revision)["replayed"] is True


def test_injected_acquisition_checkpoints_and_resumes_without_refetching_completed_pages(tmp_path: Path) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = fixture["pages"][0]
    start = fixture["requested_start_ms"]
    end = fixture["requested_end_ms_exclusive"]

    class Flaky:
        approved = True

        def __init__(self):
            self.calls: list[int] = []
            self.fail_page_once = True

        def fetch_page(self, request):
            self.calls.append(request.page_index)
            if request.page_index == 1 and self.fail_page_once:
                raise TimeoutError("synthetic timeout")
            page = [row for row in rows if request.start_time_ms <= row[0] <= request.end_time_ms][:request.limit]
            return HttpResponse(200, {}, json.dumps(page).encode(), "2026-01-01T00:30:01+00:00")

    transport = Flaky()
    store = HistoryStore(tmp_path)
    with pytest.raises(HistoryError) as failure:
        store.acquire(start, end, transport=transport, page_size=5, max_pages=44, max_attempts=1, max_requests=44, max_rows=43_200, allow_historical_ingest=True, authorization=authorized(requested_start_ms=start, requested_end_ms_exclusive=end, page_size=5, max_pages=44, max_requests=44, max_rows=43_200, max_runtime_seconds=900, max_attempts=1))
    assert failure.value.code == "retry_exhausted"
    assert transport.calls == [0, 1]
    transport.fail_page_once = False
    result = store.acquire(start, end, transport=transport, page_size=5, max_pages=44, max_attempts=1, max_requests=44, max_rows=43_200, allow_historical_ingest=True, authorization=authorized(requested_start_ms=start, requested_end_ms_exclusive=end, page_size=5, max_pages=44, max_requests=44, max_rows=43_200, max_runtime_seconds=900, max_attempts=1))
    assert result.canonical_count == 10
    assert transport.calls.count(0) == 1
    assert store.replay(result.dataset_revision)["network_requests"] == 0


def test_checkpoint_recovery_rejects_raw_hash_tampering(tmp_path: Path) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = fixture["pages"][0]
    start = fixture["requested_start_ms"]
    end = fixture["requested_end_ms_exclusive"]

    class Flaky:
        approved = True

        def __init__(self):
            self.fail_page_once = True

        def fetch_page(self, request):
            if request.page_index == 1 and self.fail_page_once:
                raise TimeoutError("synthetic timeout")
            page = [row for row in rows if request.start_time_ms <= row[0] <= request.end_time_ms][:request.limit]
            return HttpResponse(200, {}, json.dumps(page).encode(), "2026-01-01T00:30:01+00:00")

    transport = Flaky()
    store = HistoryStore(tmp_path)
    with pytest.raises(HistoryError):
        store.acquire(start, end, transport=transport, page_size=5, max_pages=44, max_attempts=1, max_requests=44, max_rows=43_200, allow_historical_ingest=True, authorization=authorized(requested_start_ms=start, requested_end_ms_exclusive=end, page_size=5, max_pages=44, max_requests=44, max_rows=43_200, max_runtime_seconds=900, max_attempts=1))
    checkpoint = next((tmp_path / "checkpoints").glob("*.json"))
    checkpoint_payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    raw_path = tmp_path / "raw" / f"{checkpoint_payload['pages'][0]['sha256']}.json"
    raw_path.write_bytes(b"[]")
    with pytest.raises(HistoryError, match="hash"):
        store.acquire(start, end, transport=transport, page_size=5, max_pages=44, max_attempts=1, max_requests=44, max_rows=43_200, allow_historical_ingest=True, authorization=authorized(requested_start_ms=start, requested_end_ms_exclusive=end, page_size=5, max_pages=44, max_requests=44, max_rows=43_200, max_runtime_seconds=900, max_attempts=1))


def test_checkpoint_recovery_rejects_page_identity_and_lineage_changes(tmp_path: Path) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = fixture["pages"][0]
    start = fixture["requested_start_ms"]
    end = fixture["requested_end_ms_exclusive"]

    class Flaky:
        approved = True

        def fetch_page(self, request):
            if request.page_index == 1:
                raise TimeoutError("synthetic timeout")
            page = [row for row in rows if request.start_time_ms <= row[0] <= request.end_time_ms][:request.limit]
            return HttpResponse(200, {}, json.dumps(page).encode(), "2026-01-01T00:30:01+00:00")

    authorization = authorized(requested_start_ms=start, requested_end_ms_exclusive=end, page_size=5, max_pages=44, max_requests=44, max_rows=43_200, max_runtime_seconds=900, max_attempts=1)
    store = HistoryStore(tmp_path)
    with pytest.raises(HistoryError):
        store.acquire(start, end, transport=Flaky(), page_size=5, max_pages=44, max_attempts=1, max_requests=44, max_rows=43_200, allow_historical_ingest=True, authorization=authorization)
    checkpoint = next((tmp_path / "checkpoints").glob("*.json"))
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    payload["pages"][0]["page_index"] = 1
    checkpoint.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(HistoryError, match="page"):
        store.acquire(start, end, transport=Flaky(), page_size=5, max_pages=44, max_attempts=1, max_requests=44, max_rows=43_200, allow_historical_ingest=True, authorization=authorization)


def test_disabled_acquisition_cannot_make_a_network_request(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path)
    with pytest.raises(HistoryError, match="source/legal review"):
        store.acquire(START, START + MINUTE)
    assert not list((tmp_path / "raw").glob("*.json"))


def test_fixture_ingest_cli_and_api_inspection_are_read_only(tmp_path: Path, capsys) -> None:
    from market_os.cli import main

    assert main(["btc-paper", "ingest", "--fixture", str(FIXTURE), "--store-root", str(tmp_path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    dataset_revision = payload["dataset_revision"]
    assert main(["btc-paper", "inspect", dataset_revision, "--resource", "manifest", "--store-root", str(tmp_path)]) == 0
    assert "dataset_revision" in json.loads(capsys.readouterr().out)

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(tmp_path / "workflow"))))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = json.dumps({"store_root": str(tmp_path / "api"), "fixture": json.loads(FIXTURE.read_text(encoding="utf-8"))}).encode()
        request = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/v1/btc/history/ingest", data=body, headers={"Content-Type": "application/json"}, method="POST")
        response = json.loads(urllib.request.urlopen(request, timeout=2).read())
        inspected = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/v1/btc/history/{response['dataset_revision']}/replay?store_root={urllib.parse.quote(str(tmp_path / 'api'))}", timeout=2).read())
        assert inspected["replayed"] is True
    finally:
        server.shutdown()
        thread.join(timeout=2)
def test_historical_readiness_cli_and_api_are_offline_and_block_ingest(tmp_path: Path, capsys) -> None:
    from market_os.cli import main

    cutoff = START + 31 * 24 * 60 * MINUTE
    assert main(["btc-paper", "historical-readiness", "--cutoff-ms", str(cutoff)]) == 0
    readiness = json.loads(capsys.readouterr().out)
    assert readiness["schema"] == "market-os.btc-history-readiness.v1"
    assert readiness["ingestion_allowed"] is False
    assert readiness["network_requests"] == 0

    with pytest.raises(SystemExit, match="allow-historical-ingest"):
        main(["btc-paper", "acquire", "--start-ms", str(START), "--end-ms", str(START + MINUTE), "--store-root", str(tmp_path)])
    assert capsys.readouterr().out == ""

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(MarketWorkflow(RunStore(tmp_path / "workflow"))))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/v1/btc/history/readiness?cutoff-ms={cutoff}"
        response = json.loads(urllib.request.urlopen(url, timeout=2).read())
        assert response["expected_pages"] == 44
        assert response["ingestion_allowed"] is False
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_missing_and_invalid_policy_refuse_before_transport(tmp_path: Path) -> None:
    class CountingTransport:
        approved = True
        calls = 0

        def fetch_page(self, _request):
            self.calls += 1
            raise AssertionError("transport must not be called")

    transport = CountingTransport()
    with pytest.raises(HistoryError, match="authorization"):
        HistoryStore(tmp_path / "missing").acquire(
            START, START + MINUTE, transport=transport,
            allow_historical_ingest=True, authorization=None,
            max_requests=1, max_rows=1,
        )
    with pytest.raises(HistoryError, match="authorization"):
        HistoryStore(tmp_path / "invalid").acquire(
            START, START + MINUTE, transport=transport,
            allow_historical_ingest=True, authorization={"schema": "wrong"},
            max_requests=1, max_rows=1,
        )
    assert transport.calls == 0


def test_acquire_cli_requires_exact_approved_policy_path(tmp_path: Path, capsys) -> None:
    from market_os.cli import main

    with pytest.raises(SystemExit, match="approved-policy.json"):
        main([
            "btc-paper", "acquire", "--start-ms", str(START), "--end-ms", str(START + MINUTE),
            "--allow-historical-ingest", "--authorization-file", str(tmp_path / "other.json"),
            "--store-root", str(tmp_path / "store"),
        ])
    assert capsys.readouterr().out == ""
