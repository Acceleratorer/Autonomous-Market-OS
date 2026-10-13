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
