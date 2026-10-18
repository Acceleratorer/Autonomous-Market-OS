# B1 BTC Historical Ingestion Report

**Status:** Offline B1 storage/replay implementation complete; public transport
disabled. No Binance candle request, authenticated request, credential, or live
market-data connection was made.

## Source and network decision

The candidate source is Binance Spot REST `GET /api/v3/klines` on
`data-api.binance.vision`, the documented market-data-only host. Official docs
state that klines are identified by open time, support one-minute intervals,
use UTC time bounds, have request weight 2, and allow at most 1,000 rows per
request. Official docs also describe IP-based used-weight headers, HTTP 429
backoff with `Retry-After`, and HTTP 418 bans after repeated violations.

Terms, regional eligibility, retention, and redistribution rights were not
verifiable: Binance legal pages returned HTTP 202 in the primary-source check.
Therefore the transport is a hard-disabled seam that raises
`source_not_approved` before opening a connection. The exact policy and source
citations are in `docs/decisions/ADR-0016-btc-b1-source-storage-policy.md`.

## Offline implementation

- Source-shaped 12-field kline pages are parsed through B0 `ClosedCandle` rules.
- Raw pages are content-addressed immutable JSON files under `raw/`.
- Canonical closed candles are stored as compressed Parquet snapshots.
- DuckDB stores dataset rows, ingestion manifests, raw-page references,
  per-record provenance, outcomes, and dataset provenance.
- Dataset revisions derive from canonical content, not request/page boundaries.
  Repeated and overlapping fixture ingestion reuses the existing revision while
  retaining new raw page evidence and ingestion-run metadata.
- Manifests record requested/observed ranges, source/receipt/availability and
  canonicalization timestamps, raw/canonical/outcome fingerprints, gaps,
  duplicate/conflict/invalid outcomes, parent revisions, package versions,
  Parquet hash/path, and network request count.
- Checkpoint files are bounded and resumable for a future approved transport;
  the current transport cannot create them because approval is absent.
- CLI commands support fixture ingestion and read-only manifest/candle/outcome/
  provenance/gap/replay inspection. The existing API has matching read-only
  inspection and fixture-ingest routes.

## Fixture evidence

The B1 fixture contains 13 source rows, including an identical duplicate, a
conflicting same-open-time row, a malformed OHLC row, and missing intervals.
It produces 10 canonical candles, one duplicate outcome, one conflict, one
invalid record, and two visible gaps.
The deterministic synthetic dataset revision is
`btc-history-7e910cbf4c3484a34249` with canonical fingerprint
`7e910cbf4c3484a34249d59901b284069a2fae23ea10e7fde38951070327f866`.
No historical data range or live dataset fingerprint was acquired. The stored
fixture dataset is synthetic and exists only in test temporary directories.

## Dependencies and limits

B1 adds `duckdb>=1.4,<2` and `pyarrow>=18,<27`. They are necessary because the
requested Parquet format and DuckDB catalog are not provided by Python's
standard library or the existing environment. No Polars, pandas, LightGBM,
MLflow, Kafka, Redis, Ray, Docker, web framework, or model dependency was added.

The next milestone is **B2: deterministic feature/label materialization and
chronological numerical baselines**, with calibration and walk-forward evidence;
Jev, model calls, backtests, and virtual brokerage remain out of B1.
