# ADR-0018: U3/B2 Feature, Label, and Baseline Evaluation Contract

- Status: Accepted
- Date: 2026-10-18

## Decision

Implement U3/B2 as a local, deterministic research layer over the hash-checked
B1 canonical BTCUSDT one-minute dataset. Keep feature inputs and future labels
as separate persisted artifacts with independent fingerprints and lineage.

The first feature version is `btc.b2.features.v1`:

- `close = C_t`
- `log_return_1m = ln(C_t/C_{t-1})`
- `log_return_5m = ln(C_t/C_{t-5})`
- `range_pct = (H_t-L_t)/C_t`
- `log_volume = ln(1+V_t)`

The target version is `btc.b2.close-return-5m.v1`:

`target_return = ln(C_{t+5}/C_t)`

Features require the current candle and five exact contiguous historical
candles. Each input must be closed and available by
`decision_eligible_at = max(close_time, availability_timestamp)`. Labels are
materialized separately only when the future five-minute path is continuous
and available by explicit replay `as_of`.

## Split and model policy

Use chronological train/calibration/test assignments. Purge any row whose
`target_end_ms >=` the next split boundary and embargo the first five minutes
after each boundary because five-minute labels overlap. Fit one-bin empirical
calibration only on the calibration partition.

The fixed B2 baselines are `naive_0_5`, `empirical_rate`, and
`conditional_rate`. LightGBM is deferred until a larger leakage-safe local
dataset justifies adding a dependency. B2 does not add a Jev, OpenAI, hosted
model, broker, portfolio, or live-trading path.

## Consequences

Missing, stale, unavailable, invalid, and warm-up rows are explicit outcomes
and cannot silently enter model samples. An empty test or calibration interval
is reported as `unavailable`, not as a zero or a fabricated score. The shipped
B1 fixture currently yields no leakage-safe labels because its eligible rows
reach the documented gap; this is a valid negative data-quality result.

Configuration, features, labels, predictions, metrics, calibration, split
metadata, artifact hashes, and lineage are persisted in a local B2 store and
replay-checked. The read-only CLI/API surfaces expose those artifacts without
recomputing them from network or provider state.

The next gate is U3/B3: a controlled Jev incremental-value benchmark over a
larger approved local dataset with matched numerical controls.
