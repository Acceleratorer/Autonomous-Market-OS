# U3/B1 BTC historical-data authorization and dataset-readiness report

**Status:** Reviewed opt-in transport implemented; historical ingestion not
authorized or executed. **Scope:** Binance BTCUSDT Spot 1-minute closed-candle
dataset proposal only. Jev, U4/B4, U5/B5, and trading are out of scope.

## Decision

**Do not ingest yet.** The B1 transport remains disabled by default. A future
acquisition requires the exact repository-root policy, the explicit runtime
flag, and the separate exact execution approval phrase. The readiness contract
makes the future request range, row/page/request/runtime caps, retention
metadata, and approval prerequisites inspectable without network access.
Binance public market-data availability is not treated as permission to retain
or redistribute data.

## Official source re-check

Official Binance materials rechecked on 2026-10-22:

- [Market Data Only URLs](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md)
  identifies `https://data-api.binance.vision` and public
  `GET /api/v3/klines`.
- [Spot REST API](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md)
  documents UTC millisecond timestamps, chronological responses, kline open
  time identity, request weight 2, and the 500 default / 1,000 maximum kline
  limit.
- The same REST documentation states that response headers expose
  `X-MBX-USED-WEIGHT-*`, HTTP 429 requires backoff, `Retry-After` is supplied
  on 429/418, and continued violations can cause HTTP 418 IP bans. HTTP 403
  is a WAF/security block; HTTP 5xx has unknown provider-side operation status.
- [Binance Terms](https://www.binance.com/en/terms) returned HTTP 202 from
  this environment and was not treated as verified.

The source facts support a bounded public-data design, but terms, regional
eligibility, retention, and redistribution rights remain unresolved blockers.

## Proposed first range and hard caps

The readiness command accepts an explicit UTC minute-aligned cutoff. It excludes
the candle opening at `cutoff` and proposes the preceding 30 UTC calendar days
using a half-open interval:

```text
[2026-09-19T00:00:00Z, 2026-10-19T00:00:00Z)
```

| Limit | Value |
|---|---:|
| Expected closed candles | 43,200 |
| Rows per page | 1,000 |
| Maximum pages | 44 |
| Maximum HTTP requests | 44 |
| Attempts per page | 1 |
| Maximum runtime | 900 seconds |
| Maximum response bytes | 262,144 |

The existing `plan_pages()` converts each exclusive end to Binance's inclusive
`endTime` by subtracting one millisecond. No candle opening at the cutoff is
requested, and no final/open candle is accepted by the existing
`parse_kline_row()` cutoff validation.

## Reused implementation and persistence

No second ingestion framework was created. The reviewed opt-in transport and
readiness gate extend
`market_os/btc_history.py` and reuses:

- `HistoryStore`, `PageRequest`, `HistoricalTransport`, and the bounded
  `BinanceHistoricalTransport`;
- B0 `ClosedCandle` validation and B1 duplicate/conflict/gap/out-of-order
  classification;
- immutable raw-page SHA-256 storage;
- canonical Parquet, DuckDB catalog, manifests, checkpoints, and replay.

The future store root is selected explicitly by the operator. Raw pages and
canonical data are local-only until explicit deletion, with no backup, upload,
or redistribution by default. Read-only inspection cannot trigger provider
requests.

The future CLI shape is:

```text
python -m market_os.cli btc-paper historical-readiness --cutoff-ms <UTC-minute-ms>
python -m market_os.cli btc-paper acquire \
  --start-ms <start-ms> --end-ms <exclusive-end-ms> \
  --page-size 1000 --max-pages 44 --max-requests 44 \
  --max-rows 43200 --max-runtime-seconds 900 --max-attempts 1 \
  --allow-historical-ingest --authorization-file <approved-policy.json> \
  --execution-approval "<exact B1 approval phrase>" \
  --store-root <local-b1-root>
```

The second command is a future command shape, not an instruction or an
authorization for this milestone. It fails closed unless the policy is valid,
unexpired, exactly bounded, and the separate execution phrase matches byte for
byte. No acquisition was run in this review.

The read-only API inspection surface is:

```text
GET /v1/btc/history/readiness?cutoff-ms=<UTC-minute-ms>
```

## Readiness tests

Offline tests cover explicit cutoff/date-range calculation, final-candle
exclusion, exact page/request/row/runtime budgets, response-size rejection,
approval-flag and execution-approval refusal before transport, checkpoint/resume behavior, existing
duplicate/conflict/gap/out-of-order handling, closed-candle validation, and
zero-network CLI/API readiness inspection. Existing B0/B1 tests remain green;
the focused readiness/B1 suite is 30 tests after the final transport-boundary
hardening.

## Verification

Verified locally without provider access:

- `python -m pytest market_os/tests/test_btc_history.py -q`: **30 passed**.
- `python -m pytest market_os/tests/test_btc_paper.py market_os/tests/test_btc_paper_cli.py market_os/tests/test_btc_history.py -q`: **44 passed**.
- `python -m pytest market_os/tests/test_btc_features.py market_os/tests/test_btc_jev_evaluation.py market_os/tests/test_btc_connectivity.py -q`: **58 passed** with `TYPESAFE_API_KEY` unset.
- `python -m pytest -q`: **273 passed, 0 failed, 1 skipped** with `TYPESAFE_API_KEY` unset.
- `python -m compileall -q market_os`: passed.
- `python scripts/ci_checks.py validate-evidence`: passed for 22 evidence JSON files.
- `python scripts/ci_checks.py secret-scan`: passed.
- `python -m pip check`: no broken requirements.
- `python -m market_os.cli btc-paper historical-readiness --cutoff-ms 1792368000000`: passed with `network_requests=0`.
- Readiness CLI/API offline smoke, replay/fingerprint checks, and `git diff --check`: passed.

No historical Binance request, Jev request, credential use, or trade occurred
during this milestone. The opt-in transport was exercised only through local
request-construction and policy-validation tests.

## Unresolved risks

- Legal terms, regional restrictions/eligibility, retention, and redistribution
  rights require an operator/legal decision from an authoritative source.
- Binance request weights, limits, headers, and endpoint behavior can drift;
  a future run must re-check the official documentation and stop on ambiguity.
- A 30-day window may still be insufficient for stable leakage-safe B2/B3
  calibration and test estimates; it is a bounded proposal, not a quality
  guarantee.
- Raw-page retention and backup choices affect privacy, storage, and audit
  obligations.
- No historical source response, dataset fingerprint, gap profile, or regional
  availability has been observed in this milestone.

## Exact next approval required

Before any historical request, obtain this separate explicit approval after
the source/terms/region/retention review is complete:

```text
APPROVE B1 HISTORICAL INGEST: BTCUSDT Spot 1m, proposed 30 UTC days, 44 pages, 44 maximum HTTP requests, 1000 rows/page, 900-second runtime cap, local-only retention, no retry after failure, no authenticated Binance access
```
