# Binance public Spot market-data research

**Checked:** 2026-10-21

## Scope and conclusion

For the BTCUSDT paper-research pipeline, Binance documents a read-only public market-data surface. The implementation should use the literal `https://data-api.binance.vision` REST host without an API key and keep trading/account endpoints out of the connector. A 1-minute kline stream can be added later, but only a message whose `k.x` field is `true` is a closed candle suitable for a finalized dataset. This note records provider facts and safety constraints; it does not authorize live trading or claim predictive performance.

## REST market data

- Binance's **Market Data Only URLs** page says the `data-api.binance.vision` REST surface requires no authentication and exposes public `GET` routes including `/api/v3/klines`, `/api/v3/ticker/price`, `/api/v3/exchangeInfo`, `/api/v3/time`, and related market-data endpoints. [Official market-data-only reference](https://developers.binance.com/en/docs/products/spot/faqs/market_data_only)
- The Spot REST market reference defines `GET /api/v3/klines`; klines are uniquely identified by their open time. The endpoint has IP request weight 2, accepts the `1m` interval, and supports a maximum `limit` of 1000 (default 500). [Kline endpoint reference](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market)
- A kline response is a 12-item array in this order: open time, open, high, low, close, base volume, close time, quote volume, trade count, taker-buy base volume, taker-buy quote volume, and an ignore field. Numeric price/volume values are strings in the documented response. [Kline response schema](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market)
- Kline query `timeZone` defaults to UTC; if supplied it changes interval interpretation, while `startTime` and `endTime` remain UTC. For a UTC-only research contract, omit `timeZone` and validate interval alignment. [Kline query semantics](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market)

## REST request handling

- Binance classifies public market data as security type `NONE`; `TRADE` is a separate security type for placing/canceling orders, and `USER_DATA` covers private account information. The connector should not add API-key headers, signatures, or private routes when it only needs public data. [REST security types](https://developers.binance.com/en/docs/products/spot/rest-api)
- The general REST documentation says HTTP 429 indicates a request-rate-limit violation and HTTP 418 indicates an IP auto-ban after continued 429 responses. A 429/418 response includes `Retry-After`; clients must back off rather than spam requests. Limits are IP-based. [REST limits and return codes](https://developers.binance.com/en/docs/products/spot/rest-api)
- HTTP 5XX responses indicate an internal Binance error and the execution status is described as unknown. For a read-only data adapter, surface the provider error and use a bounded retry policy only where appropriate; do not interpret a 5XX as evidence of a successful data write or order. [REST return codes](https://developers.binance.com/en/docs/products/spot/rest-api)
- Binance documents that public market-data APIs should use `data-api.binance.vision`; the general `api.binance.com` host is not needed for this read-only path. [General REST information](https://developers.binance.com/en/docs/products/spot/rest-api)

## WebSocket kline stream

- The Spot WebSocket market-stream reference documents the UTC stream name `{symbol}@kline_{interval}` at `wss://stream.binance.com:9443`; for intervals other than `1s`, updates are sent every 2 seconds. The `1m` interval is supported. [WebSocket stream reference](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/ws-streams/~)
- Each kline message contains `e` (event type), `E` (event time), `s` (symbol), and a `k` payload. The payload includes `t` (start), `T` (close), OHLC prices, volumes, trade count, and `x`, documented as “Is this kline closed?”. Persist/feature only `x == true`; treat `x == false` as an in-progress update. [WebSocket kline schema](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/ws-streams/~)
- The documented UTC example uses a close time ending in `...9999` for a 1-minute candle and reports event/start/close timestamps as Unix timestamps. The adapter should still validate the actual interval and timestamps rather than deriving closure from a local wall clock. [WebSocket kline example](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/ws-streams/~)

## Headers and transport details

- `GET` endpoint parameters are sent in the query string. Binance timestamps are milliseconds by default; the optional `X-MBX-TIME-UNIT:MICROSECOND` header switches timestamp fields to microseconds. For this adapter, omit that header and keep the documented millisecond contract. [General REST information](https://developers.binance.com/en/docs/products/spot/rest-api)
- The kline endpoint is documented as database-backed. The general REST page says asynchronous responses can have normal delay and describes Database as the most delay-prone of its listed data sources; record observed/received time separately from exchange timestamps. [Data sources](https://developers.binance.com/en/docs/products/spot/rest-api)

## Operational and terms boundary

- Binance's API FAQ says excessive requests can trigger a WAF restriction; repeated violations can result in an IP ban. It also warns users to protect API keys and secrets. This project needs neither credential for public market-data ingestion. [Binance API FAQ](https://www.binance.com/en/support/faq/detail/360004492232)
- Binance's current Terms of Use prohibit conduct intended to artificially affect crypto-asset prices, including wash trading, front running, quote stuffing, and spoofing/layering, and prohibit imposing an unreasonable load on Binance infrastructure. A research connector should remain low-rate, read-only, and paper-only. [Binance Terms of Use](https://www.binance.com/en-JP/terms)

## Implementation implications for Autonomous-Market-OS

1. Allowlist the REST host `data-api.binance.vision` and only public `GET` market-data paths.
2. Normalize the 12-element kline array into named fields while preserving decimal strings (or `Decimal`) until a numerical feature layer deliberately converts them.
3. Validate `symbol`, `interval`, positive finite OHLC values, nonnegative volume, open/close timestamp order, sorted unique open times, and 1-minute alignment. Do not silently fill gaps.
4. Drop the newest REST candle when its closure cannot be established; for WebSocket data, only `k.x == true` enters the finalized candle set.
5. On 429/418, honor `Retry-After` and stop/reduce polling; on 403/451 or regional restriction, report the failure and use fixtures rather than switching to an unofficial host.
6. Keep connector output as market data and research evidence. No order creation, account access, margin/futures, withdrawal, or authenticated Binance route belongs in this slice.

## Primary source list

- [Binance Spot Market Data Only URLs](https://developers.binance.com/en/docs/products/spot/faqs/market_data_only)
- [Binance Spot Market REST reference](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market)
- [Binance Spot REST general information](https://developers.binance.com/en/docs/products/spot/rest-api)
- [Binance Spot WebSocket Market Streams](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/ws-streams/~)
- [Binance API FAQ](https://www.binance.com/en/support/faq/detail/360004492232)
- [Binance Terms of Use](https://www.binance.com/en-JP/terms)

## Limitations

This is documentation research only. No Binance request, WebSocket connection, API key, account access, or order endpoint was used. Binance documentation and regional availability can change; re-check the linked first-party references before implementing or running an opt-in connectivity probe.
