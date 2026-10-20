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
  recovery now verifies checkpoint schema/source/dataset identity, requested
  range and caps, contiguous page order, page request identity, raw-page
  SHA-256, row count, and capture timestamp before reuse.
- Canonical Parquet retains numeric `float64` columns for analytical consumers
  plus exact source decimal lexemes for OHLCV. Decimal lexemes participate in
  canonical content and replay fingerprints, so precision differences cannot
  silently collapse into one dataset revision.
- CLI commands support fixture ingestion and read-only manifest/candle/outcome/
  provenance/gap/replay inspection. The existing API has matching read-only
  inspection and fixture-ingest routes.

## Fixture evidence

The B1 fixture contains 13 source rows, including an identical duplicate, a
conflicting same-open-time row, a malformed OHLC row, and missing intervals.
It produces 10 canonical candles, one duplicate outcome, one conflict, one
invalid record, and two visible gaps.
The current implementation regenerates the deterministic synthetic dataset as
revision `btc-history-77e4548a5394b078adee` with canonical fingerprint
`77e4548a5394b078adee6bf57d9d37df55c72fe09eec388a22ba5a5a1b90bfa6`.
The earlier `7e910cbf...` value is stale evidence from the pre-closure
canonicalization and is not treated as a current identity. The current
manifest reports `observed_end_ms_exclusive=1767226320000`, matching the
exclusive one-minute boundary rather than adding one millisecond.
No historical data range or live dataset fingerprint was acquired. The stored
fixture dataset is synthetic and exists only in test temporary directories.

## Dependencies and limits

B1 adds `duckdb>=1.4,<2` and `pyarrow>=18,<27`. They are necessary because the
requested Parquet format and DuckDB catalog are not provided by Python's
standard library or the existing environment. No Polars, pandas, LightGBM,
MLflow, Kafka, Redis, Ray, Docker, web framework, or model dependency was added.

## Defect-closure result

- Hard-disabled Binance transport: **intentional boundary**, retained. A
  separately reviewed enablement boundary is still required; this milestone
  does not enable or exercise it.
- Fingerprint mismatch: **stale documentation/evidence**, reconciled to the
  current implementation above and in the machine-readable U3/B2/U3/B3
  records.
- `observed_end_ms_exclusive` off by one: **confirmed and fixed**.
- Checkpoint integrity: **confirmed and fixed** with identity, ordering, hash,
  row-count, and lineage checks.
- Float64 precision loss: **confirmed and fixed** by preserving exact source
  decimal lexemes in B1 storage and fingerprints while retaining float64
  analytical columns.

No historical data was acquired. Jev, model calls, backtests, and virtual
brokerage remain out of B1.
