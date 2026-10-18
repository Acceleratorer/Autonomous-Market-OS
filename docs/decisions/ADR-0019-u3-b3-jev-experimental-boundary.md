# ADR-0019: U3/B3 Jev Experimental Boundary and Promotion Criteria

- Status: Accepted
- Date: 2026-10-18

## Decision

Implement U3/B3 as a controlled, offline-only incremental-value benchmark
over the frozen B2 feature, label, chronological split, purge, embargo, and
calibration contracts. The Jev-shaped adapter consumes deterministic recorded
responses only. It does not import a provider SDK, hold credentials, open
network transport, or retry a provider request.

The benchmark compares:

1. **E1:** the existing numerical B2 conditional-rate baseline over the exact
   frozen feature input `X`.
2. **E2:** the same numerical inputs plus one typed recorded Jev assessment,
   with downstream rates fit on the training range only.

E2 is eligible for a matched-control delta only on the identical held-out test
rows where both arms have usable predictions. Jev-unavailable, malformed,
late, inconsistent, hostile, and explicit-abstention responses remain explicit
response records and reduce E2 coverage; they never silently become a numeric
prediction.

## Contract boundary

Each experiment records the dataset revision, B2 feature fingerprint, exact
question and answer schema, provider/model/resolved-version identity, request
and response fingerprints, eligibility and response timestamps, failure and
abstention state, cache identity, experiment/split/calibration identity, and
artifact lineage. Offline latency, usage, and cost are `unknown-not-observed-
offline`, not zero.

The Jev-shaped output is an experimental typed assessment. It is never a
`BUY`, `SELL`, order, risk override, execution authority, or calibrated
five-minute BTC return probability. The question's choice distribution and
confidence are semantic model outputs until a separate target-specific
calibration study establishes otherwise.

## Promotion criteria

No promotion occurs from U3/B3 alone. A future promotion would require:

- a larger continuous approved local dataset and frozen evaluation plan;
- stable out-of-sample improvement against the same-input numerical control;
- calibration evidence fit only on the calibration range;
- explicit coverage, abstention, failure, latency, usage, and cost evidence;
- cost-aware paper evaluation and prospective shadow verification; and
- deterministic replay, lineage, and provider-version pinning.

The current B1 fixture cannot form leakage-safe labels after its documented
gap, so predictive and calibration metrics are unavailable. This is a data
limitation, not evidence of Jev value or failure.

## Consequences

- B3 can validate contract, replay, availability, failure, leakage, and
  matched-control behavior without external state.
- B3 does not add context `Z`, LightGBM, a broker, portfolio, paper fills, or
  any live/provider request.
- The explicit result of this milestone is **not promoted** and the next gate
  is a larger approved local benchmark before any provider integration.
