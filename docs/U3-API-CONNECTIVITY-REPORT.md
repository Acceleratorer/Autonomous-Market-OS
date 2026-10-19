# U3/API Bounded Connectivity Report

**Status:** Implemented and locally verified offline. **Scope:** public
Binance BTCUSDT Spot ticker/1m kline connectivity and optional TypeSafe/Jev
connectivity only. U4/B4 and U5/B5 are not started.

## Implemented boundary

- Binance: `https://data-api.binance.vision/api/v3/ticker/price` and
  `/api/v3/klines`, public GET only, BTCUSDT only, 1m klines only.
- Validation: decimal prices, OHLC geometry, nonnegative volume, aligned and
  closed timestamps, duplicate/order/gap detection, raw-response fingerprints,
  bounded timeout/retry policy, and explicit HTTP error categories.
- TypeSafe: documented `POST https://api.typesafe.ai/v1/systemone` wire format
  through stdlib `urllib`; Choice, Noul, and Score answers are validated
  against a fixed synthetic question bundle. `jev-1.14.0` and `jev-1.13.0`
  are the supported versioned identities; aliases are not accepted.
- Jev output is descriptive experimental assessment only. It cannot produce an
  order, fill, portfolio mutation, risk override, or execution authority.

## Modes

```text
market-os btc-paper connectivity offline
market-os btc-paper connectivity binance --operation ticker|kline --allow-live-probe
market-os btc-paper connectivity jev --allow-live-probe --model-version <version> --max-spend-usd 0.05 --paper-only
market-os btc-paper connectivity inspect <probe-id> --resource manifest|result|fingerprints|replay
```

Offline mode uses committed synthetic fixtures and performs zero network
requests. The prepared Binance live command will make at most one HTTP attempt
with no retries, including on timeout, 429, 5xx, redirect, or connection
failure. It will not switch hosts or bypass regional restrictions. Jev live
probes require `TYPESAFE_API_KEY`, make at most one request, use zero retries,
and reserve a durable one-shot marker before transport.

The published TypeSafe price is `$0.042/Mtok` input and output is documented as
free. Local payload length is only a rough preflight estimate; it is not a
guaranteed token count or hard provider billing cap. The preflight therefore
fails closed when the configured estimate exceeds `$0.05`, reports live cost as
`estimated-from-provider-input-tokens-not-billing`, and does not claim that the
provider cannot charge more than the estimate.

Offline Jev latency, usage, and cost remain unknown rather than zero. The
current environment does not contain `TYPESAFE_API_KEY`; no live request was
attempted.

## Evidence and risks

Redacted probe metadata is persisted through `ConnectivityStore`; raw keys,
authorization headers, and raw provider payloads are not persisted. Evidence is
in `docs/evidence/u3-api-connectivity.json`.

Verification passed: 41 focused connectivity tests, 40 B0/B1/B2/B3 regression
tests, and the full suite at 252 passed with one existing skipped test. Compile,
evidence, secret, dependency, CLI/API offline smoke, replay/fingerprint, and
diff checks also passed.

Preflight facts retrieved 2026-10-19: TypeSafe official docs list Jev
`jev-1.14.0` and `jev-1.13.0`, `$42/Btok` (`$0.042/Mtok`) input pricing,
64k/request and 32k/question context limits, and 429/529 retry behavior. The
official Binance source repository confirms public market-data-only URLs on
`data-api.binance.vision`, HTTP 429/418 rate-limit behavior, and
`Retry-After`; the direct Binance docs pages returned an HTTP 202 CloudFront
WAF challenge from this environment.

Exact sources retrieved on 2026-10-19:

- TypeSafe API: https://docs.typesafe.ai/api.md
- TypeSafe models/pricing: https://docs.typesafe.ai/models.md
- TypeSafe Python retry behavior: https://docs.typesafe.ai/sdk/python/api/retries.md
- TypeSafe Python response types: https://docs.typesafe.ai/sdk/python/api/types/responses.md
- Binance market-data-only URLs: https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md
- Binance REST limits and market-data endpoints: https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md
- Binance terms: https://www.binance.com/en/terms (direct retrieval returned HTTP 202 and was not treated as verified)

Unresolved risks include Binance regional availability and terms, retention and
redistribution policy, TypeSafe regional/account entitlement, pricing drift,
provider/model drift, response latency, and lack of BTC-target calibration.

No paid Jev request or Binance live request was made during implementation or
verification. No trade or exchange execution occurred.

Preflight verification after safety fixes: 41 focused connectivity tests, 40
B0/B1/B2/B3 regressions, and 252 full-suite tests with one skipped test. No
live provider request was made.

## Prepared live commands — not executed

Binance public one-shot ticker probe:

```powershell
python -m market_os.cli btc-paper connectivity binance --operation ticker --allow-live-probe --store-root .market_os/btc-connectivity-live
```

- Endpoint: `GET https://data-api.binance.vision/api/v3/ticker/price?symbol=BTCUSDT`
- Maximum outbound attempts: 1; retries: 0; no redirect or host fallback.
- Expected output: redacted immutable probe manifest with validated symbol,
  decimal price, response fingerprint, endpoint, timestamps, request count,
  and `action: none`.
- This is still subject to the unresolved Binance terms/region/retention gate.

Jev one-shot synthetic assessment probe:

```powershell
python -m market_os.cli btc-paper connectivity jev --allow-live-probe --model-version jev-1.14.0 --max-spend-usd 0.05 --paper-only --store-root .market_os/jev-connectivity-live
```

- Endpoint: `POST https://api.typesafe.ai/v1/systemone`
- Payload: committed synthetic BTCUSDT descriptive state and fixed Choice,
  Noul, and Score questions; no future BTC labels, private data, or trade
  instruction.
- Maximum requests: 1; retries: 0; durable reservation file:
  `.market_os/jev-connectivity-live/jev-live.reservation.json`.
- Timeout: bounded connect/read envelope from the adapter; response body is
  byte-bounded.
- Cost: the local estimate is capped at `$0.05`, but provider tokenization and
  billing cannot be guaranteed from payload length. The command must not be
  approved as a guaranteed hard-charge ceiling; actual provider usage/cost is
  recorded only if returned/observed.
- Expected output: redacted manifest containing provider/model/version,
  request/response fingerprints, timestamps, latency, provider usage when
  returned, estimate-only cost status, validation, abstention, and `action: none`.

The Jev command requires the key in the local environment only. Current
preflight status: `TYPESAFE_API_KEY` is absent; its value was not printed or
requested in chat. No paid request was attempted.
