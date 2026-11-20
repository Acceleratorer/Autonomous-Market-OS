# BTC Prospective Capture Proposal

**Status:** Proposal for owner review only. It authorizes no network request,
data capture, Jev call, credential use, or trading.
**Packet gate:** Under the 2026-11-19 clarification to ADR-0057, a
contemporaneous local receipt with a defensible UTC error bound can establish
availability while source publication remains unknown.
**Scope:** BTCUSDT Spot, Binance public market data, BTC-only MiniRAG evidence
flow.
**Prepared:** 2026-11-19
**Preflight (2026-11-20):** The current Windows workspace host's Windows Time
service was not started, so no defensible UTC error bound was available. This
keeps the proposal diagnostics-only until a qualified time source and
continuous bound monitoring are available. See the
[clock and source preflight](evidence/btc-prospective-capture-preflight-2026-11-20.json).

## Purpose

The approved B1 Binance Vision archives are retrospective. Their local receipt
time is later than the B2 observations, and their original source publication
time was not recorded. Under [ADR-0057](decisions/ADR-0057-btc-strict-recorded-availability.md),
those archives remain ineligible for a historical point-in-time B3.1 packet.

This proposal defines a small prospective capture to check whether finalized
BTC candles can be recorded with local availability timestamps before future
research decisions. It is a capture-integrity pilot. It is not a powered market
study, a prospective shadow evaluation, a result about trading edge, or a Jev
assessment run. It does not change the project-wide LightRAG decision.

## Proposed bounded run

| Field | Proposal |
|---|---|
| Venue / instrument | Binance Spot / `BTCUSDT` |
| Source class | Public market-data WebSocket stream; no API key or account stream |
| Stream | `btcusdt@kline_1m`, UTC intervals |
| Endpoint | `wss://data-stream.binance.vision:443/ws/btcusdt@kline_1m`; no host fallback |
| Candle-open range | `[2026-11-23T00:00:00Z, 2026-11-23T23:50:00Z)` (1,430 one-minute bars) |
| Final-candle receive grace | Through `2026-11-23T23:50:30Z` |
| Maximum finalized records | 1,430 closed candles |
| Connection attempts | 1 total; no reconnect or retry |
| Runtime cap | 85,830 seconds (23 hours 50 minutes 30 seconds) |
| Market-data messages | At most 50,000 event messages, 1 KiB each |
| Aggregate market-data payload | At most 32 MiB received |
| Local capture artifacts | At most 2 MiB total |
| Request cap | 1 WebSocket connection attempt; 0 REST market-data requests |
| Persistence | Local-only under the ignored `.market_os/` data root |
| Retention | Keep locally until explicit deletion; no upload or redistribution |

The dates are part of this proposal, not standing authorization. If separate
approval is not in place before the proposed start, replace the date range and
obtain approval for the new dates before connecting. Stop at the first exceeded
cap, malformed event, unexpected source behavior, disconnection, or storage
failure; retain a partial-run manifest and do not reconnect or backfill.

The candle-open range and receive window are distinct. Keep the connection open
through the 30-second post-close grace so the candle opened at 23:49 UTC can be
delivered and validated after it closes at 23:50 UTC. Do not accept candles
opened at or after 23:50 UTC; do not exceed the 1,430-record cap.

The stream is a better fit than replaying another archive because the client
can record when it actually received each finalized event. Binance documents a
market-data-only WebSocket endpoint, the `1m` kline stream, and the fields
listed below. Binance documents a 24-hour lifetime for a Spot connection to
`stream.binance.com`, but does not separately state that limit for the
market-data-only hostname. This proposal conservatively caps the session at
23 hours and 50 minutes; confirm endpoint-specific limits before approval. The
documented kline update cadence means incoming market-data message count can
exceed the number of saved closed candles; both are capped above. Required
PING/PONG control frames are outside the market-data message cap and must
follow Binance's WebSocket limits.

## Timestamp and provenance record

For every saved event, preserve the original JSON payload and record:

| Field | Meaning |
|---|---|
| `source_event_time` (`E`) | Binance event timestamp; not treated as publication or local availability time |
| `candle_open_time` (`k.t`) | UTC start of the one-minute candle |
| `candle_close_time` (`k.T`) | UTC candle close timestamp carried by the event |
| `candle_closed` (`k.x`) | Must be `true` for a finalized candle to be stored |
| `received_at_utc` | Local UTC wall-clock timestamp captured immediately when the complete WebSocket event is delivered |
| `received_monotonic_ns` | Local monotonic receipt counter for within-process ordering and duration checks |
| `connection_id`, `sequence`, `stream`, `symbol`, `interval` | Capture-session and source identity |
| `payload_sha256` | Hash of the exact preserved event payload |
| `source_published_at` | `null`; the feed does not provide a publication timestamp in the documented kline payload |
| `publication_time_status` | `unknown-not-captured` |
| `clock_error_bound_ms` | Quantified upper bound on total UTC timestamp error at this receipt, including time-source and timestamp-sampling uncertainty; `null` if no defensible bound is available |
| `clock_status` | Time-source identity/state, bound observations, and clock-step or sync-loss events recorded against the monotonic clock throughout capture; start/stop snapshots alone are insufficient |

