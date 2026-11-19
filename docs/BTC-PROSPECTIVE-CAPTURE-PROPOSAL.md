# BTC Prospective Capture Proposal

**Status:** Proposal for owner review only. It authorizes no network request,
data capture, Jev call, credential use, or trading.
**Scope:** BTCUSDT Spot, Binance public market data, BTC-only MiniRAG evidence
flow.
**Prepared:** 2026-11-19

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
| Proposed UTC range | `[2026-11-23T00:00:00Z, 2026-11-23T23:50:00Z)` |
| Maximum finalized records | 1,430 closed candles |
| Connection attempts | 1 total; no reconnect or retry |
| Runtime cap | 85,800 seconds (23 hours 50 minutes) |
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
| `clock_status` | Operating-system clock-sync state sampled at start and stop; do not infer clock accuracy if unavailable |

The locally observed `received_at_utc` is a recorded availability timestamp;
it must never be copied into `source_published_at`. Binance's `E`, `t`, and
`T` fields remain source event/candle times. This capture establishes local
receipt only. Whether a future packet may use a source whose publication time
is unknown depends on the packet-gate choice below.

Store only `k.x=true` finalized events. Do not use in-progress candle updates
for a decision, fill missing minutes, or substitute a historical archive row.
Mark missing or duplicate candle intervals in the manifest. Treat all Binance
candles in this capture as one source-dependency group; MiniRAG retrieval of
them is not independent corroboration.

## Packet-gate prerequisite

The current BTC packet builder rejects
`publication_time_status="unknown-not-captured"`, even when a separate local
availability timestamp exists. Therefore, this capture would **not** make a
B3.1 packet eligible under the current implementation by itself.

Before any capture request, resolve this contract question explicitly:

1. Keep the current packet gate unchanged. In that case, the proposed capture
   is limited to timestamp/provenance diagnostics and cannot feed a Jev packet;
   or
2. Review and approve a packet-contract change that allows a source with
   unknown publication time only when its separately recorded local
   availability is no later than the decision eligibility time. The change
   must preserve publication as unknown, keep event time separate, and add
   validation/evidence before the capture is run.

Option 2 does not claim or infer the original publication time. No code change
or gate relaxation is included in this proposal. The owner must choose one
option before any new data request.

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

## Approval checklist

Approval for any later run must identify the exact UTC range and confirm the
following together:

- the timestamp-gate choice above;
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
- [ADR-0057: Strict Recorded Availability for BTC Evidence](decisions/ADR-0057-btc-strict-recorded-availability.md)
- [ADR-0021: BTC historical-data authorization and readiness gate](decisions/ADR-0021-btc-historical-readiness-gate.md)
- [BTC MiniRAG and Jev Evidence Path](BTC-MINIRAG-JEV-EVIDENCE-PATH.md)
