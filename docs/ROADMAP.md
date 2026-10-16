# Autonomous Market OS: Roadmap

## Milestone sequence

| Milestone | Target result | Main projects | Gate |
|---|---|---|---|
| M0 | Product and repository decision record | All | Scope and ownership agreed |
| M1 | Versioned platform contracts | OpenHarness/nanobot/DeepCode comparison | Contract tests pass |
| M2 | Cited research API and CLI | Vibe-Trading, LightRAG, RAG-Anything | Reproducible research run |
| M3 | Paper portfolio and order plans | AI-Trader, Vibe-Trading | No live side effects |
| M4 | Web and desktop operator console | OpenHarness, existing frontends | Shared API state |
| M5 | Evaluation and reports | ClawWork, DeepTutor, Paper2Slides | Benchmark baseline |
| M6 | Live trading pilot | Broker adapters | Safety review passed |
| M7 | Media, marketplace, and tool ecosystem | ViMax, CLI-Anything | Isolation and governance passed |

## First 90 days

### Weeks 1–2: decide

- Select the orchestration kernel.
- Define the first user and supported markets.
- Record contracts and ownership.
- Establish one development environment and one configuration model.

### Weeks 3–6: prove research

- Build the gateway service.
- Implement research task creation and run events.
- Connect market data, retrieval, citations, and backtesting.
- Ship a CLI that can start, inspect, and export a run.

### Weeks 7–10: prove paper trading

- Add portfolio and order-plan schemas.
- Add simulated broker execution and risk policy checks.
- Add approval and cancellation flows.
- Persist artifacts and audit events.

### Weeks 11–13: prove product surface

- Add web dashboard for runs, evidence, portfolio, and approvals.
- Add desktop/mobile shell against the same API.
- Add baseline cost, quality, latency, and recovery benchmarks.

## Priority rule

Every milestone must improve one complete user workflow. Defer broad integrations that do not improve the current vertical slice or its safety evidence.

## Current status

M1 contract validation and JSON fixtures are implemented. M1.5's fixture parity
is complete. M1.6 now runs the actual OpenHarness runtime in an isolated
environment with a scripted no-network model client; it reports `runtime_verified=true`
and zero parity mismatches, but OpenHarness remains provisional because
runtime-native failure, cancellation, and multi-agent scenarios are unsupported.
M1.7 direct recovery probes are complete. M1.8 adds root-owned terminal
recovery, cancellation checkpoints, abandoned-run cleanup, artifact
idempotency, a versioned multi-agent aggregation contract, and a deployment
review. OpenHarness remains provisional because runtime-native restart/resume,
synchronous persistence cancellation, partial teammate failure propagation,
duplicate teammate handling, and deployed-service evidence remain open. The
exact next milestone is **M1.9: validate the deployment shape and close or
explicitly reject the remaining runtime blockers**, still with no real providers
or live trading. M1.9 now adds launched-service deployment evidence, but ADR-0007
keeps OpenHarness provisional because runtime-native checkpoint/resume,
teammate failure propagation, duplicate handling, and deployment controls for
resource limits, timeouts, and structured logs remain open. The exact next
milestone is **M1.10: add or reject the bounded deployment wrapper and rerun
the OpenHarness promotion gate**.

M1.10 accepts a local paper-only wrapper and records 48 named scenarios, but
ADR-0008 keeps OpenHarness provisional because native persistence cancellation,
checkpoint/resume, teammate propagation, duplicate handling, and external
service controls remain open. The exact next milestone is **M1.11: supply or
reject the external supervisor controls and obtain final native blocker
evidence**.

M1.11 classified every remaining blocker and closed the safe Market OS
adapter-level behaviors. M1.12 makes the final decision: **Market OS owns
orchestration; OpenHarness is optional**. Market OS is the sole owner of
production orchestration, safety policies, events, persistence, cancellation,
restart recovery, multi-agent aggregation, and the deployment boundary.
OpenHarness remains available behind the optional adapter for local,
no-network, paper-only agent capabilities. ADR-0010 supersedes the provisional
ownership and promotion decisions while preserving their historical evidence.

