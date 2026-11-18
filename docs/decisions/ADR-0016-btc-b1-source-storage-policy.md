# ADR-0016: B1 historical source, transport gate, and local dataset storage

- **Status:** Accepted for one bounded archive execution on 2026-11-18; future acquisitions require fresh date-bound approval
- **Date:** 2026-11-18 (source and regional review update)
- **Scope:** BTCUSDT Spot, closed one-minute history for local quantitative research; no live streaming or trading

## Decision

Keep B1 transport disabled by default. A run is enabled only while source
terms, regional eligibility, retention, and exact owner authorization checks
pass. Each future range or repeat acquisition requires fresh date-bound
approval.

Binance's official Spot REST documentation lists `GET /api/v3/klines` on
`data-api.binance.vision` as keyless public market data. The Binance Vision
Dataset Terms, however, name `data.binance.vision` and its associated endpoints
without naming `data-api.binance.vision`. An open question in Binance's public
data repository received a contributor response advising use of
`data.binance.vision`; that conflicts with the official Spot API documentation
and is not an authoritative legal clarification. Therefore the current REST
host is not cleared by this review.

If Binance remains the chosen provider, use its historical archive service at
`data.binance.vision`, which the Vision Dataset Terms name directly. The B1
archive adapter now uses a separate authorization schema and transport. It
fetches exactly one daily BTCUSDT/1m ZIP and its `.CHECKSUM` sidecar for each of
30 completed UTC days, verifies SHA-256, rejects redirects, and preserves the
raw ZIP, checksum, and source-row lineage. It does not reuse the REST host,
REST authorization file, or REST execution phrase.

The Vision Dataset Terms allow only listed non-commercial uses, including
purely personal non-production algorithmic historical backtesting and
non-commercial open-source data-science evaluation. They prohibit commercial
use and certain downstream uses. This project may use such data only for the
owner's personal, non-production, offline research and paper simulation under
those restrictions. The terms mention downloading/caching/querying but do not
set a retention period; indefinite local retention is not certified by this
review. Do not redistribute datasets or derived feeds.

The owner has identified Vietnam as the access region. The official Binance
Terms link to a prohibited-country PDF updated 2026-01-05; that published list
does not name Vietnam. The PDF reserves Binance's ability to designate other
locations, and the general Terms allow service restrictions. A Binance Public
Data repository maintainer says the Vision Dataset Terms apply wherever a
user lives, in a response about Japan; this is useful source guidance, not a
Vietnam-specific legal ruling. The linked country page is JavaScript-rendered,
so recheck the current linked list before acquisition. A prior
`GET /api/v3/ping` returned HTTP 200 from the separate `data-api.binance.vision`
REST host; it does not establish archive-host reachability. The reviewed
sources show no identified Vietnam exclusion, but they do not guarantee
current access to `data.binance.vision`; stop on any regional or policy refusal.

Vietnam Government Resolution 05/2025/NQ-CP covers the pilot for crypto-asset
issuance, exchange-market organization, service provision, and state
management. The cited scope does not specifically address downloading public
historical candles for private offline research; this is not a legal opinion
or a certification that any future use is permitted.

## Source facts checked 2026-11-18

- Binance Spot REST docs define kline intervals, UTC `startTime`/`endTime`,
  chronological rows identified by open time, request weight, and a maximum
  limit of 1,000. The kline REST response has no WebSocket-style
  `is_closed` flag; B1 must enforce its explicit cutoff.
- Binance's Market Data Only FAQ lists `data-api.binance.vision` and
  `GET /api/v3/klines` as public, unauthenticated endpoints.
- Binance Vision Dataset Terms v1.0 (last updated 2026-08-26) apply to public
  datasets on `data.binance.vision` and associated endpoints. They govern use
  of derived data, grant a non-commercial CC BY-NC-SA 4.0 license, restrict
  permitted purposes, prohibit commercial utilization without a separate
  written enterprise license, and set no explicit retention duration.
- A contributor comment in open issue #502 (2026-11-05) says
  `data-api.binance.vision` is not a live Binance endpoint and recommends the
  `data.binance.vision` archive service. This statement conflicts with Binance's
  official Spot API docs; the issue is not treated as legal authority.
- A maintainer response in open issue #524 (2026-11-05) says Vision datasets
  are available without an account and the same terms apply wherever a user
  lives. The response concerns a Japan resident; applying its general wording
  to Vietnam is an inference, not a Vietnam-specific legal ruling.
- The official Binance Vietnamese Terms link to a prohibited-country list and
  say services may be restricted by jurisdiction. The linked list PDF, updated
  2026-01-05, does not name Vietnam and reserves the right to add locations.
  The linked page is JavaScript-rendered, so the current list must be rechecked
  before acquisition. A prior ping to the separate REST host does not prove
  archive-host access.
