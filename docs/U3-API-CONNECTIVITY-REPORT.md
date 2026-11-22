# U3/API Bounded Connectivity Report

**Status:** Implemented and locally verified offline. **Scope:** public
Binance BTCUSDT Spot ticker/1m kline connectivity and optional TypeSafe/Jev
connectivity only. The current BTC owner decision keeps Jev at connectivity;
B3.1 packet content stays local with Qwen under
[ADR-0058](decisions/ADR-0058-btc-jev-connectivity-only-local-assessor.md).
U4/B4 and U5/B5 are not started.

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

The configured TypeSafe input rate is `$0.042/Mtok`; output is documented as
free. The request preflight estimates input tokens as serialized payload bytes
divided by four, then applies that rate. This is only a rough reservation
estimate, not provider-reported token usage or a hard billing cap. It fails
closed when the configured estimate exceeds `$0.05`. Live records label this
`estimated-from-provider-input-tokens-not-billing`; the label describes the
rate basis, while the amount itself comes from the payload-length proxy.

Offline Jev latency, usage, and cost remain unknown rather than zero. Before
the approved run, `TYPESAFE_API_KEY` was absent from the active process and was
then confirmed present/non-placeholder in the local User environment without
printing its value.

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

No Binance live request was made during implementation or offline verification.
The separately approved one-shot ticker request is recorded below. No trade or
exchange execution occurred.

Offline and regression verification after safety fixes: 41 focused connectivity
tests, 40 B0/B1/B2/B3 regressions, and 252 full-suite tests with one skipped
test. The separately approved Jev attempt below is the only live provider
request; no Binance request was made.

## Actual approved Jev attempt

The approved Jev command was executed exactly once on 2026-10-19. The User
environment contained a non-placeholder `TYPESAFE_API_KEY`; its value was not
printed or persisted. The request used pinned model `jev-1.14.0`, the committed
synthetic payload, paper-only mode, one request, and zero retries.

Observed result:

- Request count: `1`
- Retry count: `0`
- Status: failed safely during local response validation
- Failure: the returned Score `context_score` was initially rejected as
  inconsistent under the preflight parser's exact floating-point check
- No trade, order, exchange-account access, portfolio mutation, or execution
  occurred.

The response was not retried. The follow-up offline fix accepts the bounded
decimal rounding documented by TypeSafe's Score semantics: the Score is the
probability-weighted mean of level numbers and may be fractional. Future
approved attempts must still use the durable reservation and one-request
policy; this failed attempt consumed the reservation and must not be repeated
without new approval.

## Actual approved Binance ticker attempt

The approved equivalent command was executed exactly once because the
`market-os` executable was not on PATH but `python -m market_os.cli` passed the
offline help check:

```text
python -m market_os.cli btc-paper connectivity binance --operation ticker --allow-live-probe
```

Observed result:

- Endpoint: `https://data-api.binance.vision/api/v3/ticker/price`
- Operation: public BTCUSDT ticker
- HTTP request count: `1`
- Retry count: `0`
- Status: successful and validated
- Symbol: `BTCUSDT`
- Price: `83063.15000000`
- Response fingerprint: `4d637e86a20e5f74b357af1df458645720e2bd0cb5e109b237f4acacf4f44a79`
- Latency: `626 ms` from recorded request start to response receipt
- Regional/rate-limit/error status: no error; no 4xx/429/451/5xx was observed
- HTTP status: not separately persisted by the pre-existing probe manifest
- Stored evidence: `.market_os/btc-connectivity/runs/connectivity-83fe6abe14f27cf21f79/`
- Replay: passed with zero new network/provider requests
- Credentials/account/order/balance/withdrawal/futures/margin/WebSocket: none
- Trade/order/fill/portfolio mutation: none

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

The above describes the 2026-10-19 snapshot. The owner later approved a fresh,
single synthetic Jev connectivity request on 2026-11-19. That one-shot request
is documented separately below. Binance Vision archive acquisition was also
approved under its separate B1 scope; this report's prepared ticker command
was not run again.

## Subsequent owner-approved Jev connectivity request — 2026-11-19

After the original reservation was consumed, the owner explicitly reauthorized
one synthetic Jev request and configured `TYPESAFE_API_KEY` in the process
environment. Its value was checked only for presence and was never printed or
persisted. The existing bounded CLI was used with `jev-1.14.0`, one request,
zero retries, paper-only mode, and the approved `$0.05` payload-estimate cap.

