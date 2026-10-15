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

## 2026-10-14 — M1.8 recovery and deployment review

- Added root-owned recovery metadata and terminalization for event, run index,
  artifact, artifact-index, finalization, idempotency, and provider boundary
  failures. Failed writes no longer leave a run falsely `running` when storage
  recovers; partial artifact files remain inspectable.
- Added cancellation checkpoints around artifact and finalization writes and a
  restart cleanup method that marks abandoned work failed with an explicit
  `resume_unsupported` reason.
- Added the versioned `market-os.multi-agent.v1` result and aggregation
  contract with deterministic ordering, fingerprints, duplicate suppression,
  conflict records, partial failure status, artifact lineage, and individual
  errors.
- Regenerated `docs/evidence/m1.8-openharness-recovery.json` against the
  isolated OpenHarness 0.1.9 runtime. Direct runtime evidence passes the safe
  failure/cancellation/coordination cases; runtime-native resume, synchronous
  persistence cancellation, partial teammate failure propagation, and native
  duplicate handling remain unsupported.
- Completed `docs/DEPLOYMENT-REVIEW.md`. It documents Python/runtime versions,
  isolation, secrets, filesystem/storage, recovery, limits, network policy,
  retention, tenant isolation, container shape, and rollback without adding
  credentials or live integrations.
- OpenHarness remains provisional under ADR-0006. M2 remains blocked from real
  providers and live trading.

## 2026-10-14 — M1.9 deployment validation

- Added `/healthz` and `/readyz` to the dependency-free service and made startup
  run `recover_inflight_runs()` before accepting requests.
- Added `market_os.deployment_probe`, which launches the real local service,
  submits a paper task, inspects events/artifacts, verifies startup recovery,
  clean and forced shutdown, clean restart, filesystem isolation, and the
  no-secret boundary.
- Fixed isolated OpenHarness source-path discovery for the actual sibling
  `company-projects/OpenHarness` checkout. The Python 3.12.0 / OpenHarness 0.1.9
  probe now runs 26 scenarios.
- Deployment lifecycle evidence passes, but process resource limits, request
  and shutdown timeouts, and structured logging are unsupported. Runtime-native
  persistence cancellation, checkpoint/resume, partial teammate failure, and
  duplicate teammate handling remain unsupported. ADR-0007 keeps OpenHarness
  provisional and blocks M2.

## 2026-10-14 — M1.10 bounded wrapper and final blocker evidence

- Added `market_os/deployment/wrapper.py`, a dependency-free process wrapper
  with explicit absolute paths, loopback and paper-only enforcement, startup /
  readiness-request / shutdown timeouts, graceful and forced termination, exit
  normalization, and structured JSONL lifecycle logs.
- Host CPU/memory quotas are explicitly rejected without an external supervisor;
  the wrapper fails closed instead of claiming unsupported process isolation.
- Added wrapper tests and a launched wrapper probe. The wrapper lifecycle passes;
  service-level quotas, provider deadlines, service audit logs, and production
  service-account permissions remain external deployment blockers.
- Expanded the isolated OpenHarness probe to 48 named cancellation, restart,
  teammate, retry, duplicate, and artifact cases. Native checkpoint/resume,
  teammate failure/cancellation propagation, and duplicate handling remain
  unsupported; root adapter recovery and aggregation cases pass separately.
- ADR-0008 keeps OpenHarness provisional and sets M1.11 as the next gate.

## 2026-10-14 — M1.11 blocker classification and promotion readiness

- Added `docs/M1.11-BLOCKER-REVIEW.md`, ADR-0009, and machine-readable
  `docs/evidence/m1.11-openharness-blockers.json` with a complete blocker
  matrix, ownership, evidence class, and M2 readiness decision.
- Closed structured service request logging and bounded HTTP request-body reads
  at the local service boundary. Provider/workflow execution deadlines remain
  separate because the workflow is synchronous.
- Reconfirmed adapter mitigations for terminal persistence recovery,
  cancellation checkpoints, restart cleanup, partial aggregation, and
  duplicate/conflict fingerprints. Native OpenHarness persistence
  cancellation, checkpoint/resume, teammate propagation, duplicate handling,
  process quotas, and service identity permissions remain promotion blockers.
- ADR-0009 keeps OpenHarness provisional and defers M2 implementation while
  permitting planning for the first licensed research adapters.

## 2026-10-14 — M1.12 final orchestration owner and M2 adapter plan

- Evaluated the three required choices: OpenHarness owner, Market OS owner with
  optional OpenHarness, and OpenHarness rejection. Accepted **Market OS owns
  orchestration; OpenHarness is optional** because the root workflow already
  owns and tests the safety-critical state transitions while the native runtime
  still lacks repeatable recovery and deployment guarantees.
- Added ADR-0010 and the final decision record. Market OS now has one explicit
  owner for production orchestration, safety, events, persistence,
  cancellation, restart recovery, multi-agent aggregation, and deployment.
- Added dependency-free provider seam contracts for health, capabilities,
  deadlines, errors, rate limits, freshness, licensing, provenance, cache
  policy, deterministic fixtures, normalized market bars, and documents.
- Read the Vibe-Trading, LightRAG, and RAG-Anything entry points without
  modifying those repositories. Recommended one deterministic Vibe-Trading
  market-data/backtest adapter as M2.1; defer LightRAG and RAG-Anything until
  document and multimodal contracts are proven.
