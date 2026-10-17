# B0 BTC Paper Experiment Replay Report

**Status:** Implemented and locally verified; offline synthetic-fixture scope
only. **No market-data request, model request, credential, broker, or order
path is present in B0.**

At `as_of=2026-01-01T00:30:00Z`, the fixture yields 19 raw events, 12
canonical candles, 12 features, and six available labels. Outcomes are 11
accepted, two duplicates, one conflict, two invalid, one open, one stale, and
one out-of-order. The manifest reports the missing interval from `00:11` to
`00:20` UTC. Dataset revision is `btc-dataset-ee742818d5cd976d`.

The reference fixture replays 19 raw events into 12 canonical candles, 12
point-in-time feature rows, and six available five-minute labels. Outcomes are
11 accepted, two duplicate, one conflicting, two invalid, one open, one stale,
and one out-of-order. One explicit gap spans `00:11` to `00:20` UTC.

## Contracts and time rules

The separate `market-os.btc-paper.v1` contracts cover raw event provenance,
closed BTCUSDT one-minute candles, dataset manifest/revision, feature rows,
five-minute label rows, prediction request/result envelopes, and paper-only
experiment configuration. The existing `market-os.v1` US equities contracts
are unchanged.

- Timestamps must be timezone-aware UTC. Event time order is
  `source_timestamp <= received_at <= availability_timestamp`.
- A candle must span one minute, be minute-aligned, have valid finite OHLCV,
  and cannot be available before its close.
- A feature's decision-eligibility time is the later of candle close and
  availability. Its input references/fingerprint include only candles closed
  by its own close and available by the decision-eligibility instant. Delayed
  availability never lets a later candle enter an earlier candle's features.
- A label is separate from its feature inputs. It is the natural log of the
  close at exactly five minutes after the feature candle close divided by that
  candle close. Missing minute continuity or a target unavailable by replay
  `as_of` suppresses that label. Its target fingerprint and `target_refs`
  identify the future candle independently of the feature-input fingerprint.
- Dataset revision is a stable prefix of the canonical full-dataset digest;
  feature/request revision is derived from the point-in-time input digest.
- Replay uses fixture `as_of` and the versioned experiment configuration's
  staleness limit, never the wall clock.

## Replay outcomes

Each event receives an inspectable outcome: accepted, duplicate, conflict,
open, invalid, stale, not-yet-available, or out-of-order. Accepted candles are
canonicalized by open time, sorted chronologically, and carry provenance. The
manifest records gaps. Replay and the `market-os btc-paper replay --fixture`
CLI command are deterministic and read-only.

## Verification evidence

Machine-readable results are in `docs/evidence/b0-btc-paper-replay.json`.
Focused tests cover contract round-trips and rejection, closed-only selection,
deduplication/conflicts, packet order, gaps, staleness, invalid/open/future
records, target horizon and lineage, empty input, and repeated replay.
The existing equities/ETF workflow and paper-only suite are included in the
full repository test run recorded in that evidence.

## Limits and next milestone

B0 is a schema/replay foundation, not persistent Parquet/DuckDB ingestion, a
trained predictor, a backtest, or a paper broker. B1 is historical closed-candle
ingestion into a canonical local Parquet/DuckDB dataset, with reproducible
replay, gap/deduplication handling, and explicit no-look-ahead evidence. Any
network source requires a separate B1 implementation decision; this B0 code
does not connect to one.
