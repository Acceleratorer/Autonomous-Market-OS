# ADR-0016: B1 historical source, transport gate, and local dataset storage

- **Status:** Proposed; public-data transport disabled pending explicit user approval and unresolved terms/region review
- **Date:** 2026-10-18
- **Scope:** B1 BTCUSDT Spot historical one-minute candles; no live streaming

## Decision

Use Binance's documented public Spot REST kline interface as the candidate
historical source. Use only `GET /api/v3/klines` on the market-data-only host
`data-api.binance.vision`; do not use authenticated, account, wallet, order, or
trading APIs. The adapter is deliberately disabled in this B1 implementation:
the current chat has not supplied the explicit authorization required to fetch
market candles, and terms/regional eligibility could not be verified from the
official legal pages, which returned HTTP 202 to the documentation fetch.

The offline implementation will accept source-shaped synthetic fixture pages,
validate and normalize them through B0's `ClosedCandle`, persist raw pages
immutably by SHA-256, store canonical closed bars as Parquet, and use DuckDB as
a local manifest/provenance/outcome catalog and query layer. Dataset revisions
derive from canonical content, not request page boundaries. DuckDB and PyArrow
are justified direct dependencies because the requested storage formats are
not available in the existing runtime or standard library; B0 contracts stay
stdlib-only.

## Primary-source facts checked 2026-10-18

- Binance's official Spot REST docs define `GET /api/v3/klines`, require
  `symbol` and `interval`, support UTC `startTime`/`endTime`, identify klines by
  open time, assign request weight 2, and specify default limit 500 / maximum
  limit 1000. The response has 12 fields; the close timestamp is the interval's
  inclusive final millisecond. The REST kline schema does not provide a
  WebSocket-style `is_closed` flag; B1 must enforce its explicit cutoff from
  the close timestamp.
- The official market-data-only FAQ lists `https://data-api.binance.vision`
  and `GET /api/v3/klines`, and says the URL does not require an API key. The
  API docs classify public market-data endpoints as security type `NONE`.
- Binance documents dynamic IP-based rate limits: response headers report
  used weight, HTTP 429 requires backoff, `Retry-After` specifies the wait, and
  repeated violations may yield HTTP 418 bans. Endpoint weights and global
  ceilings can change; future transport must honor current server headers and
  fail closed on 418.
- The official API documentation repository states that documented endpoints
  and parameters are supported. This is not a license grant for retaining or
  redistributing market data. Binance's legal terms pages were inaccessible
  to this research pass (HTTP 202), and no authoritative regional eligibility,
  data-retention, or redistribution terms could be established. These remain
  approval gates, not assumed permissions.

Sources:

- [Binance Spot REST API — Kline/Candlestick data and limits](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#klinecandlestick-data)
- [Binance Spot REST API — IP limits and request security](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md#ip-limits)
- [Binance Market Data Only URLs FAQ](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md)
- [Binance API documentation repository](https://github.com/binance/binance-spot-api-docs)
- [Binance Terms of Use](https://www.binance.com/en/terms) (HTTP 202; content not verified)

## Proposed controls if transport is approved later

- Allowlist DNS hostname `data-api.binance.vision`, HTTPS port 443, and the
  exact `GET /api/v3/klines` path only. No redirects to a different host.
- Send a descriptive `User-Agent` such as
  `MarketOS-BTC-Paper/0.1 (+https://github.com/Acceleratorer/Autonomous-Market-OS)`.
- Require explicit UTC, minute-aligned half-open ranges `[start, end)`. Translate
  the exclusive end to Binance's inclusive `endTime=end_ms-1`.
- Maximum 1000 candles/page (source limit); proposed local cap 100 pages and
  100,000 candles per run. These local caps are application safeguards, not
  Binance quotas.
- Proposed 10-second per-request timeout and at most three total attempts for
  network timeouts and 5xx errors. On 429, honor `Retry-After` and stop if it
  exceeds 60 seconds; never retry 418. A checkpoint permits manual resume.
- Proposed local-only retention: raw response pages and derived datasets stay
  in the user-selected local store, are never uploaded or redistributed, and
  remain until the user deletes them. This retention proposal is not activated
  for exchange data until legal/region review and explicit approval.

No candle request was made for this decision. The disabled transport seam
raises a stable `source_not_approved` failure before opening any connection.