- M2.1 does not require real network access. No provider credentials, brokers,
  live execution, or child-repository changes were added.

## 2026-10-14 — M2.1 fixture-backed Vibe-Trading adapter

- Verified the read-only Vibe-Trading source at commit
  `c25fea2bc261a2d0ed971c989d194de9f04ec963`; the executed seam is
  `src.tools.backtest_tool.run_backtest` through the `source=local` loader.
- Added a synthetic, content-addressed daily OHLCV fixture for SPY, QQQ, and
  IWM with normalized `MarketBar` metadata, provenance, validation, and
  internal-only licensing classification.
- Added explicit CLI/API provider selection and an isolated child-process
  adapter. The default fixture path is unchanged; an unavailable optional
  adapter fails closed.
- Actual offline Vibe-Trading execution passed: `$10,000` became `$10,260.10`
  (`2.601%`) with reproducible fingerprint
  `3aa2b58c3a07c1e5fbcf95285b7c39eb110efc1cdb04eebfce80576d8bf817be`.
- Full project verification passed: 69 tests passed and one optional actual-
  runtime test was skipped when prerequisites were not configured. The
  reference repository remained unchanged.

## 2026-10-15 — M2.2 cited LightRAG retrieval adapter

- Evaluated LightRAG, RAG-Anything, and MiniRAG read-only. Selected LightRAG at
  `4d0afc1bc36e6a34d4a5895b68efe9413748627a` because its `ainsert` plus
  structured `aquery_data(mode="naive")` path is the smallest useful offline
  document/retrieval seam.
- Added four synthetic, content-hashed documents with provenance, licensing,
  stable IDs, timestamps, symbol metadata, and validation.
- Actual LightRAG code executed offline in an isolated environment and returned
  cited chunks with `reference_id` and source file paths. RAG-Anything and
  MiniRAG were not integrated.
- Added explicit `lightrag` document selection with `vibe-trading` backtest
  selection, root-owned document/retrieval artifacts, citations, lineage,
  restart/idempotency behavior, and paper-only enforcement.
- Verification passed: 13 focused M2.2 tests, 9 M2.1 tests, and 82 full-suite
  tests with one optional test skipped. All three reference repositories stayed
  unchanged.

## 2026-10-15 — M2.3 cited research synthesis and inspection

- Confirmed the M2.2 research layer was summary-only: citations existed, but
  claims, exact supports, coverage, and read-only resource inspection did not.
- Added `market-os.research.v1` contracts for document/passage references,
  citations, exact-quote claim support, supported/unsupported claims, evidence
  coverage, and deterministic synthesis fingerprints.
- Added root-owned `cited-research` artifacts and read-only CLI/API inspection
  for documents, passages, claims, passage-to-claim links, citations, and
  artifact lineage. Inspection validates artifact/content hashes and lineage
  without invoking providers.
- Verified actual LightRAG and Vibe-Trading offline workflow behavior,
  deterministic replay, paper-only enforcement, and corruption failures.
- Final verification passed: 93 tests passed and one optional test skipped.

## 2026-10-15 — M2.4 model-gated cited summaries

- Preserved M2.3 deterministic exact-quote synthesis as the default and trusted
  baseline; added the versioned `market-os.model-summary.v1` contract behind an
  explicit `deterministic-test` provider selection.
- Added provider identity, prompt/input/output/summary fingerprints, usage
  metadata, classified supported/inference/unsupported/rejected statements,
  validation errors, gate decisions, deterministic fallback identity, and
  cited-research artifact lineage.
- The output gate resolves citation/support/document/passages against persisted
  M2.3 evidence, checks content/provenance hashes and exact quotes, rejects
  unsupported citations and cross-claim links, and renders only visibly
  classified statement text. Model failures preserve deterministic output;
  rejected model text is not published.
- Added read-only CLI/API inspection for model summaries and inferences with
  artifact hash, fingerprint, and lineage validation. The workflow remains
  paper-only and model output cannot change risk or order-plan state.
- Actual offline LightRAG and Vibe-Trading seams were re-run with the local
  deterministic model double. The composed workflow completed with three
  supported claims, 100% M2.3 and model evidence coverage, final cash 10348.25,
  stable replay, and persisted `model-summary` lineage. No hosted model,
  credentials, network path, broker, or child-repository modification was
  added.

## 2026-10-15 — M2.5 research-quality benchmark

- Added the local `market-os.quality-benchmark.v1` benchmark over an 18-case
  synthetic corpus covering supported, unsupported, inference, conflict,
  duplicate, citation, hash, lineage, fallback, malformed, excessive,
  prompt-injection-like, and secret-like cases.
- Compared M2.3 deterministic exact-quote synthesis with the explicitly labeled
  M2.4 deterministic test-model double. Reports include independently
  inspectable citation, quote, support, unsupported/inference, evidence,
  isolation, hash, replay, fallback, malformed-output, security, lineage,
  latency, usage, and cost dimensions.
- Added read-only CLI/API benchmark run and inspection, content-addressed
  benchmark artifacts, stable fixture/case/report fingerprints, and ADR-0011.
- Baseline evidence: 36 evaluations, 28 pass and 8 intentional adversarial or
  quality failures. Promotion is **Not ready — specific failures remain**;
  there is no real model/provider, no cost signal, and human approval remains
  required before M2.6.
