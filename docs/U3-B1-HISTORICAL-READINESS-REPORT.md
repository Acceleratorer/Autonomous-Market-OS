# U3/B1 BTC historical-data readiness

**Status:** The readiness gates were closed for one approved run on
2026-11-18. Binance Vision transport remains disabled by default; the approved
BTCUSDT/1m archive range was downloaded once, kept local, and indexed for
offline research.

**Execution result:** UTC dates 2026-10-19 through 2026-11-17 produced 30
checksum-verified daily archives, 43,200 canonical candles, zero gaps, and 60
HTTPS requests. Dataset revision:
`btc-history-9c58a3ac5cfd05c7398e`; manifest:
`btc-history-manifest-6307b278cdc684f4dc42`. The acquisition evidence and
recovery/timestamp caveats are in
[`evidence/b1-binance-vision-execution-2026-11-18.json`](evidence/b1-binance-vision-execution-2026-11-18.json).

## Decision

Use Binance Vision's daily Spot archives at `data.binance.vision` for the
bounded BTCUSDT/1m dataset. The archive host is named directly in the
[Binance Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md).
The old REST route on `data-api.binance.vision` remains a separate legacy
adapter and is not authorized by this archive policy.

The terms limit use to listed non-commercial scopes, including purely
personal, non-production historical backtesting. Commercial utilization
requires a separate written license. Raw datasets and derivative feeds cannot
be sold or commercially exploited, and redistributed derivatives must retain
the stated attribution and license. This project can use these archives only
for private offline research and paper simulation within those terms. This is
a source-policy decision, not legal advice.

