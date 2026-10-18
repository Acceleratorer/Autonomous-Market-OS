# ADR-0020: U3/API Bounded Connectivity Boundary

- Status: Accepted
- Date: 2026-10-19

## Decision

Add a fixture-first, paper-only connectivity slice for BTCUSDT Spot public
market data and optional TypeSafe/Jev assessment. The default mode performs no
network requests. Live probes are explicit, bounded, and independent from the
existing B0/B1/B2/B3 offline workflows.

## Provider boundaries

- Binance uses only `https://data-api.binance.vision` with literal public GET
  paths `/api/v3/ticker/price` and `/api/v3/klines`.
- The adapter supports only BTCUSDT Spot ticker data and 1m klines. It has no
  API-key header, signed query, account, order, withdrawal, margin, futures,
  WebSocket, or execution path.
- TypeSafe uses the documented `POST https://api.typesafe.ai/v1/systemone`
  wire contract through stdlib HTTPS transport. The key is read from
  `TYPESAFE_API_KEY` only for an explicitly gated live probe.
- Jev live probes require a versioned model, `--allow-live-probe`, paper-only
  mode, the exact `$0.05` ceiling, and exactly one request with zero retries.

## Interpretation and evidence

Provider responses are validated into versioned descriptive experimental
assessments with request/response fingerprints, timestamps, latency, usage,
cost status, failures, abstention, and validation metadata. Choice
probabilities, confidence, Noul, and Score values are not interpreted as
calibrated five-minute BTC-return probabilities.

Connectivity artifacts are redacted and replay-checked. They cannot create a
BUY/SELL command, order, fill, risk override, portfolio mutation, or execution
authority. No U4/B4 or U5/B5 work is included.

## Consequences

Offline fixtures remain the CI and development path. Regional access, legal and
retention terms, provider/model drift, pricing, spend, and target-specific
calibration remain unresolved operational risks requiring later review.