Observed result:

- Status: valid; requested and resolved model: `jev-1.14.0`.
- Request count: `1`; retry count: `0`; latency: `1,679 ms`.
- Provider usage: `484` input tokens and `92` output tokens.
- Local preflight cost estimate: `$0.0000089775`, using the serialized payload
  length divided by four as an approximate input-token count. The separately
  reported `484` input tokens were not used to calculate this amount. It is not
  an observed provider charge or a hard billing ceiling.
- Probe replay verified the saved manifest with `0` network requests and `0`
  provider requests.
- Question contract: `btc.connectivity.synthetic-descriptive.v1`. The result
  is not a B3.1 evidence assessment, a BTC return probability, or a trading
  signal. No trade or exchange action occurred.

Fingerprints, normalized synthetic answers, and explicit limits are recorded
in [`jev-connectivity-reauthorized-2026-11-19.json`](evidence/jev-connectivity-reauthorized-2026-11-19.json).
The raw key and raw provider response body are not included.

## Owner-requested Jev smoke and bounded BTC capture — 2026-11-22

The owner requested a fresh Jev API connectivity check followed by a short
real-time BTCUSDT capture. The Jev check reused the existing bounded CLI with
`jev-1.14.0`, the fixed synthetic descriptive request, one request, zero
retries, paper-only mode, and the `$0.05` local estimate guard. The process
environment contained `TYPESAFE_API_KEY`; its value was not read into output,
logged, or persisted.

Observed Jev result:

- Status: valid; requested and resolved model: `jev-1.14.0`.
- Request count: `1`; retry count: `0`; latency: `467 ms`.
- Provider usage: `484` input tokens and `92` output tokens.
- The recorded estimate was `$0.0000089775`; this is not a provider invoice or
  a guaranteed billing ceiling.
- Probe ID: `connectivity-ff090f36f3f734431879`; the normalized result and
  fingerprints remain under the ignored local path
  `.market_os/jev-connectivity-live-2026-11-22/`.
- The request used only the synthetic contract
  `btc.connectivity.synthetic-descriptive.v1`. It included no live BTC price,
  MiniRAG result, or B3.1 packet and produced no market signal or trade action.

The public Binance probe then confirmed one BTCUSDT ticker read. The bounded
capture command is `python -m market_os.btc_realtime_capture
--allow-live-capture --samples N`: it polls the existing allowlisted public
1-minute kline endpoint once every 180 seconds, requires a finite sample count,
uses one attempt per poll, and stores JSONL plus an atomic manifest under the
ignored `.market_os/btc-realtime-captures/` directory. It does not start a
background service or call Jev.

The owner-requested two-poll sample ran on 2026-11-22 at 15:17:28 UTC and
15:20:28 UTC. Both requests succeeded, with zero retries, and yielded seven
new closed candles. Its local run is
`btc-live-20261122T151728Z-ce0cadf6`; the candle values remain in ignored
local files and are not included in this repository. The manifest keeps
`source_published_at` and `clock_error_bound_ms` unknown and marks every record
`packet_eligible: false`. This sample is useful for capture-path verification
and local chart data only; it is not eligible for a B3.1 point-in-time packet.

No BTC evidence was sent to TypeSafe. ADR-0058 remains in force. A longer
capture still needs a bounded run plan and review of the applicable Binance
terms/retention conditions.

## Local chart integration — 2026-11-22

The read-only gateway now exposes `GET /v1/btc/realtime/latest` from its
configured Market OS store root. The local Next.js operator reaches it through
a same-origin server route; the browser refreshes that route every 180 seconds
with caching disabled. The chart shows the newest 64 validated closed candles
from the capture and falls back to the registered historical dataset when no
live run is available. The capture process itself remains finite and must be
started explicitly:

```text
python -m market_os.btc_realtime_capture --allow-live-capture --samples 30
```

`--samples` accepts 1 through 432 polls; each poll is one request, spaced 180
seconds apart. The runner uses `MARKET_OS_STORE_ROOT`, or `.market_os/` by
default, so it shares the local store with the gateway. No service is installed
or started automatically. The web chart never calls Binance directly and
does not call Jev.

The existing two-poll local run supplies the chart with seven candles. The
clock error bound remains unknown, so the capture is explicitly excluded from
B3.1 and paper decisions. No new market-data requests or Jev calls were needed
to wire the local chart.