The owner confirmed Vietnam as the access region. A Binance Public Data
repository contributor answered that the Vision Dataset Terms apply wherever
the user lives, in response to a Japan-specific question; this is repository
maintainer guidance rather than a Vietnam-specific legal ruling. The official
Terms link to a prohibited-country PDF updated 2026-01-05; that published list
does not name Vietnam. The live country page is JavaScript-rendered, so this
does not prove the list has not changed since that PDF. Recheck the official
linked list immediately before acquisition. A previous ping to the separate
REST host does not establish archive-host reachability. Do not probe
`data.binance.vision` before the usage-scope and exact acquisition gates; make
the approved, bounded acquisition the first archive-host request and stop on
any region or policy refusal. [Binance Public Data issue #524](https://github.com/binance/binance-public-data/issues/524)
records the maintainer's answer; [Binance Terms of Use](https://www.binance.com/en/about-legal/terms)
remain applicable alongside the [Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md).

**Source clarification reviewed 2026-11-18 (Asia/Saigon):** Binance Public Data
issue #502 states that `data-api.binance.vision` is not a live Binance endpoint
and directs users to `data.binance.vision` for the Datasets. The archive is
documented as daily/monthly files; the README says daily files appear the next
day, Spot klines from 2025-01-01 use microsecond timestamps, and every ZIP has
a `.CHECKSUM` sidecar. The same issue says access/use of Vision Datasets,
including automated retrieval, is governed by the Vision Dataset Terms and
Binance Terms of Use. [Issue #502](https://github.com/binance/binance-public-data/issues/502)
and the [official Public Data README](https://github.com/binance/binance-public-data/blob/master/README.md)
are the supporting primary sources. The conclusion here is limited to these
published source statements; it is not legal advice.

The owner confirmed personal non-commercial offline/paper research and
local-only retention, then approved the exact date-bound phrase for this run.
The root policy was valid for less than 24 hours. That approval is exhausted;
any repeat or expanded date range needs a new policy and separate exact
approval. The old REST approval phrase does not authorize archive requests.

## Current proposal and hard caps

The zero-network readiness command returned the half-open candle range
`[2026-10-19T00:00:00Z, 2026-11-18T00:00:00Z)`: 30 completed UTC days, up to
43,200 rows and 60 archive/checksum requests. That exact range was executed
once under the owner approval above. Recompute the proposal and obtain fresh
approval before any future acquisition.

| Limit | Value |
|---|---:|
| Daily Spot archive files | 30 |
| Expected maximum closed candles | 43,200 |
| HTTPS requests, including one checksum per ZIP | 60 |
| Attempts per file | 1 |
| Maximum ZIP size | 1 MiB each |
| Maximum checksum size | 1 KiB each |
| Maximum total downloaded bytes | 32 MiB |
| Maximum uncompressed CSV size | 1 MiB per day |
| Maximum runtime | 900 seconds |
| Redirects, credentials, accounts, orders, streaming | Disabled |

The official [Binance Public Data README](https://github.com/binance/binance-public-data/blob/master/README.md)
says Spot klines are distributed as daily or monthly archives, daily data is
published the next day, each ZIP has a `.CHECKSUM` file, and Spot timestamps
from 2025-01-01 use microseconds. The adapter therefore requests only the 30
completed UTC days before the selected cutoff. It converts timestamps to
milliseconds using integer arithmetic and preserves the ZIP bytes, sidecar,
hashes, source rows, and row-to-archive lineage.

## Implementation

The archive adapter is isolated in `market_os/btc_history.py` and reuses B0/B1
candle validation, canonical Parquet, DuckDB manifests, and replay:

- It allowlists only HTTPS `GET` requests for the exact BTCUSDT/1m daily ZIP
  and `.CHECKSUM` paths on `data.binance.vision`; redirects are rejected.
- It validates each sidecar's SHA-256 and exact filename before opening the ZIP.
- It requires one expected CSV member, caps ZIP and decompressed bytes, checks
  all 12 Spot kline columns, converts Spot microsecond timestamps exactly, and
  keeps rows in their UTC date and chronological order.
- It performs requests sequentially, once per file, without automatic retry or
  resume. It holds the bounded first run until the integrity checks complete,
  then persists immutable `.zip` and `.CHECKSUM` artifacts with their hashes.
- It records archive and checksum hashes, row counts, host, request count, and
  row provenance in the existing B1 manifest. It does not enable streaming,
  credentials, account access, trading, or redistribution.

The offline `btc-paper historical-readiness` CLI and
`GET /v1/btc/history/readiness` endpoint now describe the archive route and
perform zero network requests. Live acquisition uses a distinct command and
authorization schema:

```text
python -m market_os.cli btc-paper historical-readiness --cutoff-ms <UTC-midnight-ms>
python -m market_os.cli btc-paper acquire-archive \
  --start-date <YYYY-MM-DD> --end-date-exclusive <YYYY-MM-DD> \
  --allow-historical-ingest \
  --authorization-file approved-vision-archive-policy.json \
  --execution-approval "<exact date-bound owner approval phrase>" \
  --store-root <local-b1-root>
```

The authorization file must be at the repository root and is git-ignored. It
must match the 30-day range, current source, Vietnam region, personal
non-commercial scope, local retention, an `expires_at` no more than 24 hours
ahead, and all byte/request/runtime caps. The phrase also binds the exact
archive dates. REST's `approved-policy.json` and
execution phrase cannot authorize this route.

## Verification

- `python -m pytest market_os/tests/test_btc_history.py -q`: **36 passed**.
- The suite verifies timestamp conversion, checksum matching, path and scope
  authorization, policy lifetime and exact-phrase gates, raw artifact
  persistence, manifest lineage, and zero-network readiness using local
  fixtures and an injected transport.
- `python -m compileall -q market_os/btc_history.py market_os/cli.py`: passed.
- No Binance Vision request, historical candle request, Jev request, credential
  use, or trade occurred while implementing this adapter.

## Post-execution gates

The B2 numerical baseline has run on the local dataset. It is a retrospective
chronological diagnostic: local archive-artifact timestamps do not reconstruct
contemporaneous per-candle feed availability, and the 30-day result does not
establish regime stability or profitability. See
[`B2-BTC-FEATURES-BASELINES-REPORT.md`](B2-BTC-FEATURES-BASELINES-REPORT.md).

The BTC evidence seam is now implemented: a local corpus contains 43,200
documents derived from the approved B1 candles, with a BTC-only optional
MiniRAG adapter, packet builder, and recorded-assessment alignment helper. See
[`BTC-MINIRAG-JEV-EVIDENCE-PATH.md`](BTC-MINIRAG-JEV-EVIDENCE-PATH.md). The
original Binance publication times were not captured. The corpus preserves
that status as unknown and uses recorded local availability conservatively;
it therefore cannot establish that these archive documents were available at
their historical B2 decision times. A pinned local MiniRAG runtime retrieved
four of six source documents with stable citations across three repeats for
one B2 feature. The strict B3.1 packet-time gate rejected those retrospective
documents because their local availability is after the feature close. B3.1
still only has its 14 synthetic recorded fixture cases and no matched
market-level Jev comparison. Keep Jev advisory, paper-only, and subordinate to
deterministic risk controls; obtain separate authorization before any provider
request. See the [retrieval evidence](evidence/btc-minirag-retrieval-2026-11-19.json).

If the owner intends to use the data in a commercial Market OS product or
redistribute it, this source is not authorized under the reviewed terms; select
a separately licensed source first.
