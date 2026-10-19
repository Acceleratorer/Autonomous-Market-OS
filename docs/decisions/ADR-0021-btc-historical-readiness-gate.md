# ADR-0021: BTC historical-data authorization and readiness gate

- **Status:** Accepted as a readiness proposal; historical transport remains disabled
- **Date:** 2026-10-19
- **Scope:** BTCUSDT Spot one-minute historical candles before any B1 network ingest

## Decision

Keep Binance historical ingestion refused by default and add a versioned,
offline readiness contract around the existing B1 `HistoryStore` seam. The
contract does not authorize a request by itself. A future run must provide all
of the following:

- an explicit `--allow-historical-ingest` runtime flag;
- a matching `market-os.btc-history-authorization.v1` policy file;
- verified source terms, regional eligibility, and retention rights; and
- the bounded range and caps recorded in that policy file.

The current `BinanceHistoricalTransport` remains hard-disabled, so this
milestone cannot perform historical ingestion even if a caller supplies a
synthetic authorization object in tests.

## Bounded proposal

The first separately reviewed run is limited to:

| Field | Proposal |
|---|---|
| Venue / symbol | Binance Spot / `BTCUSDT` |
| Method / endpoint | `GET https://data-api.binance.vision/api/v3/klines` |
| Interval | `1m` |
| Range | `[2026-09-19T00:00:00Z, 2026-10-19T00:00:00Z)` |
| Final-candle rule | Exclude the candle opening at `2026-10-19T00:00:00Z`; `cutoff_ms` is the first excluded open time |
| Expected rows | 43,200 closed candles |
| Page size | 1,000 rows |
| Maximum pages | 44 |
| Maximum HTTP requests | 44 total, one attempt per page |
| Maximum runtime | 900 seconds |
| Maximum response size | 256 KiB per page |
| Retry behavior | No automatic retry for the initial run; record and stop on failure |

The range is half-open and minute-aligned. Binance's inclusive `endTime` is
derived by the existing B1 planner as `end_ms_exclusive - 1`.

## Purpose and storage policy

The only approved purpose proposed here is local BTC quantitative research and
paper-only simulation. No live signal, order, account, portfolio, or execution
authority is created.

Data would remain in the selected local B1 `HistoryStore` root:

- immutable, SHA-256-addressed raw JSON pages;
- canonical closed-candle Parquet;
- the existing DuckDB catalog;
- manifests, checkpoints, outcomes, provenance, and content fingerprints.

Retention is local-only until explicit user deletion. No backup, upload,
redistribution, or external sharing is enabled by default. Access is limited
to the local operator and the existing read-only inspection surfaces. Raw pages
and canonical data must retain lineage to the source page, request range,
receipt/availability timestamps, and validation outcomes.

## Source and operational facts

The official Binance Spot documentation checked on 2026-10-19 states that:

- public market-data-only REST requests use `https://data-api.binance.vision`;
- `GET /api/v3/klines` is public market data with no API key requirement;
- timestamps are UTC milliseconds by default, klines are ordered
  chronologically, and the kline open time identifies a candle;
- the documented request weight is 2, the default limit is 500, and the
  maximum is 1,000;
- response headers expose IP used-weight values;
- HTTP 429 requires backoff, `Retry-After` is supplied for 429/418, and
  repeated violations can result in HTTP 418 IP bans; and
- HTTP 403 indicates a WAF/security block and must not be bypassed by changing
  hosts or falling back to an authenticated endpoint.

The official terms page returned an HTTP 202 challenge from the current
environment. Terms, regional eligibility, retention, and redistribution rights
therefore remain unresolved and are hard blockers rather than assumed
permissions.

Sources:

- [Market Data Only URLs](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md)
- [Spot REST API](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md)
- [Kline/Candlestick data](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#klinecandlestick-data)
- [IP limits](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#ip-limits)
- [Binance Terms](https://www.binance.com/en/terms) — HTTP 202 challenge; not verified

## Failure, checkpoint, and restart policy

The existing B1 checkpoint and raw-page immutability are reused. A future
approved run must:

- validate symbol, interval, aligned timestamps, closed-candle status, OHLCV,
  duplicates, conflicts, ordering, and gaps;
- reject oversized responses and exceedance of page, row, request, or runtime
  caps;
- persist a completed page before proceeding to the next page;
- resume only with a new explicit approval using a matching checkpoint and
  bounded policy; and
- stop on timeout, 403, 418, 451, malformed response, unexpected source
  behavior, or a missing/over-limit `Retry-After` rather than switching hosts.

## Conditions preventing ingestion

Historical ingestion is not authorized in this ADR because the source terms,
regional eligibility, retention/redistribution rights, and a future explicit
operator approval are unresolved. No historical Binance request is made in the
readiness milestone. Jev remains consumed and is not invoked; U4/B4 and U5/B5
remain outside scope.
