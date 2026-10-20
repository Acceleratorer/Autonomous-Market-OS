# U3/B2 BTC Features and Numerical Baselines Report

**Status:** Implemented and locally verified offline. **Scope:** B2 only;
BTCUSDT Spot, closed one-minute B1 candles, five-minute research labels.

## Result

B2 adds a deterministic materializer in `market_os/btc_b2.py`, local artifact
persistence, numerical baselines, chronological split metadata, calibration
outputs, replay checks, and read-only CLI/API inspection. The implementation
does not add or enable market-data transport, Jev/OpenAI/hosted-model calls,
credentials, brokers, virtual portfolios, or live trading.

The shipped B1 synthetic fixture remains intentionally negative for evaluation:
its only feature-eligible rows occur immediately before the documented missing
interval, so there are no leakage-safe labels and the final metrics and
calibration outputs are `unavailable`. This is an explicit data-quality result,
not a zero or fabricated score. The focused synthetic materializer and split
tests also cover positive formula and baseline paths.

The current defect-closure regeneration uses B1 dataset revision
`btc-history-77e4548a5394b078adee` and canonical fingerprint
`77e4548a5394b078adee6bf57d9d37df55c72fe09eec388a22ba5a5a1b90bfa6`.
Earlier `btc-history-49b70e...` evidence is stale and has been superseded.

## Formulas and availability

Feature version `btc.b2.features.v1` uses the smallest hand-checkable set:

- `close = C_t`
- `log_return_1m = ln(C_t / C_{t-1})`
- `log_return_5m = ln(C_t / C_{t-5})`
- `range_pct = (H_t - L_t) / C_t`
- `log_volume = ln(1 + V_t)`

The current candle and exact five prior one-minute candles must be present,
contiguous, valid, and available by `decision_eligible_at = max(close_time,
availability_timestamp)`. Feature input references contain only those past or
current candles. The feature fingerprint includes the dataset revision and
the full deterministic feature row.

Target version `btc.b2.close-return-5m.v1` is separate from feature input:

`target_return = ln(C_{t+5} / C_t)`

The target stores its own fingerprint and the exact future target reference. It
is emitted only when the five-minute path is continuous and the target is
available by the explicit materialization `as_of`; it is never included in
feature inputs.

Inspectably classified feature outcomes are `eligible`, `warm_up`, `gap`,
`stale`, `unavailable`, and `invalid`. Label outcomes distinguish eligible,
gap, and unavailable future targets. Missing, stale, unavailable, or invalid
rows cannot produce a prediction sample.

## Baselines and splits

The persisted baselines are:

1. `naive_0_5`: fixed `P(up)=0.5`.
2. `empirical_rate`: train-only positive-direction rate.
3. `conditional_rate`: train-only positive-direction rate conditioned on the
   sign of `log_return_1m`, with train-rate fallback for unseen groups.

Metrics include log loss, Brier score, and accuracy. Calibration uses a
one-bin empirical rate fit on the calibration partition only. If purge and
embargo leave no calibration or test rows, the result is `unavailable`.

Splits are frozen in chronological order. For each boundary, rows with
`target_end_ms >= boundary` are purged because five-minute labels overlap, and
the first five minutes after the boundary are embargoed. No random shuffle is
used. Split assignments and reasons are persisted.

LightGBM was not added. The current B1 fixture is too small and too gappy to
justify a new dependency or a model comparison; the decision is deferred to a
later U3/B3 gate with a larger leakage-safe local dataset.

## Persistence and inspection

Each B2 run persists immutable JSON artifacts for configuration, features,
labels and label outcomes, splits, predictions, metrics, calibration, and
lineage. The manifest records B1 dataset revision, feature/label fingerprints,
artifact hashes, baseline names, and a replay fingerprint. Artifact paths are
relative to the B2 store and are hash-checked before inspection/replay.

CLI:

```text
market-os btc-paper b2 run --dataset-revision <revision> --history-store-root <b1-root> --store-root <b2-root>
market-os btc-paper b2 inspect <run-id> --resource metrics --store-root <b2-root>
```

API:

```text
POST /v1/btc/b2/runs
GET /v1/btc/b2/<run-id>/<resource>?store_root=<b2-root>
```

## Verification

- Focused B2, B0, and B1 tests: **7 B2, 12 B0, and 22 B1 passed** in the
  readiness defect-closure run.
- `python -m compileall -q market_os`: **passed**.
- `python scripts/ci_checks.py validate-evidence`: **passed**.
- `python scripts/ci_checks.py secret-scan`: **passed**.
- `python -m pip check`: **No broken requirements found**.
- CLI/API smoke, formula, availability, no-look-ahead, split leakage,
  calibration boundary, persistence, and replay tests: **passed**.
- `git diff --check`: **passed** at the verification checkpoint.
- Full regression suite after B1 closure: **265 passed, 1 skipped**.

Machine-readable evidence is in
`docs/evidence/u3-b2-btc-features-baselines.json`.

## Explicit exclusions and next gate

Excluded from B2: network ingestion, Binance transport enablement, Jev,
OpenAI, hosted models, credentials, LightGBM, broker/portfolio/execution code,
and live trading. The unresolved data limitation is the small B1 fixture's
missing interval and resulting absence of leakage-safe evaluation labels.

The next unified milestone is **U3/B3 — controlled Jev incremental-value
benchmark**, after a larger approved local dataset and matched numerical
controls exist.
