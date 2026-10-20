# U3/B3 Jev Incremental-Value Benchmark Report

**Status:** Implemented and locally verified offline.  **Scope:** U3/B3 only;
BTCUSDT Spot, frozen B2 feature/label/evaluation path, Jev-shaped typed
assessment fixtures.

## Result

U3/B3 adds `market_os/btc_b3.py`, a versioned experiment contract, strict
recorded-response parsing, deterministic failure/abstention handling, a
same-input E1/E2 comparison, replay-checked persistence, read-only CLI/API
inspection, focused tests, an ADR, and machine-readable evidence.

The adapter is intentionally fixture-backed. It performs zero network or
provider requests and has no TypeSafe SDK, credential, HTTP, socket, retry, or
live transport path.

The current defect-closure regeneration is tied to B1 revision
`btc-history-77e4548a5394b078adee` with canonical fingerprint
`77e4548a5394b078adee6bf57d9d37df55c72fe09eec388a22ba5a5a1b90bfa6`.
The previous `btc-history-49b70e...` identity was stale evidence.

## Exact matched-control protocol

1. Materialize the frozen B2 `btc.b2.features.v1` and
   `btc.b2.close-return-5m.v1` artifacts from the selected local B1 dataset.
2. Reuse B2's chronological boundaries, five-minute target-overlap purge, and
   five-minute embargo. Boundaries are frozen before fitting either arm.
3. Fit E1's numerical conditional-rate groups on train rows only.
4. Fit E2's numerical-plus-Jev groups on the subset of train rows with a
   usable recorded Jev assessment. Missing/invalid/late/abstaining rows are
   explicit abstentions, not fallbacks.
5. Fit one-bin empirical calibration on calibration rows only. Never fit or
   tune on test rows.
6. Compare raw and calibrated metrics only on valid held-out rows. Compute the
   matched-control delta on the identical test-row intersection where E1 and
   E2 both have predictions.

No context-input `Z` experiment is included, so no extra-information claim is
made. LightGBM remains deferred because the local B2 dataset is too small and
gappy to justify a new dependency.

## Contract and provider semantics

The typed Jev-shaped answer is a `Choice` with `bullish`, `bearish`, and
`indeterminate` options, plus probabilities and confidence. The experiment
records the exact question, answer schema, provider `typesafe`, model role
`jev`, resolved version `jev-1.14.0`, request/response fingerprints,
availability timestamps, failure, abstention, cache, and lineage metadata.

The output remains an experimental semantic assessment. It is not a direct
`BUY`, `SELL`, order, risk override, execution authority, or calibrated
five-minute BTC return probability.

## Metrics and availability

The B1 fixture's eligible feature rows reach the documented gap, so no
leakage-safe future labels form. Classification, prediction, and calibration
metrics are therefore recorded as `unavailable` for the shipped run. The
contract and positive evaluation path are tested with larger in-memory
synthetic rows. Offline latency, usage, and cost are recorded as
`unknown-not-observed-offline`.

Coverage and abstention are always recorded when candidate rows exist. Failure
counts and replay fingerprints remain inspectable even when metrics are
unavailable.

## Promotion decision

**Not promoted.** B3 proves the controlled offline benchmark boundary and
failure behavior, not Jev value. Promotion requires a larger continuous local
dataset, stable out-of-sample matched-control improvement, target-specific
calibration, uncertainty analysis, cost-aware paper evidence, and prospective
shadow verification.

## Surfaces

```text
market-os btc-paper b3 run --dataset-revision ... --history-store-root ... --fixture ... --store-root ...
market-os btc-paper b3 inspect <run-id> --resource manifest|config|fixture_cases|responses|abstentions|splits|predictions|metrics|calibration|matched_controls|report|lineage|artifacts|fingerprints|replay --store-root ...
POST /v1/btc/b3/runs
GET  /v1/btc/b3/<run-id>/<resource>?store_root=...
```

The read-only inspection resources validate artifact hashes and replay
fingerprints without invoking a provider.

## Verification

- Focused U3/B3 tests: **8 passed**.
- Provider/fixture parsing, hostile and malformed rejection, unavailable and
  abstaining behavior, timestamp/input-fingerprint validation, no-look-ahead,
  frozen splits, calibration isolation, matched controls, deterministic replay,
  CLI/API inspection, and no-real-transport proof: **passed** in focused tests.
- Focused defect-closure regressions: **B1 22, B0 12, B2 7, B3 8,
  connectivity 43, and CLI 2 passed**.
- Full suite after B1 closure: **265 passed, 1 skipped**.
- `compileall`, evidence JSON validation, dependency check, secret scan, replay/
  fingerprint checks, CLI/API smoke, and `git diff --check`: **passed**.

Evidence: `docs/evidence/u3-b3-jev-incremental.json`.
Provider facts: `docs/research/typesafe-jev-u3-b3.md`.
