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
requests. Binance live probes are one bounded public read. Jev live probes
require `TYPESAFE_API_KEY`, make at most one request, use zero retries, and are
never run by tests, CI, or implementation checks.

## Evidence and risks

Redacted probe metadata is persisted through `ConnectivityStore`; raw keys,
authorization headers, and raw provider payloads are not persisted. Evidence is
in `docs/evidence/u3-api-connectivity.json`.

Verification passed: 39 focused connectivity tests, 40 B0/B1/B2/B3 regression
tests, and the full suite at 250 passed with one existing skipped test. Compile,
evidence, secret, dependency, CLI/API offline smoke, replay/fingerprint, and
diff checks also passed.

Unresolved risks include Binance regional availability and terms, retention and
redistribution policy, TypeSafe regional/account entitlement, pricing drift,
provider/model drift, response latency, and lack of BTC-target calibration.

No paid Jev request or Binance live request was made during implementation or
verification. No trade or exchange execution occurred.