The locally observed `received_at_utc` is a recorded availability timestamp;
it must never be copied into `source_published_at`. Binance's `E`, `t`, and
`T` fields remain source event/candle times. This capture establishes local
receipt only. Before treating receipt as time evidence, the configured time
source must expose a quantified UTC-error bound that remains valid throughout
the capture, with observations tied to the monotonic clock. If that bound is
missing, stale, exceeded, or interrupted by a clock step or sync loss, mark
all records in the indeterminate interval's bound unknown and withhold packet
eligibility. A future availability comparison must use the conservative
latest possible receipt time (`received_at_utc` plus the applicable error
bound); it must be no later than B2 decision eligibility. A source that
cannot establish this bound may produce timestamp diagnostics only. This
proposal does not authorize a new time-service endpoint or request.

The 2026-11-20 read-only host preflight found that `w32tm /query /status` and
`w32tm /query /configuration` both reported the Windows Time service was not
started (`0x80070426`). The service is configured for NTP with a peer present,
but no sync status or UTC error bound was available. Do not start it or treat
its wall clock as packet-eligible without the owner's approval and continuous
bound observations. A capture made in this state may retain diagnostics, but
its receipt timestamps cannot establish packet availability.

Store only `k.x=true` finalized events. Do not use in-progress candle updates
for a decision, fill missing minutes, or substitute a historical archive row.
Mark missing or duplicate candle intervals in the manifest. Treat all Binance
candles in this capture as one source-dependency group; MiniRAG retrieval of
them is not independent corroboration.

## Selected packet gate

The owner selected strict recorded availability under
[ADR-0057](decisions/ADR-0057-btc-strict-recorded-availability.md) and
reaffirmed on 2026-11-20 that a contemporaneously recorded local receipt time
with a defensible UTC error bound qualifies as availability while source
publication remains unknown. Keep the two fields distinct. For a future packet,
use the conservative receipt bound (`received_at_utc + clock_error_bound_ms`)
and require the source event to end by the observation close and that receipt
bound to be no later than B2 decision eligibility. Binance's documented kline
payload still does not provide its original publication timestamp.

The retrospective B1 archive remains ineligible: its local receipt occurred
after the historical B2 decisions and no defensible clock error bound was
captured. This proposal remains an unapproved capture-integrity pilot; it does
not authorize a new connection, B2 run, packet assessment, provider call, or
market-performance claim. If a later capture is separately approved, eligible
packets use local Qwen under ADR-0058; packet content is not sent to hosted Jev.

Any later change that uses event time as publication, omits the receipt-time
error bound, or admits evidence received after B2 decision eligibility requires
a new owner decision. The current rule preserves unknown publication,
contemporaneous local availability, source event time, and the bounded-clock
eligibility check as separate fields.

## Use, limits, and later work

- Purpose remains personal, non-commercial, offline/paper research in Vietnam.
- Keep source data and derived capture artifacts on the local machine until
  explicit deletion. Do not publish, redistribute, or send them to a provider.
- No credentials, user/account streams, order endpoints, live signals, or
  execution are in scope.
- No Jev, embedding, hosted LLM, or other provider call is authorized. Any
  later provider use requires its own explicit approval and data-handling
  decision.
- The pilot may verify capture integrity and the receipt-time record only. It
  cannot support a market-performance claim, calibration conclusion, or
  statistical B3.1 comparison. A larger sample and preregistered protocol would
  need a separate proposal and approval.
- Before a future run, recheck the current source terms and regional
  eligibility. The official API documentation establishes the technical
  market-data endpoint; it does not settle the terms, retention rights, or
  regional-use questions already marked as blockers in
  [ADR-0021](decisions/ADR-0021-btc-historical-readiness-gate.md).
- The 2026-11-20 source-document check reconfirmed that Binance documents the
  market-data-only WebSocket endpoint without API-key authentication. The
  current Terms of Use says service availability can vary by jurisdiction; the
  reviewed public material did not settle public-stream retention rights or
  Vietnam-specific eligibility. Keep both questions unresolved until the
  actual terms applicable to this endpoint and region are confirmed.

## Approval checklist

Approval for any later run must identify the exact UTC range and confirm the
following together:

- the diagnostics-only scope and strict packet gate clarified by ADR-0057;
- current source terms and regional eligibility review;
- the one-stream, one-connection, row, message, byte, storage, and runtime caps;
- local-only retention and non-commercial paper-research purpose; and
- no Jev/provider egress, credentials, redistribution, or trading.

This document is not the execution approval. The earlier B1 archive approval
was date-bound to its historical archive range and caps and does not authorize
this prospective connection.

## Primary references

- [Binance Spot WebSocket Streams](https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md) — kline fields, update cadence, connection lifetime, and WebSocket limits.
- [Binance market-data-only endpoints](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md) — public WebSocket market-data endpoint and no API-key requirement.
- [Binance Terms of Use](https://www.binance.com/en/terms) and [prohibited-countries page](https://www.binance.com/en/legal/list-of-prohibited-countries) — service availability may be jurisdiction-specific; this review did not resolve public market-data retention or Vietnam eligibility.
- [2026-11-20 clock and source preflight](evidence/btc-prospective-capture-preflight-2026-11-20.json)
- [ADR-0057: Strict Recorded Availability for BTC Evidence](decisions/ADR-0057-btc-strict-recorded-availability.md)
- [ADR-0021: BTC historical-data authorization and readiness gate](decisions/ADR-0021-btc-historical-readiness-gate.md)
- [BTC MiniRAG and Jev Evidence Path](BTC-MINIRAG-JEV-EVIDENCE-PATH.md)