M2 planning is now unblocked. The exact next milestone is **M2.1: implement
one deterministic Vibe-Trading-shaped market-data/backtest adapter against the
root provider contracts**, with no real network access, credentials, brokers,
or live execution.

M2.1 is implemented. The explicit `vibe-trading` adapter normalizes the
synthetic three-ETF fixture, executes the actual Vibe-Trading local-loader
backtest in an isolated environment, persists root-owned evidence/citations,
lineage, provenance, paper order plans, and risk decisions, and preserves the
fixture default. The exact next milestone is **M2.2: add a cited document or
retrieval adapter only after its root document/citation contract is approved**.

M2.2 is implemented. The explicit `lightrag` adapter validates a synthetic
four-document corpus, executes LightRAG's actual offline `ainsert` and
`aquery_data(mode="naive")` seam in isolation, persists document/retrieval
lineage, and composes with the Vibe-Trading backtest and paper-only workflow.
The exact next milestone is **M2.3: harden cited research synthesis and
document/passage inspection without adding external providers**.

M2.3 is implemented. Deterministic cited synthesis now emits versioned claims,
supports, citations, coverage, unsupported-claim records, stable fingerprints,
and read-only CLI/API inspection with artifact/hash/lineage validation. The
exact next milestone is **M2.4: evaluate richer research summaries only behind
an explicit model contract and citation-preserving output gate**.

M2.4 is implemented. The deterministic M2.3 synthesis remains the trusted
baseline; an explicitly selected local deterministic test provider produces a
versioned, citation-preserving model-summary artifact. Supported statements are
exact persisted quotes, inference and unsupported statements are explicit, bad
output is rejected, provider failure preserves the deterministic synthesis, and
model-summary/inference inspection is available through CLI and API. The actual
offline LightRAG and Vibe-Trading seams remain composed and paper-only. The
exact next milestone is **M2.5: define the next research-quality gate or
benchmark before considering any real model/provider adapter**.

M2.5 is implemented. The offline research-quality benchmark evaluates 18
synthetic cases through deterministic exact-quote and deterministic test-model
methods, measures independent citation/grounding/replay/fallback/security/
lineage/latency/usage metrics, persists read-only benchmark artifacts, and
exposes CLI/API inspection. The promotion decision is **Not ready — specific
failures remain**: no real model was exercised, cost is unavailable, and the
test-model quote/support/coverage metrics remain below thresholds. The exact
next milestone was M2.6 quality review.

M2.6 is implemented offline. It reproduces all 36 evaluations, classifies the
eight reported v1 failures as expected invalid/hostile candidate rejection or
integrity rejection, and fixes the benchmark's combined pass/fail semantics,
empty-denominator handling, invalid-citation accounting, unavailable usage
reporting, latency threshold brittleness, and v1 artifact inspection path. The
v2 report has 36/36 benchmark-success checks and 36/36 gate-correctness checks;
seven deterministic test-model candidate-quality failures remain intentionally
visible. No hosted model is called. The exact next milestone is **M2.7:
implement recorded-response tests and one bounded optional model adapter after
explicit provider, data-retention, credential, and spend approval**.

M2.7 is implemented as an offline foundation. Recorded Responses-shaped
fixtures exercise parsing, grounding, fallback, replay, usage-unknown behavior,
and hostile-output rejection. A stdlib-only optional OpenAI Responses adapter
supports `gpt-6.1-sol` behind explicit approval, bounded budgets, `store: false`,
paper-only mode, and bounded transient retries; it is not selected by default
and no live call was made. Fusion-repository CI and security workflows validate
tests, offline integration markers, compilation, evidence JSON, diff hygiene,
secret-like fixture content, and model-boundary checks without credentials.
The exact next milestone is **M2.8: run an explicitly approved single live
synthetic smoke only if provider, credential, retention, destination, request,
token, and spend approvals are separately supplied**.

M2.8 offline preparation is complete. The local harness validates one synthetic
payload, exact one-request/zero-retry/$0.02/20-second bounds, redaction, and the
existing citation gate while ordinary CI remains credential-free. The live
smoke is **Pending approval — offline preparation complete, no live request
made**. The exact next action is a separate human approval followed by one
manual execution, or a recorded decision to keep the smoke pending.