- The official Vietnam Government record for Resolution 05/2025/NQ-CP scopes
  the pilot around crypto-asset markets and services, not data-only retrieval.

## Sources

- [Binance Vision Dataset Terms](https://github.com/binance/binance-public-data/blob/master/TERMS_AND_CONDITIONS.md)
- [Binance public-data repository issue #502](https://github.com/binance/binance-public-data/issues/502)
- [Binance public-data repository issue #524](https://github.com/binance/binance-public-data/issues/524)
- [Binance Public Data README](https://github.com/binance/binance-public-data/blob/master/README.md)
- [Binance Market Data Only URLs](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md)
- [Binance Spot REST API](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md)
- [Binance Terms of Use, Vietnamese](https://www.binance.com/vi/terms)
- [Binance List of Prohibited Countries](https://www.binance.com/en/about-legal/list-of-prohibited-countries) and its [linked PDF](https://bin.bnbstatic.com/static/cms/cg08ou2ak0tn7mcplvfg/file/2dead3dd5d9bccb32694e2f0fe5c7f2c6b583e7a6f851296edef7088340e6df5.pdf) (updated 2026-01-05; PDF title includes `[DRAFT]`)
- [Vietnam Government registry: Resolution 05/2025/NQ-CP](https://vanban.chinhphu.vn/?classid=0&docid=215249&pageid=27160)

## Existing B1 implementation and proposed controls

The existing offline implementation accepts source-shaped 12-field kline
fixture pages, validates them through B0 `ClosedCandle`, stores raw pages by
SHA-256, writes canonical Parquet, and uses DuckDB for manifests, provenance,
outcomes, and replay. Dataset revisions derive from canonical content rather
than page boundaries. DuckDB and PyArrow are direct dependencies because the
requested formats are not available from the standard library.

The opt-in REST adapter remains separate and disabled because its license
coverage is unresolved. It allowlists only HTTPS `GET /api/v3/klines` on
`data-api.binance.vision` and requires its own root policy and execution phrase.
Those REST-specific controls do not authorize archive requests.

## Execution record — 2026-11-18

The owner approved BTCUSDT Spot 1m for UTC dates 2026-10-19 through
2026-11-17, personal non-commercial offline/paper research, local-only
retention, and no redistribution, credentials, or trading. The bounded run
made 60 HTTPS requests (30 ZIPs and 30 checksums), verified all SHA-256
sidecars, downloaded 2,093,387 bytes, and stored 43,200 canonical candles with
zero gaps. Dataset revision `btc-history-9c58a3ac5cfd05c7398e` and manifest
`btc-history-manifest-6307b278cdc684f4dc42` are retained in the local B1
store. Full evidence is in
[`../evidence/b1-binance-vision-execution-2026-11-18.json`](../evidence/b1-binance-vision-execution-2026-11-18.json).

The first ingest failed after the downloads because the generic page guard
allowed only 1,000 rows while each daily archive held 1,440. Recovery used the
preserved local artifacts, archive-specific row validation, and batched DuckDB
writes; it made no additional network request. Per-response HTTP receive times
were not committed by the failed ingest, so the final manifest records local
artifact modification timestamps. A provisional manifest from an interrupted
local recovery remains unregistered and was not used by B2.

## Proposed archive controls

The archive proposal is 30 completed UTC days, up to 43,200 rows, 30 ZIPs and
30 checksum sidecars, 60 HTTPS requests total, one attempt per file, a 1 MiB
ZIP cap, a 1 KiB checksum cap, 1 MiB uncompressed CSV cap per day, 32 MiB total
download cap, and a 900-second runtime cap. The parser requires one expected
CSV member with 12 columns, converts Spot timestamps from microseconds for
dates on or after 2025-01-01, and leaves B1's continuity/gap classification
authoritative. The archive transport still requires a repository-root
`approved-vision-archive-policy.json`, an exact date-bound execution phrase,
explicit personal non-commercial scope, confirmed local retention, and an
expiry no more than 24 hours ahead. The execution phrase is required even for
an injected transport. The approved execution record above closes this gate
for one range only; the default transport remains disabled.

Any future approved route must keep files local, avoid backups/uploads and
redistribution, preserve raw-source hashes and lineage, validate closed
candles and gaps, and stop on provider or integrity ambiguity. Generate a fresh
UTC cutoff and obtain new date-bound approval before another run.

The approved archive execution made 60 requests to `data.binance.vision`; the
offline recovery made zero requests. No Jev request, credential use, or trade
occurred. A prior public ping to the separate REST host was a separate review
action and did not participate in this acquisition.
