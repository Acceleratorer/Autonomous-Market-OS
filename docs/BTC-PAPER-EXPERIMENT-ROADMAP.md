# BTC Spot Paper Experiment Roadmap

**Status:** B0 implemented and B1 offline storage/replay implemented with
synthetic source-shaped fixtures. Verification results are recorded in the
respective evidence files. Public market-data transport remains disabled until
source/legal review and explicit approval. This roadmap does not authorize a
market-data network connection, a Jev request, a model credential, or a real
exchange action.

**Source of truth:** `TECH_DOCS.md` contains the complete technical design.
This file is the execution sequence for the fusion repository.

## Product boundary

The experiment studies BTCUSDT Spot with a five-minute horizon using closed
one-minute candles. It is a quantitative research and virtual paper-trading
system. Market OS owns the deterministic authority; model outputs are inputs to
measurable experiments, never direct execution commands.

```text
closed market data
  -> validation and replay
  -> deterministic features and labels
  -> statistical + LightGBM baselines
  -> optional Jev typed context signal
  -> calibration and walk-forward evaluation
  -> deterministic policy
  -> virtual paper broker, risk gate, audit trail
```

## Delivery order

| Phase | Deliverable | Surface | Exit gate |
|---|---|---|---|
| B0 | Contracts, dataset manifest, fixture replay, and data-quality specification | Local | Time and lineage rules are executable and tested |
| B1 | Historical closed-candle ingestion and canonical Parquet/DuckDB dataset | Local | Reproducible replay, gap detection, deduplication, and no-look-ahead evidence |
| B2 | Feature/label pipeline and numerical baselines | Local | Chronological walk-forward evaluation and calibration reports |
| B3 | Jev adapter and controlled incremental-value benchmark | Local | Jev is evaluated against matched controls with no execution authority |
| B4 | Virtual portfolio, cost model, and prospective shadow mode | Local | Deterministic, paper-only PnL and risk results replay exactly |
| B5 | Web deployment of the existing API plus BTC experiment read views | Web | Deployment stays paper-only; health, auth boundary, observability, and recovery are verified |
| B6 | CLI commands for BTC ingestion, replay, inspection, and reports | CLI | CLI calls the same versioned API/contracts and has no privileged trading path |
| B7 | Desktop/mobile app shell | App | App presents shared API state and owns no market, risk, or order logic |

The existing research CLI remains intact. B0 adds the narrow read-only command
`market-os btc-paper replay --fixture <path>`; broader BTC CLI/API work remains
deferred until its contracts stabilize.

B1 adds fixture-backed `btc-paper ingest` plus read-only manifest, candle,
outcome, provenance, gap, and stored-replay inspection. The candidate public
transport is isolated and disabled.

## B0: data contract and replay foundation

Build only the smallest offline vertical slice.

### Required work

- Audit current `market_os/`, tests, persistence, event contracts, CLI/API, and
  paper-only protection before selecting files to change.
- Add versioned contracts for candle records, raw-market-event provenance,
  canonical-bar manifests, dataset revisions, feature rows, label rows,
  prediction requests/results, and experiment configurations.
- Use synthetic BTCUSDT closed one-minute fixtures. Include valid sequences,
  duplicate events, gaps, out-of-order packets, partial/open candles, invalid
  prices/volumes, and stale observations.
- Define a point-in-time rule: inputs, source timestamp, receipt timestamp,
  availability timestamp, feature version, and decision eligibility timestamp
  are persisted and reproducible.
- Define the five-minute target without allowing future information into input
  features. Preserve labels separately from observable input records.
- Add fixtures and focused tests for schema validation, replay idempotency,
  deduplication, gap classification, closed-candle-only selection, and lineage.
- Update the existing docs, ADRs, evidence schema, and understanding log.

**Implementation:** Complete. Exact semantics and results are recorded in
`docs/B0-BTC-PAPER-REPLAY-REPORT.md` and
`docs/evidence/b0-btc-paper-replay.json`.

### B0 acceptance gate

- No network calls, credentials, Jev calls, OpenAI calls, broker interfaces, or
  live execution code.
- Fixture replay produces identical canonical candles, dataset manifests, and
  fingerprints on repeat runs.
- A failing timestamp, open candle, duplicate, gap, or invalid numeric input is
  explicit and inspectable.
- Existing US equities/ETF workflow and paper-only behavior continue to pass.

## B2/B3 evaluation protocol

Use time-ordered walk-forward splits. Because five-minute outcomes overlap,
apply a documented purge/embargo policy. Freeze training, calibration, and
final evaluation intervals before comparing candidates.

| Experiment | Input | Candidate | Question |
|---|---|---|---|
| E0 | Returns only | Naive/statistical policy | Does any complexity beat a simple baseline? |
| E1 | Numerical features `X` | LightGBM | Is there numerical predictive value? |
| E2 | Same `X` | Jev | Is Jev useful on identical information? |
| E3 | `X` plus Jev output from `X` | LightGBM + Jev feature | Does Jev improve a finite-data predictor? |
| E4 | `X` plus timestamped context `Z` | LightGBM + Jev feature | Does Jev extract useful additional context? |
| Control | `X` plus non-Jev representation of `Z` | Baseline | Is gain from Jev rather than new data? |

Measure log loss, Brier score, calibration error, selective/abstention quality,
net PnL after costs, drawdown, turnover, p95 latency, availability, and cost.
A Jev result advances only when its out-of-sample improvement is stable,
calibrated, post-cost positive relative to a matched control, and reproducible.

## Architecture rules

- **Math first:** price math, features, labels, calibration, thresholds, risk,
  fill simulation, and accounting are deterministic or reproducible numerical
  code.
- **Typed model boundary:** Jev receives an explicitly versioned state and
  question. Its response is validated as typed data, attributed to a model
  version, and stored with fingerprints.
- **No-trade default:** missing, stale, invalid, uncalibrated, late, or
  over-budget input results in `hold`.
- **Paper-only structural boundary:** no live mode exists in the BTC experiment.
  Virtual spot inventory cannot become negative.
- **Small stack:** add packages only after B0 proves they are necessary. Do not
  introduce distributed infrastructure for one instrument on one machine.

## Documentation updates

- `TECH_DOCS.md` remains the complete BTC design specification.
- ADR-0015 records the architectural decision.
- `docs/ROADMAP.md` records B0 as the exact next product milestone.
- `docs/UNDERSTANDING-LOG.md` records the decision and implementation evidence.
- Update `STACK.md` when model-lane status changes; M2.9 is currently blocked
  by a missing approved credential, not waiting for an approval phrase.

## B0/B1 implementation evidence

See `docs/B0-BTC-PAPER-REPLAY-REPORT.md` and
`docs/evidence/b0-btc-paper-replay.json` for B0, and
`docs/B1-BTC-HISTORICAL-INGESTION-REPORT.md`,
`docs/evidence/b1-btc-historical-ingestion.json`, and ADR-0016 for B1. B1 has
no network/model/broker code;
the implementation and tests use only the standard library and existing
pytest.

## Next milestone

**B2 — deterministic feature/label materialization and chronological numerical
baselines** with calibration and walk-forward evidence. B1 historical transport
remains disabled until source/legal review and explicit approval resolve the
network gate.
