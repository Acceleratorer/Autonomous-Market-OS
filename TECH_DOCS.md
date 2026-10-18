# TECH_DOCS.md

# Autonomous-Market-OS — BTC Spot Probabilistic Research & Paper-Trading Experiment

**Document type:** Engineering design / technical research specification
**Status:** Proposed architecture; **not** an implementation or deployment authorization
**Version:** 0.1 — design baseline
**Prepared:** 2026-10-17
**Project:** [Acceleratorer/Autonomous-Market-OS](https://github.com/Acceleratorer/Autonomous-Market-OS)
**Companion document:** `STACK.md` (existing project constraints)

> **Foundational rule:** The deterministic platform controls data validity, risk, state transitions, simulation, and all execution permissions. Models provide optional analysis, explanations, or experimental predictions. **Nothing in this document authorizes real trading, live exchange orders, or a real model/API request.** B0 implements only offline contracts and synthetic replay; the remaining ingestion, modeling, and paper-simulation design is not implemented.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Decisions, Assumptions, and Non-Goals](#2-decisions-assumptions-and-non-goals)
3. [Existing Repository and Architectural Constraints](#3-existing-repository-and-architectural-constraints)
4. [Core Research Question and Hypotheses](#4-core-research-question-and-hypotheses)
5. [Feasibility and Critical Engineering Judgments](#5-feasibility-and-critical-engineering-judgments)
6. [Proposed System Architecture](#6-proposed-system-architecture)
7. [Technology Stack and Trade-offs](#7-technology-stack-and-trade-offs)
8. [Binance Market-Data Pipeline](#8-binance-market-data-pipeline)
9. [Data Storage, Lineage, and Schemas](#9-data-storage-lineage-and-schemas)
10. [Market Features and Five-Minute Targets](#10-market-features-and-five-minute-targets)
11. [Jev: Capabilities, Limits, and Research Role](#11-jev-capabilities-limits-and-research-role)
12. [Hybrid Cloud/Local Model Lifecycle](#12-hybrid-cloudlocal-model-lifecycle)
13. [Inference Processing and Internal Interfaces](#13-inference-processing-and-internal-interfaces)
14. [Probability, Calibration, and Decision Theory](#14-probability-calibration-and-decision-theory)
15. [Model Comparisons and Incremental-Value Experiments](#15-model-comparisons-and-incremental-value-experiments)
16. [Paper Broker, Market Simulation, and Risk Boundary](#16-paper-broker-market-simulation-and-risk-boundary)
17. [Backtesting, Walk-Forward Evaluation, and Statistical Validity](#17-backtesting-walk-forward-evaluation-and-statistical-validity)
18. [Costs, Latency, and Resource Budgeting](#18-costs-latency-and-resource-budgeting)
19. [Testing Strategy and Acceptance Gates](#19-testing-strategy-and-acceptance-gates)
20. [Roadmap and Release Gates](#20-roadmap-and-release-gates)
21. [Proposed Repository Layout and Integration Plan](#21-proposed-repository-layout-and-integration-plan)
22. [Risks, Failure Modes, and Mitigations](#22-risks-failure-modes-and-mitigations)
23. [Open Architecture Decisions](#23-open-architecture-decisions)
24. [Definition of Done and Handoff Checklist](#24-definition-of-done-and-handoff-checklist)
25. [Primary References and Verification Notes](#25-primary-references-and-verification-notes)

---

## 1. Executive Summary

This specification captures the architectural decisions and engineering reasoning for a proposed **BTC/USDT Spot, five-minute-horizon, strictly paper-only** experiment within Autonomous-Market-OS.

The research question is not “Can Jev return `BUY` or `SELL`?” It is:

> **Does Jev provide measurable incremental out-of-sample predictive value beyond the information and predictive performance already available to a properly tuned statistical/LightGBM baseline—and does any improvement survive realistic transaction costs and delayed execution?**

The chosen development philosophy is **math-first, model-assisted, and evidence-driven**:

1. Build trustworthy, timestamped Binance public market data.
2. Preserve raw events, normalize closed candles, and test reproducibility.
3. Compute deterministic numerical features and point-in-time targets.
4. Establish simple statistical models and a well-tuned LightGBM baseline.
5. Evaluate Jev independently and as an additional feature producer.
6. Control for whether apparent improvements arise from Jev itself or merely from giving it additional information (for example, news text).
7. Select models using held-out prediction quality, calibration, inference cost, stability, and **net paper-trading utility**.
8. Keep all trading behavior in a deterministic virtual broker with no live-order interface.

### Key conclusions at design time

- **Feasible to engineer:** Ingestion, historical replay, LightGBM training, optional Jev inference, and virtual trading can all be built with a modest Python stack.
- **Unproven predictive edge:** No evidence reviewed here establishes that Jev predicts BTC five-minute movements better than numerical ML baselines.
- **Important separation:** A Jev `choice` probability expresses the model's answer to a *defined question*; it is not automatically a calibrated `P(BTC rises in 5m)`.
- **Likely baseline advantage:** For tabular OHLCV/technical features alone, LightGBM is the strong, inexpensive first benchmark. Jev might improve a finite-sample model via a different inductive bias, but the benefit must be measured.
- **More promising complementary role:** Jev may map additional, timestamped unstructured context (news, event descriptions, conflicting evidence) into typed semantic features. A matched control is needed to establish that Jev adds value beyond the new data itself.
- **No Jev fine-tuning assumption:** As of the TypeSafe documentation checked on 2026-10-17, Jev does **not** offer customer-specific LoRA or weight fine-tuning; its recommended customization is through `state`, question design, and a separately trained downstream model.
- **Strictly paper-only:** This design must not contain authenticated live order submission, real exchange balances, leverage, or live-broker permissions.

## 2. Decisions, Assumptions, and Non-Goals

### 2.1 Confirmed design decisions

| Dimension | Decision |
|---|---|
| Experiment | BTC/USDT market-data-driven research and paper trading |
| Venue | Binance **Spot** public market data |
| Target horizon | **5 minutes** ahead |
| Primary input granularity | 1-minute closed candles |
| Initial prediction cadence | One candidate prediction after every closed 1-minute candle |
| Real capital | None |
| Initial execution | Deterministic virtual broker only |
| Primary analytical stack | Python, Polars/NumPy, Parquet/DuckDB |
| First trained baseline | LightGBM, following trivial/statistical baselines |
| Jev | Experimental, optional typed-decision / semantic-feature provider |
| Generative LLM | Optional grounded research summarization/explanation only |
| Hosting strategy | Hybrid cloud/local, benchmarked—not unconditional fallback routing |
| Optimization criterion | Out-of-sample accuracy/calibration **and** executable net economic value |
| Phase 0 scope | Repository audit, data contracts, ingestion design, QA, reproducibility |
| Implementation status | B0 contracts/replay and B1 offline storage/replay implemented; public transport disabled, no model or broker calls |

### 2.2 Explicit assumptions to validate

- Public Binance BTCUSDT Spot data can be accessed from the target deployment environment under the exchange's current terms, regional restrictions, and operational limits.
- Closed 1-minute candles can be reconstructed consistently for historical and live data.
- End-to-end decision latency is small enough to define a reproducible *next executable quote* after model completion.
- A five-minute return target is a useful *research* horizon; this does not imply a profitable strategy.
- Local inference hardware and model variants must be benchmarked; do not assume a given parameter count fits available GPU memory at the desired context length.
- All market data and model inputs used for an observation were actually available by the recorded decision time.

### 2.3 Non-goals

The initial experiment will **not**:

- Send authenticated Binance orders, withdraw funds, or access exchange account balances.
- Trade margin/futures, short BTC, or use leverage.
- Ask an LLM to override a risk limit or approve an exchange action.
- Assume that JSON itself performs probabilistic computation.
- Presume Jev has forecasting specialization or customer fine-tuning support.
- Start with Kafka, Kubernetes, Ray, distributed microservices, an agent swarm, or a full-time GPU serving cluster.
- Optimize trading PnL by repeatedly tuning against the final held-out test set.
- Claim causality, market alpha, or deployability from one promising backtest.

## 3. Existing Repository and Architectural Constraints

### 3.1 Observed public state

The public repository README currently identifies `Autonomous-Market-OS` as a personal platform for research, reproducible backtesting, paper trading, and future controlled execution. The visible root includes:

```text
.github/workflows/
docs/
market_os/
scripts/
.gitignore
README.md
pyproject.toml
```

The available `pyproject.toml` specifies Python >=3.11, `market-os = "market_os.cli:main"`, and the pytest path `market_os/tests`.

The existing README's Phase 0 workflow is aimed at **US equities/ETFs**, not yet this BTC experiment. It treats the project as the owner of common contracts, orchestration, persistence, risk checks, CLI, and service interfaces; other projects are integrated through narrow adapters. It says **live execution is disabled in `market-os.v1`**.

### 3.2 `STACK.md` constraints (supplied project context)

The companion `STACK.md` describes this established research flow:

```text
Retrieved documents
    -> LightRAG passages
    -> deterministic evidence and claims
    -> optional model summary
    -> citation / grounding gate
    -> research report
    -> backtest and paper order plan
```

Responsibilities:

- **Market OS:** deterministic orchestration, persistence, audit events, permission/risk controls, paper orders.
- **LightRAG:** retrieved passages and document evidence.
- **Vibe-Trading:** deterministic backtesting.
- **Model:** optional citation-preserving research summarizer; it is not an execution authority.
- **Fallback:** deterministic reports must remain available without a model/network.

`STACK.md` reports M2.8 offline preparation completed, no real model call yet, and M2.9 gated on a specific approval for one synthetic call. Those statements describe the attached document's reported status, **not a fresh full source-code audit**.

### 3.3 Compatibility decision

Treat the BTC work as a **bounded research experiment**, not a silent change to the existing product scope. Reuse the project's safety, audit, provenance, and test conventions where practical; isolate the crypto data adapter, evaluation labels, model experiment, and paper ledger.

**Architecture distinction:** The existing model may explain research, while a new experimental predictor may *propose* signals in the sandbox. This is not permission to grant a model trading authority. Any model-driven paper action requires an explicitly separate deterministic policy and virtual risk gate.

### 3.4 Repository audit and B0 implementation boundary

The B0 implementation audit inspected the actual `market_os/` contracts, workflow, JSONL store, CLI, HTTP API, existing paper-only task/order contracts, test conventions, and ADR-0010 ownership rules. BTC is isolated in `market_os/btc_paper.py`; existing `market-os.v1` US-symbol contracts and workflow remain unchanged. B0 adds only offline synthetic replay and a read-only CLI fixture command. It does not implement the Binance ingestion design elsewhere in this document. See `docs/B0-BTC-PAPER-REPLAY-REPORT.md` for executable timestamp and target semantics.

Before coding: inventory `market_os/`, `docs/`, and `scripts/`; review the relevant ADRs; map existing interfaces; choose the smallest surgical change. Do not copy/paste a speculative directory tree into the project without this audit.

## 4. Core Research Question and Hypotheses

Let:

- `t` denote an observation's completed 1-minute candle index.
- `X_t` denote numerical features that were observable by decision time.
- `Z_t` denote any additional observable, timestamped context (news text, event descriptions, etc.).
- `Y_t` denote the realized five-minute-ahead outcome.
- `J_t` denote Jev's typed output.
- `f_L` denote a LightGBM model.

### H1 — Numerical market features have predictive content

A properly constructed LightGBM model using `X_t` beats prespecified naïve/statistical baselines **on unseen periods** under relevant predictive metrics. A failure of H1 is a reason to investigate labels, sampling, data quality, and feature sufficiency before adding models.

### H2a — Jev provides useful representation from the same features

`f_L(X_t, J_t(X_t))` improves on `f_L(X_t)` in strictly out-of-sample tests. This tests practical value from a different inductive bias, not acquisition of new information.

### H2b — Jev extracts incremental information from additional context

`f_L(X_t, J_t(X_t, Z_t))` improves on `f_L(X_t)` **and** appropriate `X_t + Z_t` controls. This is the stronger complementary-use hypothesis.

### H3 — Predictive improvement survives implementation costs

The resulting fixed policy, with realistic entry timing, spreads, fees, slippage, and turnover, improves risk-adjusted **net** performance over the matching baselines in a separate walk-forward paper simulation.

### H4 — The operational cost is justified

Any improvement is meaningful after model cost, data acquisition, latency, outages, retries, maintenance, and reliability are accounted for.

### Information-theoretic qualification

For a fixed pretrained Jev and predictions computed from `X_t` alone, the data-processing inequality implies:

`I(Y_t ; J_t) <= I(Y_t ; X_t)`.

Jev cannot manufacture genuinely new information by reformatting the same input. It can still help **a specific finite-data LightGBM learner** extract a useful representation. For truly additional input `Z_t`, ask whether `I(Y_t ; Z_t | X_t) > 0` and whether Jev extracts useful parts of that information more effectively than alternative models.

Mutual information is a useful conceptual lens, **not** a promise that a high-dimensional conditional-information estimator will be statistically reliable on financial data. Practical tests should focus on preregistered held-out performance and ablation comparisons.

## 5. Feasibility and Critical Engineering Judgments

| Proposal | Engineering feasibility | Scientific confidence | Decision |
|---|---|---|---|
| Binance market-data-only ingestion | High if reachable and within terms | High for data acquisition; not for edge | Adopt |
| Parquet + DuckDB + Polars feature pipeline | High | High for reproducibility | Adopt |
| Statistical and LightGBM baselines | High | Strong baseline methodology | Adopt |
| Jev market-state `choice` inference | Plausible to integrate | **Unproven** as BTC forecaster | Experimental |
| Jev as a semantic feature extractor | Plausible | Potentially useful, requires controls | Experimental |
| Jev fine-tuned on BTC data | **Not supported by documented customer tuning** | N/A | Do not plan around it |
| Train LightGBM on Jev probabilities | High | Depends on OOS gain | Test |
| Predict exact `price-after` from a `choice` | Conceptually invalid | None | Reject |
| Deterministic paper broker | High | Strong testability | Adopt |
| Live real-capital strategy | Outside scope | Not established | Prohibited |

### Five-minute BTC is difficult

The five-minute horizon is noisy. Frequent overlapping labels, a strong random-walk baseline, competition, spread/fees, and asynchronous information availability all make small reported gains easy to overinterpret. Most of the project's research value may be in the *falsifiable evaluation framework* rather than in a profitable trading policy.

### Critical distinction: semantic confidence vs market probability

A Jev answer such as `choice = bullish` with `probabilities.bullish = 0.73` need not mean a realized 73% chance of positive BTC return in the next five minutes. It may simply be confidence in a classification rubric, e.g. “Does this snapshot appear bullish?” Its relation to realized future outcomes must be **learned and calibrated empirically**.

## 6. Proposed System Architecture

### 6.1 Research and paper-trading architecture

```text
                             PUBLIC MARKET INPUTS
      Binance REST historical klines   Binance WS closed 1m klines
                    \                           /
                     \                         /
                      v                       v
                  INGESTION + VALIDATION + TIME GATING
                   raw events / replay / dedupe / gaps
                                  |
                                  v
                       CANONICAL MARKET DATA
                     Parquet + DuckDB + manifests
                                  |
                                  v
                    DETERMINISTIC FEATURE ENGINE
                  X_t + lineage + availability metadata
                                  |
                    +-------------+--------------+
                    |             |              |
                    v             v              v
                Statistics     LightGBM       Optional Jev
                baseline       baseline      assessment J_t
                    |             |              |
                    |             +------+-------+
                    |                    |
                    +--------------------+
                                         v
                       CALIBRATION / EVALUATION
                      frozen scores + OOS predictions
                                         |
                                         v
                      DETERMINISTIC DECISION POLICY
                          HOLD / virtual buy / sell
                                         |
                                         v
                      RISK GATE + VIRTUAL PAPER BROKER
                   simulated fills / wallet / ledger / audit
                                         |
                                         v
                      METRICS / REPORTS / REPLAY ARTIFACTS

        Separate grounded research lane:
        LightRAG evidence -> citation gate -> optional LLM summary
        (No direct path from LLM or Jev to executable exchange orders.)
```

### 6.2 Control plane vs data plane

**Data plane:** market packets, validated candles, derived features, predictions, simulated fills, and virtual portfolio states.

**Control plane:** configurations, allowlists, network policy, model registry, dataset versions, hashes, release gates, budgets, kill switches, and audit trails.

Do not grant the inference processor responsibility for either exchange credentials or broker account state transitions.

### 6.3 Computational roles

| Role | Ownership | Must be deterministic? |
|---|---|---|
| Market data parsing | Binance adapter | Yes, given input bytes |
| Candle QA and time eligibility | Data validator | Yes |
| Feature calculation | Feature engine | Yes, under pinned version |
| Statistical inference | Numerical models | Reproducible under pinned versions/seeds |
| Jev semantic classification | Jev adapter | No; record exact output/version |
| Local/cloud explanation | Summarizer | No; optional, grounded |
| Model calibration | Offline trainer | Reproducible; fitted only on train/calibration split |
| Trading policy | Policy engine | Yes, given inputs and policy version |
| Exposure and risk limits | Risk gate | Yes |
| Fill simulation | Virtual broker | Reproducible with pinned fill assumptions |
| Report grounding | Evidence/citation validator | Yes for verifiable checks |

## 7. Technology Stack and Trade-offs

### 7.1 Recommended minimal stack (v0)

| Layer | Preferred choice | Why now | Alternatives / when to change |
|---|---|---|---|
| Language | Python >=3.11 | Existing repo, ML tooling | No change |
| Public data | Binance Spot REST + WebSocket | Accessible market data, no trading keys | Other vendor only after proving data limitations |
| Async networking | `httpx` + `websockets` (proposed) | Simple bounded IO | `aiohttp` if a unified client is preferred |
| Validation | Pydantic, strict domain validators | Typed boundaries and explicit failures | Dataclasses for low-level hot path |
| Price representation | `Decimal`/original strings at ingestion | Fidelity and auditability | Integer tick units if explicitly normalized |
| Analytical representation | Float64 numerical arrays | Fast model features | Preserve exact prices outside feature layer |
| Dataframes | Polars | Efficient rolling/columnar transforms | Pandas if existing code already standardizes it |
| File storage | Parquet + PyArrow | Columnar, reproducible | No database server initially |
| Analytical queries | DuckDB | SQL against Parquet | SQLite for metadata, not large analytics |
| Metadata ledger | SQLite | Lightweight ACID manifests/checkpoints | PostgreSQL later if multi-writer scale requires |
| Numeric/statistical | NumPy, SciPy, statsmodels | Baselines and diagnostics | Keep math local |
| Primary ML | LightGBM | Strong tabular learner, low inference cost | XGBoost/CatBoost comparison later |
| Calibration | scikit-learn | Platt/isotonic and validation tools | Custom if needed after evidence |
| Experiment history | MLflow (optional at first) | Artifact/parameter/metric tracking | JSON manifests first if lighter |
| Jev | TypeSafe HTTP/Python SDK | Typed probabilistic experiment | Provider must remain optional |
| Local model | CPU classifier or small quantized LLM | Reduce cloud dependency where useful | llama.cpp/Ollama/vLLM only after measurements |
| Grounded prose model | Existing optional OpenAI adapter | Preserve `STACK.md` architecture | Avoid premature multiple summarizers |
| Charts/inspection | Matplotlib/Plotly, notebooks | Research diagnostics | Dashboard only after stable metrics |
| Test framework | pytest | Matches repository setup | Property-based tests with Hypothesis where helpful |

### 7.2 Rejected early infrastructure

Kafka, Redis queues, Kubernetes, high-availability clusters, Ray, and elaborate multi-agent orchestration solve scale/coordination problems the initial *single-symbol, minute-cadence* study has not demonstrated. Start with one controlled producer, one durable writer, an offline trainer, and a separate paper-replay process. Add complexity after measured bottlenecks.

### 7.3 Why hybrid must be capability-based

“Hybrid” does **not** mean “always send a request to local and then to cloud.” A correct router asks:

1. Is inference necessary at all? Can exact Python/statistical code answer it?
2. Does the task need semantic comprehension or numerical prediction?
3. Does its privacy policy permit sending this state to a remote provider?
4. Which calibrated candidate meets accuracy/latency/cost constraints?
5. Is the caller in an authorized research, shadow, or paper mode?

Optional local and cloud models should be **substitutable behind typed interfaces** only when they implement the same kind of task. Do not pretend a Jev classifier, numerical forecaster, and generative summarizer all provide an interchangeable `generate()` operation.

## 8. Binance Market-Data Pipeline

### 8.1 Public-only endpoints

For market data only, official Binance documentation lists endpoints that do not require API authentication:

```text
REST:      https://data-api.binance.vision/api/v3/klines
WebSocket: wss://data-stream.binance.vision:443/ws/btcusdt@kline_1m
```

`GET /api/v3/klines` requires symbol and interval and supports time bounds/pagination. WebSocket kline payloads carry the nested kline field `x`, which signals whether that kline has closed.

These are public market-data paths **not private account/trading endpoints**. They remain subject to current exchange rules, geographic access constraints, rate limits, and terms. “No API key required” is not a guarantee of unrestricted usage, uptime, or a permanent free service.

### 8.2 Historical ingestion workflow

```text
Define UTC time range and symbol
 -> Query pages of 1-minute historical klines
 -> Persist raw response with retrieval metadata
 -> Parse each bar into canonical schema
 -> Validate timestamps, ordering, prices, and volume
 -> Upsert/deduplicate by logical candle key
 -> Detect missing one-minute intervals
 -> Write immutable Parquet partitions
 -> Record manifest and checksum
 -> Emit completeness/data-quality report
```

**Operational decisions:**

- Use bounded page sizes and respect response-reported rate-limit information.
- Retry only idempotent public reads with bounded exponential backoff and jitter.
- Never silently interpolate missing OHLCV bars; record gaps and quarantine affected windows.
- Historical candles may be revised or differ from previously captured live data. Preserve original captures and reconciliation policy; do not quietly overwrite evidence.
- Pin the requested time interval in UTC and log client clock plus server/event timestamps.
- Query data availability before treating a newly closed bar as complete.

### 8.3 Live ingestion workflow

```text
Connect market-data-only WebSocket
 -> Decode message
 -> Validate symbol + kline interval
 -> Persist raw receipt / event metadata
 -> Ignore nonfinal candle for canonical commit (x == false)
 -> On x == true: normalize and validate bar
 -> Idempotent candle commit
 -> Detect open-time discontinuity
 -> REST backfill missing interval(s)
 -> Confirm dataset continuity
 -> Publish feature-eligible candle
```

**Time alignment nuance:** Binance's one-minute kline close timestamp is typically the **last millisecond of the interval**, not the instant of the next executable trade. Store `open_time_ms`, `close_time_ms`, `event_time_ms`, `received_at_ms`, and `eligible_at_ms` separately. Distinguish logical bar boundaries from real information availability.

**Reconnect expectations:** WebSocket sessions can close/disconnect; plan proactive renewal as documented, heartbeats, bounded backoff, data-gap detection, and REST reconciliation. On unknown gaps or stale state, suppress new model decisions and virtual orders.

### 8.4 Phase 0 collection levels

**Required:** historical and live *closed* 1-minute klines.
**Optional next:** best bid/ask / `bookTicker` for executable-price proxies.
**Deferred:** synchronized depth-book reconstruction, individual trades, funding/open interest, on-chain and news feeds.

Order-book imbalance requires consistent book snapshots/delta synchronization, not merely a feature column added to candle data. Do not claim microstructure quality before this subsystem is verified.

## 9. Data Storage, Lineage, and Schemas

### 9.1 Proposed datasets and partitioning

```text
data/btc_paper/
  raw/
    binance/spot/BTCUSDT/kline_1m/date=YYYY-MM-DD/...
  canonical/
    candles/symbol=BTCUSDT/interval=1m/date=YYYY-MM-DD/...
  features/
    feature_set=v1/symbol=BTCUSDT/date=YYYY-MM-DD/...
  labels/                         # OFFLINE ONLY; never live input
    target_version=v1/...
  predictions/
    experiment_id=.../...
  simulation/
    run_id=.../...
  metadata.sqlite
  manifests/
    dataset_id=...json
```

Partitions are immutable or atomically replaced with a new dataset version, never modified without updating hashes/lineage. A feature dataset references exact candle dataset IDs. Models reference exact feature/label dataset IDs and training windows.

### 9.2 Canonical candle contract

| Field | Type | Required invariant |
|---|---|---|
| `venue` | string | `binance` |
| `market_type` | string | `spot` |
| `symbol` | string | `BTCUSDT` |
| `interval` | string | `1m` |
| `open_time_ms` | int64 | UTC; aligned minute start |
| `close_time_ms` | int64 | Exchange-reported UTC close; consistent interval |
| `open`, `high`, `low`, `close` | decimal or exact string | All positive; `low <= min(open, close) <= max(open, close) <= high` |
| `base_volume`, `quote_volume` | decimal or exact string | Nonnegative |
| `trade_count` | int64 | Nonnegative |
| `taker_buy_base`, `taker_buy_quote` | decimal or exact string | Nonnegative and within plausible totals |
| `is_final` | bool | Must be true for canonical feature-eligible bars |
| `exchange_event_time_ms` | nullable int64 | From stream if provided |
| `received_at_ms` | int64 | Local recorded receipt time |
| `eligible_at_ms` | int64 | First safe availability for this observation |
| `source_batch_id` | string | Links to raw ingest |
| `capture_mode` | enum | `historical_rest` or `live_ws` |
| `source_revision` | integer/string | Tracks reconciliation |
| `quality_status` | enum | `valid`, `quarantined`, `reconciled`, ... |

**Logical key:** `(venue, market_type, symbol, interval, open_time_ms)`.
**Physical provenance key:** logical key plus `source_batch_id` or revision. Raw captures retain duplicates/revisions; a versioned canonical view resolves conflicts under a documented rule.

### 9.3 Market-state contract (illustrative, not observed data)

```json
{
  "schema_version": "btc.market_state.v1",
  "symbol": "BTCUSDT",
  "venue": "binance",
  "market": "spot",
  "horizon_seconds": 300,
  "decision_time_ms": 1790000002500,
  "latest_final_candle_open_ms": 1789999940000,
  "feature_set_id": "market-features-v1",
  "input_dataset_hash": "sha256:<computed-at-runtime>",
  "features": {
    "log_return_1m": 0.0008,
    "log_return_5m": 0.0021,
    "realized_vol_30m": 0.0014,
    "momentum_15m": 0.0032,
    "volume_zscore_30m": 1.25,
    "rsi_14": 58.2,
    "range_pct": 0.0011,
    "taker_buy_ratio": 0.56
  },
  "quality": {
    "final_candles_only": true,
    "warmup_complete": true,
    "has_unresolved_gaps": false,
    "is_stale": false
  }
}
```

The timestamps above are synthetic examples; their purpose is to illustrate separation of candle time and decision time, not to certify chronological consistency for a real stream.

### 9.4 Model prediction contract

```json
{
  "schema_version": "btc.prediction.v1",
  "observation_id": "<deterministic-id>",
  "prediction_task": "five_minute_direction",
  "model_id": "<pinned-version>",
  "question_version": "<pinned-question-set>",
  "input_dataset_hash": "<hash>",
  "prediction_created_at_ms": 0,
  "raw_model_scores": {
    "down": 0.31,
    "neutral": 0.22,
    "up": 0.47
  },
  "score_semantics": "uncalibrated_model_classification",
  "calibration_id": null,
  "decision_eligible": false
}
```

These are **illustrative** scores. They must not be presented as BTC empirical probabilities, nor mapped to trade actions before calibration and policy approval.

### 9.5 Separation between labels and live inputs

`Y_t` is constructed offline after future data arrives. Store it in a separate label dataset and enforce a hard read boundary so the online feature constructor and Jev request serializer cannot import label or future-return columns.

### 9.6 Reproducibility manifest

Record at minimum:

- Raw source URL type and request windows (without credentials).
- Capture mode, retrieval times, exchange time, and data availability policy.
- Dataset IDs, checksums, partition layout, missing/gap reports.
- Feature graph/version, code revision, environment/lockfile hash.
- Target definition/version, split IDs, random seed, calibration ID.
- Model name and exact version, input/question version, provider response fingerprint.
- Trading policy version, fill assumptions, fee schedule and simulated-wallet initial state.

## 10. Market Features and Five-Minute Targets

### 10.1 Basic deterministic features

Let `C_t, H_t, L_t, V_t` denote the **final** close/high/low/base-volume for the minute indexed `t`. Initial candidate features:

| Feature | Definition | Important caveat |
|---|---|---|
| `log_return_1m` | `ln(C_t / C_{t-1})` | Final bars only |
| `log_return_5m` | `ln(C_t / C_{t-5})` | Must not be confused with future label |
| `return_15m` | `C_t / C_{t-15} - 1` | Past-only momentum |
| `realized_vol_30m` | Rolling std of one-minute log returns | Specify sample std, NaN policy, no unannounced annualization |
| `range_pct` | `(H_t - L_t) / C_t` | Well-defined close denominator |
| `volume_zscore_30m` | `(V_t - rolling_mean(V)) / rolling_std(V)` | Zero-std/low-liquidity handling |
| `rsi_14` | RSI with pinned smoothing convention | Wilder vs EMA/SMA differs |
| `taker_buy_ratio` | `taker_buy_base / base_volume` | Undefined if volume=0 |
| `time_of_day` | UTC cyclical encoding | Time-only pattern may drift |
| `missingness/quality` | Gap/stale/source quality flags | May instead gate inference outright |

Start with a **small, interpretable** feature set. Technical indicators computed from the same OHLCV observations are often highly redundant; more indicators do not guarantee new signal.

### 10.2 Optional features after the first baseline

- Best bid/ask spread in basis points at the *actual intended execution time*.
- Volume-weighted price and trade-flow imbalance from auditable trades data.
- Volatility-regime summaries and autocorrelation diagnostics.
- Order-book imbalance only with correctly synchronized snapshots/deltas.
- Time-qualified public event/news semantic factors.
- Funding/open interest only as additional cross-market *context* if sourced legally and timestamped; execution remains spot.

### 10.3 Define the target before training

The simplest **research target** is a completed-candle five-minute forward return:

`r_{t,t+5} = ln(C_{t+5} / C_t)`.

Possible supervised targets:

- **Regression:** continuous `r_{t,t+5}`.
- **Binary classification:** `1[r_{t,t+5} > 0]`.
- **Three-class direction:** `UP`, `DOWN`, `FLAT`, with boundaries defined on the training period and frozen for validation/testing.
- **Cost-aware classification:** use a prespecified economic threshold in basis points; this is a separate target version, not interchangeable with raw directional labels.

**Crucial:** The canonical `C_t` is not automatically a fill price that is reachable *after* bar `t` closes and the prediction is processed. Keep the convenient research label separate from the **executable-return label** or broker's PnL calculation, which starts at the first eligible post-decision bid/ask quote/fill.

### 10.4 Availability and label completion

- Features: only values with `available_at <= decision_time`.
- Predictions: computed at a measured time after bar closure.
- Labels: materialize only after their future horizon is observed.
- Simulated entry: price from a quote/trade **after** decision completion, plus modeled delay.
- Calibration and training: exclude information that was not known by each historical decision time.

### 10.5 Overlapping labels

At 1-minute cadence with 5-minute targets, consecutive labels share four minutes of future market evolution. They are serially dependent. Use chronological evaluation with appropriate boundary purges/embargoes and dependence-aware confidence intervals. Never randomly shuffle and treat observations as IID.

## 11. Jev: Capabilities, Limits, and Research Role

### 11.1 What Jev is

TypeSafe describes Jev as a **System One decision model** that consumes a text/structured `state` and typed questions rather than producing an unconstrained natural-language report. Core primitives include:

- **Choice:** choose from supplied options; returns probabilities and a choice-confidence statistic.
- **Score:** evaluate ordered rubric levels; returns score/probabilities/confidence.
- **Noul:** evaluate a yes/no statement; returns a 0–1 value (without the same separate confidence field).

The TypeSafe documentation also describes an image-oriented `Box` primitive, but it is not relevant to BTC market-state inference.

Jev evaluates multiple well-scoped questions over a shared state; combining answers into risk or financial decisions remains **application code's job**.

### 11.2 Verified version/price facts (2026-10-17)

At the time of drafting, the official model listing shows:

| Property | Officially documented value |
|---|---|
| Latest new Jev release | `jev-1.14.0` (released 2026-10-14) |
| Another listed release | `jev-1.13.0` |
| Price | **USD $0.042 / 1 million input tokens**, equivalent to **$42 / 1 billion** |
| Output token billing | Free, as stated in the official model listing |
| Default context constraints | 64k tokens/request; 32k tokens per question together with shared state |
| Model endpoint | `POST /v1/systemone` |
| Customer weight tuning / LoRA | **Not supported** per official customization guidance |
| Version policy | Pin explicit model ID for controlled experiments; do not silently depend on a moving alias |

*Check current documentation and your own account limits before any budget or integration approval.* Earlier discussion used a hypothetical `$10/1B` claim; the verified published rate is **$42/1B**. Some third-party pages may be stale.

### 11.3 What “fine-tuning” means here

The official Jev model documentation states that customer-specific fine-tuning/LoRA adaptation is not how Jev is customized. It recommends:

1. Supplying task-specific `state`.
2. Designing atomic instructions and criteria.
3. Combining typed scores in code.
4. Training a **separate classical downstream model** over Jev-derived features, where useful.

Therefore, “fine-tune Jev to forecast BTC” is **not an available baseline assumption**. Train LightGBM/CatBoost, calibrators, or a separate local model instead. If TypeSafe's capability changes later, evaluate it as a new, versioned R&D proposal.

### 11.4 Appropriate Jev questions

Potential semantic questions (research examples, **not API-ready request definitions**):

- “Given the available timestamped news, is this event primarily supportive, adverse, or unrelated to BTC spot demand?”
- “Does the provided evidence actually support this proposed market-regime explanation?”
- “Is the supplied narrative internally contradictory or based on stale information?”
- “How severe is the described market shock according to this fixed rubric?”

A numerical-state experiment can also ask whether a snapshot matches a **defined descriptive regime** such as trending / range-bound / high-volatility. That remains a *regime classification* question, not a validated probability of future returns.

### 11.5 Inappropriate interpretations

- A `BUY/SELL/HOLD` label from Jev is **not** a broker instruction.
- A `bullish=0.9` choice output is not necessarily a calibrated 90% forecast of a positive 5-minute return.
- A confidence statistic derived from a concentrated choice distribution is **not** the same as economic expected value or out-of-sample correctness probability.
- `price-after` is **not** directly inferable from a directional score. Predicting a median and price interval requires a separate statistical distribution forecast or empirically validated conditional-return model.

### 11.6 Why Jev could help—and why it might fail

Potential gains:

- Different pretrained representation / inductive bias compared with gradient-boosted trees.
- Stronger semantic interpretation of news/evidence than OHLCV models.
- Cheap batched typed assessment if the measured endpoint performance matches the workload.
- Useful auxiliary features with explicit output schemas.

Potential failure modes:

- Limited signal in common technical indicators.
- Jev outputs correlated with existing features and therefore redundant.
- Generic semantic confidence disconnected from realized market returns.
- Model-version changes, sample instability, or calibration drift.
- Increased latency and transaction costs erasing any benefit.
- Additional `Z_t` data arriving too late to help a five-minute trading horizon.

### 11.7 Jev role within the broader project

Two Jev lanes are conceptually separate:

- **Research lane:** classify passages/claims, assess sources, help grounding and explanation.
- **Sandbox prediction lane:** produce experimental, timestamped features evaluated against five-minute outcomes.

The first can be useful even if the second fails. No model's output may bypass deterministic governance.

## 12. Hybrid Cloud/Local Model Lifecycle

### 12.1 Lifecycle states

```text
UNINITIALIZED
    -> INITIALIZING
    -> READY
    -> DEGRADED  -> RECOVERING -> READY
    -> UNAVAILABLE
    -> SHUTTING_DOWN
    -> STOPPED
```

A runtime manager maintains state **per provider and per pinned model version**. It must distinguish provider health from task suitability and calibration status.

### 12.2 Cloud model loading

Cloud “loading” means acquiring/configuring a client connection and request policy, **not** loading neural-network weights into local VRAM:

- Parse provider credentials from protected environment/secret store (never hardcode).
- Validate egress policy, model allowlist, rate/usage budget and task authorization.
- Initialize/reuse HTTP client and connection pool.
- Configure concurrency limit, request deadlines, retry budget, circuit breaker.
- Make no real API requests until the project's existing explicit model-call approval gate is satisfied.
- Pin model version; log effective returned model version.
- Persist only permitted/redacted payloads and response fingerprints.

### 12.3 Local model loading

Local inference may require:

- Explicit model artifact version and integrity checksum.
- CPU/GPU compatibility validation and resident model memory budget.
- Model weight loading and warm-up as needed.
- Bounded input size, batching/concurrency, KV-cache sizing for generative models.
- Measured tokens/s, latency distribution, thermal behavior, RAM/VRAM peak.
- Graceful unload/reclaim on idle and robust crash handling.

For a machine with approximately 8 GB GPU VRAM, small quantized models are sensible *candidates*, not capacity guarantees. A local classifier or small text model may beat an LLM for narrow semantic tasks. LightGBM numerical inference generally does not require a GPU inference server.

### 12.4 Routing policy (proposed)

| Task | First preference | Other candidate | Failure behavior |
|---|---|---|---|
| Arithmetic/feature computation | NumPy/Polars | None | Reject invalid state |
| Tabular return prediction | LightGBM / statistical baseline | Another pinned local model | Return no prediction if invalid |
| Grounded citation checking | Deterministic references + rule checks | Optional Jev semantic support assessment | Deterministic report/abstain |
| Free-text market explanation | Existing optional summarizer | Tested local summarizer | Deterministic explanation |
| Jev representation test | Pinned Jev API during approved experiment | Cached recorded response in unit tests | Skip feature or mark unavailable |

**Do not silently substitute** a different model for Jev inside a frozen experiment, because that changes the treatment being evaluated. A provider failure should be recorded as missing inference/abstention; baseline and paper engine still work. If fallback is experimentally desired, give it a separate model/configuration ID and evaluate it explicitly.

### 12.5 Reliability controls

Timeout budgets; bounded queues; rate-limit-aware retries; idempotent cache keys; budget ceilings; health status; no unbounded failover storms; no inference on stale data; instrument p50/p95/p99 latency, error categories, successful/failed decisions, and GPU utilization. All runtime clocks use monotonic elapsed timing plus UTC wall-time for audit.

## 13. Inference Processing and Internal Interfaces

### 13.1 Typed domains—do not collapse them

Propose separate conceptual interfaces:

```text
MarketDataSource        -> Candle / Quote / DataQuality
FeatureComputer         -> FeatureSnapshot
NumericForecaster       -> PredictiveDistribution or TargetScore
EvidenceClassifier      -> SemanticAssessment
ResearchSummarizer      -> GroundedSummary
ProbabilityCalibrator   -> CalibratedPrediction
DecisionPolicy          -> PaperOrderIntent or HOLD
RiskGate                -> Accepted / RejectedIntent
PaperBroker             -> VirtualFill / PortfolioState
```

These are *responsibility contracts*, not exact Python class names. Their concrete shape should be resolved after the repository audit.

### 13.2 Processing stages

1. **Receive:** ingest an immutable, time-qualified event or research task.
2. **Validate:** parse and enforce schema, chronological validity, source freshness, and availability.
3. **Transform:** compute deterministic features and hashes.
4. **Determine task:** numeric forecasting vs semantic interpretation vs narrative explanation.
5. **Route:** no model by default for deterministic computations; optional model only if task-specific policy allows it.
6. **Infer:** pin version and criteria; capture raw outputs, latency, usage, and errors.
7. **Validate output:** verify probability bounds, supported label set, numeric finiteness, matching observation ID/version, and provenance.
8. **Calibrate:** apply the matching held-out-fitted calibrator, when available.
9. **Abstain/gate:** if invalid, stale, missing, uncalibrated for the requested policy, or provider unavailable, do not create a new paper signal.
10. **Record:** store immutable prediction and decision events, including `NO_TRADE`.
11. **Report:** render research with citation gating, and simulated portfolio analytics separately.

### 13.3 Idempotency and cache design

The cache fingerprint should cover:

`(observation_id, feature_version, input_hash, provider, model_version, question_version, inference_configuration)`.

A cached response is safe for **replay** only when these fields match. In a live paper session, cached answers must not be mistaken for freshly valid information on a newer market snapshot. Store expiry and availability constraints separately.

### 13.4 User-facing explanation remains optional

The generative model may explain “why this snapshot was classified as higher volatility” or “which cited article supports a thesis,” but it must not invent a risk approval or fabricate information from market data it did not receive. Reports should separate:

- Observed data and facts.
- Derived deterministic quantities.
- Experimental model assessments.
- Actual realized outcomes.
- Assumptions and known limitations.

## 14. Probability, Calibration, and Decision Theory

### 14.1 Separate probability objects

The following objects have different meanings:

1. `P(semantic claim supported | supplied evidence)`.
2. `P(UP | current market state)`.
3. `P(net executable return > 0 | current state, fees, delay)`.
4. A model's **choice confidence** as concentration of its categorical output.
5. A prediction interval for future log return or price.

Never label these generically as `confidence` and interchange them.

### 14.2 Calibration

For a binary event `Y ∈ {0,1}` and forecast `p`, Brier score is:

`BS = (1/N) * sum((p_i - y_i)^2)`.

Also evaluate log loss, reliability diagrams, event-base-rate drift, ECE (with cautious bin choice), and separate calibration by market regime. Calibration must be learned on training/validation periods, **not** on the final test.

### 14.3 Choice confidence is not accuracy

TypeSafe documents a `Choice` confidence statistic derived from the maximum choice probability and number of options. It is a measure of **distribution concentration**, not a measured rate of correctness on future BTC returns. Use observed out-of-sample frequencies to determine whether and how a Jev output should be mapped into a target probability.

### 14.4 Why `p_up` is not enough for BUY

Suppose, hypothetically:

- `p_up = 0.70`.
- Average positive return conditioned on `UP` is `+0.05%`.
- Average negative return conditioned on `DOWN` is `-1.00%`.

Expected return before costs is:

`0.70 * 0.05% + 0.30 * (-1.00%) = -0.265%`.

Thus, higher directional accuracy can coexist with negative trading expectation. Probability of direction alone does not specify the conditional payoff distribution.

For a candidate long trade, under clearly defined conditioning assumptions:

`EV_long ≈ p_up * E[r | up] + p_down * E[r | down] - expected_round_trip_cost`.

A real evaluation must include transaction sizes, bid/ask pricing, order timing, fees, slippage, inventory, and execution uncertainty.

### 14.5 Price forecasting

If a model estimates a distribution of five-minute log returns `R`, a hypothetical future price is:

`P_future = P_reference * exp(R)`.

Median/quantile intervals require a **return-distribution estimate** and out-of-sample coverage tests. A Jev `Choice(UP, DOWN, FLAT)` distribution does **not** by itself identify the conditional magnitude distribution needed to output an honest `price-after`.

### 14.6 Policy design

Start with fixed, transparent and risk-bounded policy options:

- `HOLD` always available.
- Spot `BUY` opens/increases a virtual BTC position within a fixed allocation cap.
- Spot `SELL` reduces existing virtual BTC; it cannot short.
- No-trade band for insufficient expected edge after costs.
- Stale, uncalibrated, invalid, or missing prediction => abstain.
- The same policy family/parameter-selection protocol must be applied to all benchmark arms.

Threshold policies are useful to test the plumbing, but `P(UP) > 0.65` is **not** a production-grade expected-utility rule and should not be treated as such.

### 14.7 Bayesian computation

Bayesian updating is relevant when likelihoods, priors, event dependencies, and outcome semantics are specified. It is not appropriate to multiply arbitrary Jev semantic scores and call the result a posterior. Duplicate reports of the same underlying news source are dependent evidence; treating them as independent overstates certainty.

## 15. Model Comparisons and Incremental-Value Experiments

### 15.1 Benchmark matrix

| ID | Inputs | Learner/processor | Primary purpose |
|---|---|---|---|
| B0 | Historical base rates | Constant / no-skill predictor | Sanity baseline |
| B1 | Historical returns | Logistic regression / simple statistical forecasting | Lightweight numeric control |
| B2 | `X_t` | LightGBM | **Primary numerical baseline** |
| J0 | `X_t` | Jev, pinned question set | Same-input model assessment |
| J1 | `X_t + J_t(X_t)` | LightGBM | Test Jev representation on same features |
| Z0 | `X_t + Z_t` or independently derived `Z` features | LightGBM / independent encoder | Control for additional information |
| J2 | `X_t + J_t(X_t, Z_t)` | LightGBM | Test Jev on additional context |
| L0 | `X_t + local semantic features` | LightGBM | Local-vs-Jev cost/quality control |
| P0 | Baseline predictions | Frozen paper policy | Economic baseline |
| P1 | Best eligible Jev-augmented predictions | Same policy protocol | Incremental economic value |

Always include a **buy-and-hold** portfolio baseline, a no-trade strategy, and clearly specified simple momentum/mean-reversion controls in economic comparisons. Predictive-score controls and trading-policy controls answer different questions.

### 15.2 Avoid confounded comparisons

If J2 receives news text and B2 does not, J2's gain is **not evidence that Jev is a superior model**; it may simply have more data. Compare J2 to Z0 and L0, ideally with the same cleaned event data, availability timestamps, and model-development budget.

**Pretraining caveat:** Even with `X_t` alone, a pretrained Jev contains priors acquired during pretraining. That does not violate information theory, but it complicates any claim that the advantage stems *solely* from same-input representation. Treat pretrained model knowledge and release dates as part of experimental conditions.

### 15.3 Time-aware Jev questions

Do not directly let a broad prompt “Will BTC go up?” define target semantics. Define the event precisely, including horizon, neutral band if any, and what input is allowed. Keep question text/version stable during a frozen evaluation. Broad exploratory question design is permitted only on development periods, not after looking at final-test performance.

### 15.4 Model version availability and historical replay

A Jev model served today may have been pretrained on information after historical test observations. This creates potential **pretraining temporal contamination** even if the request contains only past market state. A retrospective Jev backtest is therefore not automatically a strict historical out-of-sample simulation. Mitigations:

- Explicitly document the model release and unknown training cutoff.
- Do not assume the model has never seen historical prices/news.
- Use retrospective results as exploratory evidence, not sole proof of causal forecasting ability.
- Prefer **prospective shadow-mode evaluation** with predictions committed before outcomes exist.
- Freeze Jev versions and raw results for reproducibility.

This distinction is particularly important for general pretrained semantic models evaluated on old market headlines.

### 15.5 Feature ablation and importance

Include:

- `X` only vs `X + J(X)`.
- `X + Z` vs `X + J(X,Z)`.
- Jev features grouped by semantic question.
- Market-only vs news-only vs combined.
- Regime and calendar subperiod performance.
- Error correlation and prediction disagreement.
- Permutation importance/SHAP as diagnostic tools, not causal proofs.

### 15.6 Model selection

Prefer the *simplest* model whose measured uplift is stable and economically meaningful. A Jev win must satisfy a prespecified acceptance threshold in held-out log loss/Brier, survive realistic execution costs, and not depend on one anomalous month or a poorly controlled additional data source.

If Jev does not add value to BTC prediction, retain it only where it provides demonstrated **research summarization/evidence** value. Failure to find alpha is a useful negative scientific result.

## 16. Paper Broker, Market Simulation, and Risk Boundary

### 16.1 Strict authorization model

```text
Market data / model scores
    -> candidate paper signal
    -> deterministic policy checks
    -> deterministic risk validation
    -> VIRTUAL broker only
    -> virtual fill event
    -> virtual BTC + USDT ledger
```

There is **no code path from this experiment to exchange order placement**. The safest initial implementation is not a hidden disabled order client—it is the **absence of authenticated trade functionality** in the experimental process.

### 16.2 Virtual portfolio

A reasonable configurable starting state for simulation is, for example, **10,000 virtual USDT** and zero BTC. The number is a test parameter, not a claim about an actual account.

Ledger fields should include:

- Virtual free USDT and BTC quantities.
- Fee debits and execution notional.
- Order intent vs accepted order vs simulated fill.
- Realized/unrealized PnL and mark-to-market equity.
- Maximum position size, turnover, and peak-to-trough drawdown.
- Rejected/expired order reasons and risk-override attempts.

### 16.3 Fill models, in increasing realism

**V0 — coarse OHLCV-only:** execute at next eligible *post-decision* bar open or clearly conservative proxy, charge configurable fees and spread/slippage assumptions. A candle close cannot be used as an instantaneous trade after that close unless a causally valid quote exists.

**V1 — bid/ask-aware:** include collected best quotes and timestamped decision/inference latency. Buy at ask, sell at bid, plus fees and estimated slippage.

**V2 — liquidity-aware:** incorporate trade size relative to volume, depth, partial fills and market impact if suitable order-book/trades data is available. Must model quote staleness and packet loss.

**Limitations:** Paper fills do not equal real fills. OHLCV alone cannot perfectly reconstruct spreads, order-book depth, queue position, price impact, or exact market-order completion.

### 16.4 Spot inventory rules

- Spot `BUY`: requires virtual USDT to cover simulated purchase + fees.
- Spot `SELL`: requires available virtual BTC.
- Negative BTC inventory is forbidden.
- Borrowing, leverage, futures funding, liquidation and short sale are out of scope.
- No strategy may create synthetic leverage through inconsistent accounting.

### 16.5 Deterministic safety gates

| Gate | Behavior on failure |
|---|---|
| No authenticated trading client in experiment | Build/release fails if introduced |
| Stale or missing market data | `HOLD`, no new orders |
| Uncertain data gap at decision time | `HOLD`, no new orders |
| Model/feature version mismatch | Reject candidate |
| Prediction uncalibrated for required policy | Abstain |
| Notional > configured virtual risk limit | Reject |
| Insufficient virtual balance | Reject |
| Excessive modeled drawdown | Stop new risk-increasing paper orders |
| Duplicate intent | Idempotent handling, not two fills |
| Provider timeout | Record failed inference, no optimistic trade |
| Unexpected process restart | Reconcile paper ledger from durable events |

### 16.6 Audit events

Every paper decision should produce an immutable record: source candle IDs, exact feature snapshot and hash, prediction ID, model and policy versions, eligibility time, accepted/rejected intent, modeled spread/fee/slippage, virtual fill details, and resulting portfolio balances.

## 17. Backtesting, Walk-Forward Evaluation, and Statistical Validity

### 17.1 Chronological evaluation

Do **not** randomly split overlapping time-series labels. Use a prespecified time-ordered split such as:

1. Historical training period.
2. Separate model/hyperparameter validation period.
3. Calibration period, with no leakage from future samples.
4. Held-out final test period, opened once.
5. Prospective paper/shadow period for operational verification.

For rolling walk-forward folds, train only on data preceding each validation window; purge/embargo overlapping label spans around boundaries and enforce feature availability limits. Record retraining frequency and training-window policy.

### 17.2 Leakage checklist

- Target uses future close while feature window uses past data only.
- Rolling transforms do not center their windows.
- Scaling/imputation/calibration parameters are fit only on training windows.
- Feature selection and hyperparameter search never use the final test.
- Market news uses **first machine-observable publication/receipt time**, not merely event date.
- Revisions/backfilled candles are not silently substituted into a historical decision without replay metadata.
- Entry price is observable *after* signal generation and applicable delay.
- Model pretraining chronology is documented, especially Jev on older history.
- Changing a question set or policy creates a new experiment ID.

### 17.3 Predictive metrics

For classification: Brier score, log loss, ROC-AUC or PR-AUC if event prevalence warrants it, classwise precision/recall, and balanced accuracy. For regression: MAE/RMSE against strong no-change baselines and distributional calibration if relevant.

For calibration: reliability curves, ECE with declared binning, coverage of prediction intervals, and calibration drift across market regimes.

### 17.4 Economic metrics

- **Net** PnL / equity curve, after fees and modeled execution friction.
- Maximum drawdown and drawdown duration.
- Volatility-adjusted performance (Sharpe, with frequency/annualization assumptions explicit).
- Turnover, trade count, average hold time, gross vs net return.
- Buy-and-hold / no-trade / matched-rule baselines.
- Sensitivity to fees, spread, delay, slippage, and capital allocation.
- Return-per-unit model/infrastructure cost where economically meaningful.

Do not report a high Sharpe without showing the number of independent opportunities, drawdowns, data period, and sensitivity to the fill model.

### 17.5 Statistical uncertainty and multiple trials

Because minute labels overlap and strategy returns are serially dependent, use block bootstrap or appropriate HAC/time-series uncertainty estimates rather than assuming IID rows. Track the number of attempted features, prompt versions, thresholds and models; multiple comparisons dramatically increase apparent false discoveries. Prefer a frozen experiment plan and an untouched final test period.

### 17.6 Prospective paper experiment

The strongest evidence is a timestamped prospective run in which all candidate predictions are **committed before the five-minute outcomes are observed**. The broker and portfolio can remain in shadow-only mode until predictive gates pass. Prospective evidence also exposes real endpoint outages and late event arrival missing from historical backtests.

## 18. Costs, Latency, and Resource Budgeting

### 18.1 Jev input pricing example

**Published rate at preparation:** `$0.042 per 1,000,000 input tokens`; output token charges listed as zero. This is **model input billing only**, not total cost of the experiment.

For an illustrative average of **1,000 billable input tokens per call** and **30 full days**:

| Cadence | Calls in 30 days | Input tokens | Estimated Jev cost |
|---|---:|---:|---:|
| 1 second | 2,592,000 | 2,592,000,000 | **$108.864** |
| 5 seconds | 518,400 | 518,400,000 | **$21.7728** |
| 1 minute | 43,200 | 43,200,000 | **$1.8144** |
| 5 minutes | 8,640 | 8,640,000 | **$0.36288** |

Formula:

`Jev_input_cost_USD = billable_input_tokens / 1_000_000 * 0.042`.

These are arithmetic estimates, not measured invoices. Requests may contain many questions sharing a state. Batching can reduce repeated state encoding, but large states, parallelism limits, question design, retries, provider changes, and non-Jev processing can alter real cost.

### 18.2 Why cheap input tokens do not imply free trading

Budget separately for:

- Historical/live data services or access restrictions.
- Retrieval, preprocessing, storage and network egress.
- Local CPU/GPU power and memory residency.
- Supplemental cloud LLM explanations/news processing.
- Jev retries, overage, failed requests, and stale snapshots.
- Model training/validation and repeated research experiments.
- Simulated trade spread, fees and slippage—the largest financial friction in many short-horizon policies.

### 18.3 Event-driven inference

Do not call Jev on every WebSocket update by default. At a closed 1-minute candle cadence, only call if the experiment branch requires fresh semantic assessment. Cache stable news or document classifications by event hash, while applying strict time-availability policies.

### 18.4 Latency budget

Define and measure end-to-end:

`bar availability -> feature computation -> model queue -> inference -> calibration/policy -> next simulated executable quote`.

Record at least:

- p50/p95/p99 provider latency and full pipeline latency.
- Missed-decision count due to delayed candles/model responses.
- Staleness at decision completion.
- Difference between benchmark close price and achievable post-decision quote.
- Local VRAM peak, queue length, throughput, and retry behavior.

For a five-minute target, a 500 ms model latency may or may not matter, depending on volatility and fill assumptions; measure rather than assume.

## 19. Testing Strategy and Acceptance Gates

### 19.1 Data tests

| Test | Expected invariant |
|---|---|
| WebSocket `x=false` | Never becomes final canonical candle |
| Duplicate closed candle | Exactly one logical canonical candle per key |
| Out-of-order delivery | Ordering and lineage restored deterministically |
| Gap of one or more minutes | Gap recorded, affected snapshots suppressed |
| Invalid OHLC geometry | Reject or quarantine |
| Negative price/volume | Reject |
| Rest-vs-WebSocket revision | Explicit reconciliation with source history |
| Missing taker volume / zero base volume | Clear null/undefined policy |
| UTC conversion / minute alignment | Deterministic timestamps |
| Replay same inputs twice | Same dataset checksum and features |
| Network/rate-limit outage | Bounded retry, no unbounded busy loop |

### 19.2 Feature and label tests

- Hand-computed small sequences verify returns, volatility, RSI, and z-scores.
- Gap in a rolling window invalidates affected features under a frozen policy.
- No feature reads `t+1` through `t+5`.
- Feature snapshots change only when new *eligible* data appears.
- Label computation is inaccessible from online inference imports.
- A dataset split crossing an overlapping-label boundary is purged correctly.

### 19.3 Inference tests

- Recorded-response parsing validates exact model/question versions.
- Probability vector is finite, nonnegative and normalized within tolerance where applicable.
- Distinguish Jev Choice distribution from Noul scalar and derived confidence.
- Provider unavailability produces an explicit abstention/fallback—not a fabricated score.
- Privacy/egress denial cannot be bypassed by failover.
- Versioned cache invalidates when input, criteria, or model changes.
- Prompt injection in retrieved text cannot alter application safety rules.
- No real provider request occurs in normal unit tests.

### 19.4 Paper-broker tests

- Virtual balances conserve accounting under fees/fills.
- Cannot sell more BTC than owned, cannot buy beyond USDT budget.
- Duplicate accepted intent cannot double-fill.
- No pre-decision or look-ahead fill prices.
- Higher slippage/fees never *improves* identical gross executed strategy PnL mechanically due to a bug.
- Stale/missing predictions lead to `HOLD`.
- Risk cap and drawdown kill switch block increasing exposure.
- **All trading/authenticated Binance endpoints forbidden by import, configuration and network allowlist tests.**

### 19.5 Benchmark tests

- No shuffled time-series split.
- Calibration fit excludes held-out test rows.
- Baselines receive matched data and feature engineering effort.
- J2 vs Z0 tests separate model value from access to news/context.
- Retrospective Jev contamination risk documented.
- Prospective prediction recorded before outcomes.
- Results stable under plausible fee/slippage assumptions.
- Re-run of frozen data + code + seed produces matching metrics within pinned tolerances.

### 19.6 Release gates

**Gate A — Data:** no unreported gaps, valid schema, deterministic replay.
**Gate B — Prediction:** baseline sound, leakage audit passed, frozen OOS metrics.
**Gate C — Jev:** measurable incremental value under fair controls; otherwise do not promote.
**Gate D — Paper:** fill/risk/accounting simulations pass; no authenticated order capability.
**Gate E — Prospective:** stable forward prediction, calibration and operational reliability.

The exact numerical thresholds are **not yet agreed**; define them using development data and requirements before final testing. Do not fabricate success criteria to fit observed results.

## 20. Roadmap and Release Gates

### Phase 0 — Repository audit and trusted data foundation

**Design goal:** Make historical/live BTC data research-grade without invoking Jev or performing a trade. B0 implemented the offline contract/replay foundation described in the companion implementation report; these remaining Phase 0 ingestion items are not yet implemented.

- **P0.1 Repository inventory:** source tree, existing adapters/contracts/tests, ADRs, execution boundary; identify reuse and isolation points. **Completed for B0.**
- **P0.2 Contracts:** versioned raw event, closed candle, dataset manifest/revision, feature, five-minute label, prediction envelopes, and experiment configuration. **Completed for B0; see report for exact rules.**
- **P0.3 Historical market data:** separately approved source policy, pagination, checkpoint/retry, raw captures, canonical Parquet, gap report. **Deferred to B1; B0 has no network source.**
- **P0.4 Live market data:** public WebSocket, closed-candle filter, reconnect, backfill, stable replay. **Deferred; no B0 network connection.**
- **P0.5 Feature processor:** small deterministic feature set, time-safe availability, warm-up flags. **B0 includes only close and one-minute log-return fixture features; expansion is deferred.**
- **P0.6 Data quality gate:** offline tests, replay determinism, manifest, dataset freeze. **B0 fixture/replay checks completed; production dataset freeze is deferred.**

**Remaining exit:** One auditable, point-in-time historical data pipeline; no trading model required. B0 alone does not satisfy this Phase 0 exit.

### Phase 1 — Statistical baselines

- Formalize target and executable-price simulation assumptions.
- Implement naïve, random-walk, logistic/statistical and LightGBM baselines.
- Establish walk-forward folds, purges, frozen training/calibration/test ranges.
- Run feature ablations and create reproducible model cards.

**Exit:** Credible B2 baseline and OOS metrics, or documented negative result.

### Phase 2 — Jev feasibility research

- Verify Jev version/access, policy and actual token usage.
- Agree on small fixed question sets and semantics.
- Generate historical exploratory Jev scores with contamination caveats.
- Evaluate J0/J1 against same-input B2.
- If justified, introduce timestamped `Z` news/context and matched Z0/J2/L0 controls.
- Fit downstream LightGBM and calibrate on appropriate periods.

**Exit:** Evidence for incremental improvement **or** falsification; no reliance on Jev fine-tuning.

### Phase 3 — Paper-broker simulation

- Virtual wallet, risk policy, event ledger and fill models.
- First run offline walk-forward replay.
- Compare all models under identical trade/risk/cost assumptions.
- Stress with fees, slippage, latency and outages.

**Exit:** Reproducible economic evaluation, no live execution dependencies.

### Phase 4 — Shadow then prospective paper mode

- Live inputs and predictions timestamped before outcomes.
- **Shadow mode:** predictions and PnL simulation without even a portfolio-changing virtual order policy if earlier gates are not met.
- **Paper mode:** explicit approval to activate only the **virtual** broker after gates pass.
- Monitor drift, provider outages, net PnL, calibration, risk and reporting.

**Exit:** Honest report about whether and when Jev adds value—not a requirement to demonstrate profitability.

### Phase 5 — Optional expansion, outside initial commitment

Explore order-book features, higher-quality external contexts, new models, or richer visualizations **only after** Phase 4 evidence. Real-money trading remains **out of scope** and would need a separate security, regulatory, risk, compliance and operational review, not an automatic roadmap continuation.

### Important milestone compatibility

The existing `STACK.md` M2.9 requirement for approval of a single synthetic model request is a separate project governance step. This technical design does not imply that approval has occurred. Any future Jev experiment with real API calls must similarly pass explicit cost/privacy/authorization gates.

## 21. Proposed Repository Layout and Integration Plan

**Illustrative target only; do not create until the repository audit is complete.**

```text
market_os/
  experiments/
    btc_paper/
      README.md
      contracts/               # market/candle/prediction schema
      data/                    # Binance public adapter + normalizer
      features/                # deterministic feature calculations
      models/                  # numeric baselines + optional Jev adapter
      evaluation/              # splits, calibration, walk-forward tests
      policy/                  # paper-only decision logic
      simulation/              # virtual wallet, ledger, fill models
      reports/                 # offline research outputs
  tests/
    ...                       # leverage existing repo test conventions

docs/
  TECH_DOCS.md                # this document, if project conventions agree
```

Recommended integration principles:

1. Follow existing `market_os` packaging and test names, not this template if they differ.
2. Keep adapters narrow; neither a market-data reader nor model adapter should import a live order client.
3. Prefer an experiment configuration whose mode is **structurally** `paper` rather than a dangerous `live=false` Boolean near a live code path.
4. Reuse logging, artifact storage, risk primitives and CLI interfaces where safe and coherent.
5. Avoid changing the existing US equities Phase 0 workflow to satisfy crypto experiment needs.
6. Do not merge the research-reports semantic model role with the experimental price-direction predictor role.

## 22. Risks, Failure Modes, and Mitigations

| Risk | Consequence | Mitigation |
|---|---|---|
| Data gaps / revisions | Incorrect features and fake alpha | Raw retention, QA, reconciliation, versioned datasets |
| Look-ahead leakage | Inflated backtest | Point-in-time eligibility, offline label isolation, timeline tests |
| Candle-close execution assumption | Impossible fills | Post-decision next quote/open and latency-aware model |
| Five-minute overlapping labels | Invalid confidence intervals | Walk-forward purge/embargo, dependence-aware statistics |
| Selection overfitting | Spurious strategy discovery | Freeze plans, track trials, untouched test |
| Jev answer ≠ return probability | Miscalibrated trade signal | Typed semantics, downstream calibration, abstention |
| Jev no customer fine-tuning | Broken architectural assumption | Train a separate downstream/local model |
| Pretraining temporal contamination | False retrospective Jev result | Document uncertainty; prospective shadow test |
| News data published/received late | Temporal leakage | First-observable timestamp, source archival metadata |
| Correlated news sources | Overconfidence | Deduplicate/correlate evidence; no naïve independent Bayes |
| Model/provider drift | Inconsistent predictions | Pin versions, frozen criteria, requalify on change |
| Cloud egress/privacy | Disclosure of sensitive data | Minimal structured state, egress allowlist, redaction |
| Cloud outage / rate limit | Missing decisions | Bounded retry + abstention; numerical baseline survives |
| Local VRAM/CPU contention | Stale predictions | Measured load, bounded queue, resource budget |
| Underestimated spread/slippage | Fake profitability | Stress scenarios and bid/ask-aware simulation |
| High turnover | Fees eat predicted edge | Cost-aware policy, no-trade band |
| Provider API cost surprise | Budget overrun | Token metering, ceilings, event-driven calls |
| Accidental real exchange interaction | Unacceptable scope violation | No keys, no order client, endpoint allowlist, CI checks |
| Prompt injection from retrieved documents | Misleading explanations/behavior | Treat retrieved text as untrusted data; independent gates |

## 23. Open Architecture Decisions

These are genuine unresolved decisions; do not invent answers when implementing:

1. **Dataset span:** How much continuous, high-quality BTCUSDT historical data is available/needed, and how much is reserved for the final test?
2. **Decision eligibility:** How many milliseconds/seconds after a final 1m candle can a prediction be considered available? Derive it from measured live runtime, not convenience.
3. **Primary target:** continuous log return, binary sign, or 3-class return band? Consider maintaining separate target versions.
4. **Executable pricing:** initial conservative fill model vs adding bid/ask collection immediately.
5. **Calibration method:** Platt/sigmoid, isotonic, or alternative for each task; choose using development data size.
6. **Market context (`Z_t`):** start with none, timestamped news, or another legally sourced event stream?
7. **Jev question set:** exact criteria to distinguish semantic regime classification from actual future-return prediction.
8. **Local semantic model:** which candidate, task, hardware budget, and license? Benchmark before commitment.
9. **Thresholds:** minimum improvement and uncertainty bounds for promoting Jev to a research signal.
10. **Virtual wallet risk settings:** initial capital, max allocation, costs, drawdown policy, maximum churn, and stop behavior.
11. **Data storage location:** local only vs remote object store; define backup/retention policy.
12. **Budget:** cloud spend ceiling, inference cadence, token caps, and permitted egress payload size.
13. **Model requests:** how approvals and recorded-response tests interact with the existing M2.9 gate.
14. **Repository integration:** where the actual existing contracts/live-disabled protection should be reused after source audit.

## 24. Definition of Done and Handoff Checklist

The full Phase 0 design should be considered ready for promotion only when the following are verified. B0 has completed only the local audit/contracts/fixture-replay subset; see §20 and `docs/B0-BTC-PAPER-REPLAY-REPORT.md` for the split between completed B0 work and deferred ingestion requirements.

### Repository and safety

- [ ] Current repository tree and ADRs reviewed, including actual test and persistence interfaces.
- [ ] The existing deterministic US equities workflow is preserved.
- [ ] BTC experiment stays strictly **paper-only**.
- [ ] No authenticated exchange order/withdrawal/account endpoints can be reached.
- [ ] Any provider request has independent approval, cost policy and redaction/egress policy.

### Data engineering

- [ ] Public Binance endpoints and deployment-region access verified.
- [ ] Historical and live 1m candle contracts agree.
- [ ] Closed-candle-only behavior, gap detection, timestamp availability and replay specified.
- [ ] Raw, canonical, feature, label and prediction stores have lineage.
- [ ] Dataset reproducibility and offline tests designed.

### Modeling

- [ ] Target horizon explicitly **300 seconds**.
- [ ] Predictive labels separated from executable-trading outcomes.
- [ ] Simple/statistical and LightGBM controls defined.
- [ ] Jev outputs assigned precise semantics and explicit version.
- [ ] No Jev weight fine-tuning dependency.
- [ ] E2/J1/J2 comparisons include fair data-source controls and pretraining caveats.
- [ ] Calibration and leakage methodology are predefined.

### Trading research

- [ ] Decision policy is deterministic and independently testable.
- [ ] Virtual execution includes documented fees, spread, slippage and latency.
- [ ] Spot inventory never goes negative.
- [ ] No-trade, stale-data and risk-failure behaviors specified.
- [ ] Net PnL and uncertainty are reported alongside predictive metrics.

### Scientific integrity

- [ ] All numbers marked as **illustrative** until measured.
- [ ] Baseline and Jev runs share frozen chronological evaluation periods.
- [ ] Retrospective-vs-prospective distinction is explicit.
- [ ] A negative or inconclusive result is acceptable.
- [ ] All decisions and model versions are reproducible and auditable.

### Minimal handoff brief for an implementation agent

> Work on `Autonomous-Market-OS` Phase 0 for a **BTCUSDT Spot, five-minute-horizon, paper-only** research experiment. First audit the existing `market_os/`, `docs/`, `scripts/`, tests and ADRs; do not invent module names. Reuse deterministic platform boundaries. Plan public Binance historical/live **closed 1m candle** ingestion with strict event/availability timestamps, raw/Parquet data lineage, QA, point-in-time features, and replay tests. No Jev/model calls, authenticated Binance access, real exchange orders, or actual fund movement in Phase 0. Train and compare statistical/LightGBM baselines before evaluating pinned Jev typed outputs. Treat Jev answers as uncalibrated semantic/model assessments, not native future-return probabilities. Use chronological, leakage-safe benchmarks and a deterministic virtual broker. See `TECH_DOCS.md` and `STACK.md` for acceptance criteria and governance.

## 25. Primary References and Verification Notes

The links below are public references checked for this document on **2026-10-17**. Provider behavior and pricing can change, so verify again before integration. Assertions about code *inside* `market_os/` remain subject to the repository audit described in §3.4.

### Project

1. [Autonomous-Market-OS public repository and README](https://github.com/Acceleratorer/Autonomous-Market-OS) — scope, public root, existing deterministic workflow, disabled live execution.
2. [Repository pyproject.toml](https://github.com/Acceleratorer/Autonomous-Market-OS/blob/main/pyproject.toml) — Python version, CLI entry point and pytest defaults.
3. Local `STACK.md` uploaded for this discussion — model boundary, grounding, reported M2.8/M2.9 status, research-report architecture.

### TypeSafe / Jev

4. [TypeSafe: Models](https://docs.typesafe.ai/models) — Jev 1.13/1.14, published cost, context, model pins and **no customer fine-tuning/LoRA**.
5. [TypeSafe: Introduction](https://docs.typesafe.ai/introduction) — system-one model and typed questions.
6. [TypeSafe: Primitives](https://docs.typesafe.ai/primitives) — `Choice`, `Score`, `Noul`, and related semantics.
7. [TypeSafe: Confidence](https://docs.typesafe.ai/confidence) — meaning and mathematical definition of confidence versus response probabilities.
8. [TypeSafe: Autoresearch feature discovery](https://docs.typesafe.ai/cookbooks/autoresearch_feature_discovery) — illustrative downstream classical-model learning from Jev-generated features; **not** evidence of BTC alpha.
9. [TypeSafe: API reference](https://docs.typesafe.ai/api) — verify current SDK/request and response schema before code is written.

### Binance public market data

10. [Binance Spot API: Market Data Only URLs](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md) — public REST/WebSocket base URLs without authentication.
11. [Binance Spot REST API](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md) — `/api/v3/klines`, parameters, limits and response details.
12. [Binance Spot WebSocket Streams](https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md) — kline close field, event timing, connection and stream details.
13. [Binance official developer portal](https://developers.binance.com/en/docs/products/spot/rest-api) — continuously updated operational REST guidance.

---

## Final Architectural Recommendation

Build a **deterministic, time-correct BTC market-data and evaluation system first**. Treat LightGBM as the numerical benchmark, Jev as an optional experimental representation/semantic feature source, and generated language as an optional grounded explanation capability. Promote Jev to a paper-trading signal **only if** it delivers reproducible out-of-sample incremental value under fair baselines and the improvement survives calibrated decision-making, post-decision execution timing, transaction friction, and prospective verification.

**Good research does not have to find a profitable bot. It has to produce results that can be reproduced, challenged, and trusted.**
