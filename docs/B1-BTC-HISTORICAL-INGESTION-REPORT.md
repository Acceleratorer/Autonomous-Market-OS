# B1 BTC Historical Ingestion Report

**Status:** One bounded Binance Vision archive run completed locally on
2026-11-18. The archive transport remains disabled by default and was enabled
for this run only by the date-bound owner approval. No credentials,
authenticated requests, Jev calls, or trades were used.

**Historical scope note:** This report documents the earlier REST-source review.
The current source decision and separately gated archive adapter are documented
in [U3/B1 historical-data readiness](U3-B1-HISTORICAL-READINESS-REPORT.md).
That policy uses `data.binance.vision`; the legacy `data-api.binance.vision`
route described below is not authorized by it.

## Executed bounded Vision archive run

The owner approved BTCUSDT Spot 1m archives for UTC dates 2026-10-19 through
2026-11-17, personal non-commercial offline/paper research, local-only
retention, and no redistribution, credentials, or trading. The run was
approved for 60 HTTPS requests including checksums, 43,200 rows, 1 MiB per
ZIP, 1 KiB per checksum, 32 MiB total download, 900 seconds, and one attempt
per file. The adapter applied a monotonic deadline during fetch/parse and
checked it before canonical ingestion. Exact total wall-clock runtime was not
saved, and local persistence was not timed against that deadline; do not treat
this report as a single measurement of the entire recovery sequence. The
initial network acquisition CLI attempt returned after 76.7 seconds, within
the cap, after fetching all 60 source objects; it then failed at canonical
ingestion because of the page-size defect. A separate offline recovery attempt
ran for 938.5 seconds and failed without additional requests. The final offline
source validation and rebuild completed in 8.2 seconds with zero additional
requests.

The final local store is `.market_os/btc-history`. It contains 30 ZIPs and 30
checksums (2,093,387 bytes total), all checksum-verified, with 1,440 rows per
day. The registered dataset is `btc-history-9c58a3ac5cfd05c7398e`, with
manifest `btc-history-manifest-6307b278cdc684f4dc42`: 43,200 canonical rows,
43,200 accepted outcomes, and zero gaps. The first and last candle opens are
2026-10-19 00:00 UTC and 2026-11-17 23:59 UTC. Machine-readable execution
details are in
[`evidence/b1-binance-vision-execution-2026-11-18.json`](evidence/b1-binance-vision-execution-2026-11-18.json).

The first CLI invocation fetched and persisted all 60 objects, then exposed a
page-size defect: the shared REST ingest guard rejected a valid 1,440-row daily
archive. The raw objects were retained. An offline rebuild added an
archive-specific 1,440-row allowance and batched DuckDB provenance writes; the
final rebuild processed archives chronologically and made zero additional
HTTPS requests. One provisional manifest from a capped intermediate rebuild
remains unregistered in the local `manifests/` directory; the manifest above is
the cataloged result.

The initial failed ingest did not commit per-response receive times. The final
manifest therefore uses local raw-artifact file timestamps
2026-11-18T04:06:41.552Z through 2026-11-18T04:06:41.662Z as receipt-time
evidence; exact HTTP response timestamps were not retained. Historical candle
open/close timestamps and row values remain source-verified. B2 is a
retrospective chronological diagnostic, not a replay of contemporaneous data
receipt or a paper-execution result.

The 2026-11-18 run used the local workspace path `.market_os/btc-history` on a
fixed local volume. Follow-up hardening now resolves every `HistoryStore` root
and rejects UNC paths, mapped Windows remote drives, and recognized Linux
network mounts before opening or creating store data. The same guard applies
to read-only corpus loading.

The acquisition deadline is now carried through row classification, Parquet
creation, and DuckDB ingestion. Deadline checks before catalog commit roll back
the transaction if synchronous ingest work overruns the cap; a blocking local
operation cannot be preempted, so an overrun may return after 900 seconds but
cannot register a successful dataset. Regression coverage exercises UNC
rejection, fixture path traversal, and expiry during archive ingestion. This
is a code-path hardening result; the historical execution timings above remain
unchanged.

## Historical REST-source review (superseded)

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
This fixture remains synthetic and is separate from the approved Vision
dataset. Its fingerprint is not the real BTCUSDT dataset revision above.

## Dependencies and limits

B1 adds `duckdb>=1.4,<2` and `pyarrow>=18,<27`. They are necessary because the
requested Parquet format and DuckDB catalog are not provided by Python's
standard library or the existing environment. No Polars, pandas, LightGBM,
MLflow, Kafka, Redis, Ray, Docker, web framework, or model dependency was added.

## Defect-closure result

- Binance transport remains disabled by default. The archive route was enabled
  only for the single approved, bounded run documented above; any new range or
  repeat acquisition requires fresh date-bound approval.
- Fingerprint mismatch: **stale documentation/evidence**, reconciled to the
  current implementation above and in the machine-readable U3/B2/U3/B3
  records.
- `observed_end_ms_exclusive` off by one: **confirmed and fixed**.
- Checkpoint integrity: **confirmed and fixed** with identity, ordering, hash,
  row-count, and lineage checks.
- Float64 precision loss: **confirmed and fixed** by preserving exact source
  decimal lexemes in B1 storage and fingerprints while retaining float64
  analytical columns.

B1 acquired no Jev assessments, model calls, backtests, or virtual brokerage
results. The offline B2 diagnostic is documented separately.
