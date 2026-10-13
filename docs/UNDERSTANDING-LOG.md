# Understanding log

## 2026-10-13 — Initial workspace pass

Inspected the top-level workspace, all 13 child repositories, their READMEs, package manifests where present, top-level layouts, Git status, and latest commit metadata. Confirmed six capability families: runtimes/harnesses, retrieval, education, finance, work evaluation, and creative generation. Existing unrelated modifications in `ClawWork` sandbox artifacts and an untracked `CLI-Anything` object directory were preserved.

## 2026-10-13 — Phase 0 and first vertical slice

- Selected a small research team / individual researcher as the first user boundary; live execution is excluded.
- Bounded the first slice to US listed equities and ETFs, USD, daily bars, deterministic local fixtures.
- Proposed OpenHarness as orchestration owner behind a narrow adapter protocol; nanobot and DeepCode remain adapters.
- Defined `market-os.v1` contracts for tasks, runs, events, artifacts, evidence, research, backtests, order plans, and risk decisions.
- Kept child repositories independent. The root package owns transport, contracts, persistence, and workflow composition; future adapters will call Vibe-Trading, LightRAG/RAG-Anything, and AI-Trader through typed interfaces.
- Implemented a dependency-light vertical proof with restart-safe JSONL persistence, immutable artifacts, deterministic backtest, paper-only order plan, and risk checks.
- Unknowns recorded in `docs/decisions/ADR-0001-phase-0.md`: runtime benchmark, production storage, provider licensing/freshness, paper limits, and live gate checklist.
- Review hardening added a durable run index, artifact index with lineage, evidence artifact, terminal failure/rejection/cancellation records, idempotency replay, CLI inspection, API run inspection, and a runtime paper-only guard.
- Deferred by design for the next milestone: asynchronous run control and mid-provider cancellation, production database/object storage, typed real-provider market bars, richer claim-level research synthesis, and the OpenHarness adapter benchmark.

## 2026-10-13 — M1 contract foundation

- Added executable `market-os.v1` validation for IDs, dates, timestamps, symbols, versions, terminal run states, paper-only execution, order values, artifact digests, and risk/approval invariants.
- Added the Phase 1 contract envelopes `AgentProfile`, `KnowledgeDocument`, `MarketObject`, `Portfolio`, `Approval`, `CancellationRequest`, and `ErrorResponse`, while preserving the existing workflow contracts.
- Added JSON boundary helpers and focused contract tests. The API now returns structured contract errors with stable codes and fields.
- Kept authentication, tenant isolation, provider-specific bar schemas, asynchronous cancellation, and production storage deferred until the next architecture decisions.

## 2026-10-13 — Fusion repository created

- Created the independent personal-project repository at `https://github.com/Acceleratorer/Autonomous-Market-OS`.
- Committed the fusion-owned foundation as `58c9e40` and pushed M1 contract stabilization as `b63f3fe` on `main`.
- The child repositories remain separate directories and were not added to the fusion Git history. Existing user changes in `ClawWork` and `CLI-Anything` remain preserved.

## 2026-10-13 — M1 contract and runtime decision evidence

- Tightened `market-os.v1` numeric validation so paper order quantities and notionals must be positive, while preserving the existing live-execution guard.
- Added representative valid and invalid JSON fixtures and deterministic serialization/deserialization coverage for the workflow-facing contracts.
- Added `docs/M1-CONTRACTS.md` with the contract inventory, validation rules, error codes, compatibility behavior, and deferred boundaries.
- Inspected OpenHarness, nanobot, and DeepCode runtime, session, event, persistence, tool, CLI, and service paths. Recorded a source-based comparison in `docs/runtime-benchmark.md`; no child runtime was executed and no performance claim is made.
- Recorded provisional OpenHarness ownership and adapter responsibilities in `docs/decisions/ADR-0002-orchestration-runtime.md`. Human confirmation is still required before a production adapter or real provider is connected.

## 2026-10-13 — M1.5 OpenHarness parity harness

- Added the narrow `OrchestrationAdapter` protocol and an OpenHarness-shaped fixture adapter under `market_os/orchestration/`.
- Kept OpenHarness optional: no child runtime import, provider credential, model call, or broker call is required.
- Added parity checks for task/results, event ordering and UTC timestamps, failure and cancellation, restart inspection, idempotency, content-addressed artifacts, lineage, citations, risk, paper-only enforcement, error normalization, contract JSON, and shared CLI/API result shape.
- Fixture parity has no mismatches. Event names require translation, and actual OpenHarness runtime behavior remains explicitly unverified (`runtime_verified=false`).
- Added `docs/M1.5-OPENHARNESS-PARITY.md` and `docs/decisions/ADR-0003-openharness-adapter.md`. Promotion requires real-runtime parity in an isolated environment before any provider or execution integration.

## 2026-10-13 — M1.6 runtime-verified OpenHarness probe

- Built a temporary isolated OpenHarness environment outside the repository from the child package metadata; no credentials, real providers, or broker calls were used.
- Added `IsolatedOpenHarnessRuntime` and a child-process probe that drives OpenHarness's actual session build, start, prompt handling, tool execution, skill loading, snapshot persistence, reload, and close paths with a scripted model client.
- The runtime parity report completed with `runtime_verified=true`, zero mismatches, and exact matches for research, backtest, paper order plan, risk, artifacts, lineage, citations, event ordering, UTC timestamps, contract serialization, and shared result shape.
- Kept OpenHarness provisional. Runtime-native failure propagation, cancellation, and multi-agent coordination are explicitly unsupported until direct probes exist. Live execution and real providers remain disabled.
- Added `docs/M1.6-OPENHARNESS-RUNTIME.md`, `docs/decisions/ADR-0004-openharness-runtime.md`, and focused runtime adapter tests.

## 2026-10-13 — M1.7 OpenHarness recovery probes

- Added `market_os/orchestration/recovery.py` and the isolated child-runtime
  probe `market_os/orchestration/openharness_recovery_probe.py`.
- Direct runtime evidence verifies provider/tool/contract/session-persistence failure
  observation, cancellation before and during provider/tool work, replay and
  duplicate handling, artifact lineage, event trace persistence, terminal
  status, paper-only enforcement, and basic two-agent shared identity/run
  coordination.
- Direct blockers are recorded for artifact-persistence cancellation, restart
  during running work, resume after cancellation, partial agent failure,
  duplicate teammate results, final aggregation, and deployment review.
- Added machine-readable evidence at
  `docs/evidence/m1.7-openharness-recovery.json`, focused recovery/coordination
  tests, `docs/M1.7-OPENHARNESS-RECOVERY.md`, and ADR-0005.
- OpenHarness remains provisional. M2 is blocked; the exact next milestone is
  M1.8 recovery blocker closure and deployment review. No real providers,
  brokers, or live execution were added.
