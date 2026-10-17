# ADR-0015: BTC experiment is math-first; Jev is an experimental typed-decision provider

- **Status:** Accepted; B0 offline contract/replay implementation recorded
- **Date:** 2026-10-17
- **Scope:** BTCUSDT spot, five-minute research and paper-trading experiment

## Decision

Build the BTC experiment as a deterministic, reproducible quantitative research
system. Market OS remains the owner of data eligibility, feature computation,
evaluation, calibration application, decision policy, virtual portfolio state,
risk limits, event persistence, and paper-only enforcement.

Use these roles:

| Role | Owner | Authority |
|---|---|---|
| Numerical computation | Polars, NumPy, DuckDB, and deterministic Python | Canonical data, features, labels, costs, simulation, and risk inputs |
| Statistical prediction | Trivial/statistical models, logistic regression, then LightGBM | Baseline market predictions from pinned numerical features |
| Typed probabilistic assessment | Jev, only through a narrow optional adapter | Experimental market-context or evidence classification signal |
| Natural-language explanation | Existing grounded summary providers | Research and result explanation only |
| Paper decision and fill simulation | Market OS | Fixed policy, risk checks, virtual orders, ledger, and audit trail |

Jev is the primary *experimental* model candidate because its typed
probabilistic output may be cheap and suitable for structured classification.
It is not a numerical computation engine, a trained BTC forecaster by default,
or an execution authority. JSON is a versioned contract for inputs and outputs;
all market arithmetic and probability calibration remain deterministic or
reproducible numerical work.

## Consequences

- The B0 implementation proves closed-candle fixture canonicalization, replay,
  data QA, lineage, and time-correct feature/label creation before any hosted
  model call. Historical source ingestion is deferred to B1.
- B0 now has a separate `market-os.btc-paper.v1` contract family and
  deterministic fixture replay. Source/receipt/availability timestamps are
  ordered in UTC; feature fingerprints are point-in-time prefixes, while label
  target fingerprints and future-candle references are stored separately.
- The exact five-minute target is log(close at feature close + 5 minutes /
  feature close); a missing candle in the interval or a target unavailable at
  fixture `as_of` suppresses the label.
- Historical Binance ingestion, Jev/OpenAI inference, model training, backtests,
  and virtual-broker behavior remain future work. B0 performs no network request.
- LightGBM earns its place only after trivial and statistical baselines; Jev
  earns its place only through fair, out-of-sample incremental-value tests.
- Jev outputs must carry a pinned provider/model version, exact input-state
  fingerprint, task/question version, response timestamp, and raw typed result
  fingerprint. They are calibrated downstream before a paper policy may consume
  them.
- A Jev score is not interpreted directly as `P(BTC rises in five minutes)`.
  That relationship must be validated against held-out outcomes.
- Every candidate policy may return `hold`; it may create virtual spot orders
  only after deterministic time, freshness, calibration, cost, and risk gates.
- No authenticated Binance endpoints, exchange balances, live orders, leverage,
  short selling, model credentials, or model-provider traffic are introduced by
  the first implementation phase.

## Alternatives considered

- **Frontier model as trading authority:** rejected. It weakens reproducibility,
  adds cost and latency, and cannot own risk or paper-execution state.
- **Jev as a replacement for numerical processing:** rejected. Typed model
  output complements, but does not replace, feature engineering, statistics,
  calibration, and simulation.
- **Local-first model routing for all tasks:** rejected. Local and cloud models
  will be selected per benchmarked task, latency, privacy, cost, and reliability
  rather than through unconditional fallback ordering.

## Evidence gate

Retain Jev only if it improves preregistered out-of-sample predictive,
calibration, and post-cost paper-simulation results over the matched baseline.
A negative result is a successful research outcome and removes Jev from the
BTC prediction path while preserving its possible research/explanation role.

## References

- `TECH_DOCS.md` — full engineering specification and experiment design
- `docs/BTC-PAPER-EXPERIMENT-ROADMAP.md` — delivery phases and acceptance gates
- `docs/decisions/ADR-0010-final-orchestration-owner.md` — Market OS ownership
- `docs/B0-BTC-PAPER-REPLAY-REPORT.md` — implemented B0 contract and verification report
