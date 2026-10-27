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

## 2026-10-15 — M2.6 research-quality failure review and bounded adapter plan

- Reproduced the M2.5 corpus: 18 cases × 2 methods = 36 evaluations. The eight
  reported failures were correctly rejected invalid/hostile deterministic
  test-model outputs or the corrupt-hash integrity case; there were no gate
  false accepts or false rejects.
- Versioned the benchmark report as `market-os.quality-benchmark.v2` and
  separated benchmark success, gate correctness, and candidate quality. The
  v2 report records 36/36 benchmark-success checks and 36/36 gate-correctness
  checks while retaining seven candidate-quality failures as explicit negative
  cases.
- Corrected citation precision denominators to include invalid citation IDs,
  represented empty denominators and unavailable provider usage/cost/latency as
  unknown or not applicable, and removed the machine-specific latency
  promotion threshold from the stable decision path. Latency remains observed
  and excluded from fingerprints.
- Added read-only CLI/API benchmark inspection for evaluation,
  candidate-quality failures, and benchmark failures. Added a compatibility
  fingerprint path for persisted v1 benchmark artifacts.
- Wrote the quality review and a bounded optional OpenAI Responses API plan for
  `gpt-6.1-sol`; no model calls, credentials, network access, or provider
  dependencies were added. The next milestone is M2.7 recorded-response tests
  and optional adapter implementation only after explicit approval.

## 2026-10-16 — M2.7 recorded model adapter and CI foundation

- Added synthetic, clearly labeled Responses-shaped fixtures for valid
  citation-preserving output, explicit inference/unsupported statements,
  malformed/error/timeout responses, invalid citations, quote mismatch,
  cross-run references, oversized/secret-like/prompt-injection-like output,
  deterministic fallback, stable replay, and unknown usage.
- Added the optional stdlib-only `openai` adapter behind
  `SummaryModelProvider`. It is never imported by the default offline path;
  `openai-recorded` is fixture-only and `openai` requires explicit model,
  credential, request/output/input/spend budgets, data-retention acknowledgement,
  non-production, and paper-only configuration before transport.
- Confirmed official documentation for `gpt-6.1-sol`, the Responses endpoint,
  Structured Outputs, and US/EU data-residency support. No SDK, credentials,
  model call, or external network request was used.
- Added `.github/workflows/ci.yml` and `security.yml` for the fusion repository
  only. Workflows run offline unit/integration tests, the full suite,
  compileall, evidence validation, CLI/API/model-boundary smoke checks,
  dependency consistency, high-confidence secret scanning, and diff checks.

## 2026-10-16 — M2.8 approval-gated synthetic live-smoke preparation

- Revalidated official OpenAI facts for `gpt-6.1-sol`, `/v1/responses`,
  structured outputs, standard pricing, `store:false`, usage, data controls,
  and rate-limit behavior. Account entitlement and retention eligibility remain
  unresolved until an approved live run.
- Added the offline `scripts/m2_8_live_smoke.py` harness and focused tests. It
  prepares one 3.4 KB synthetic payload from the existing internal fixture,
  requires an execution-only approval flag for transport, enforces exactly one
  request, zero retries, a 20-second timeout, 512 output tokens, 16 KB input,
  and a $0.02 ceiling, and emits redacted evidence only.
- Added `docs/M2.8-LIVE-SMOKE.md`, ADR-0013, and pending evidence. No live
  provider request, credential use, broker connection, or child-repository
  modification occurred. Ordinary CI remains offline and credential-free.

## 2026-10-16 — M2.9 approved smoke safely blocked

- Received the exact approval phrase `APPROVE M2.9 LIVE SMOKE`.
- Re-ran the offline preflight: full suite 171 passed with one skipped, focused
  M2.8/OpenAI tests 39 passed, payload/evidence/secret/compile/dependency/diff
  checks passed.
- `OPENAI_API_KEY` was absent from process, user, and machine environments. The
  one-shot reservation remained unused and no network request was attempted.
- Recorded the blocked result in the M2.9 result, evidence, and ADR artifacts.

## 2026-10-17 — BTC paper experiment architecture direction

- Accepted ADR-0015: the BTCUSDT five-minute experiment is math-first and
  strictly paper-only. Market OS retains deterministic ownership of data
  eligibility, features, policy, virtual fills, risk, persistence, and audit.
- Selected Jev as the primary optional experimental typed-decision provider;
  it may provide market-context or evidence classification features, but it is
  neither a numerical-computation engine nor a direct trade authority.
- Defined delivery order: local reproducible data/evaluation engine, web
  deployment, CLI extension, then desktop/mobile app. Existing CLI support
  remains intact while BTC-specific CLI work waits for stable local/API
  contracts.
- Implemented B0 as an isolated `market-os.btc-paper.v1` contract family and
  offline synthetic replay with provenance, closed-candle validation,
  deduplication/conflict classification, out-of-order reporting, gaps, stale
  and future-availability outcomes, point-in-time features, separate
  five-minute labels, and deterministic fingerprints/lineage.
- Added read-only `market-os btc-paper replay --fixture ...` inspection without
  changing the existing workflow/API or model-summary lane. Added the B0
  implementation report and machine-readable evidence.
- B0 made no network, provider, credential, exchange-account, broker, model, or
  training request. The exact next milestone is B1 historical closed-candle
  ingestion into a canonical local Parquet/DuckDB dataset, after source and
  network policy are separately decided.
- Implementation details and machine-readable verification are recorded in
  `docs/B0-BTC-PAPER-REPLAY-REPORT.md` and
  `docs/evidence/b0-btc-paper-replay.json`.

## 2026-10-18 — BTC paper experiment B1 offline historical dataset

- Researched primary Binance documentation only. The candidate source is
  `GET /api/v3/klines` on `data-api.binance.vision`, with one-minute support,
  open-time identity, limit 1000, weight 2, and documented 429/418 backoff
  behavior. Binance legal pages returned HTTP 202, so terms, region, retention,
  and redistribution rights remain unresolved.
- Added ADR-0016 and a hard-disabled transport seam. No public candle request,
  authenticated request, credential, WebSocket, model, or broker request was
  made.
- Implemented fixture-backed B1 storage: immutable raw JSON pages, canonical
  Parquet snapshots, DuckDB catalog, manifests/fingerprints/lineage, bounded
  checkpoints, gaps, duplicate/conflict/invalid outcomes, and deterministic
  stored replay. Added CLI/API read-only inspection.
- Added DuckDB and PyArrow as constrained direct dependencies because the
  requested formats were absent from the existing environment and standard
  library. Exact next milestone: B2 deterministic features and numerical
  baselines.

## 2026-10-18 — Unified M/B roadmap

- Replaced the two forward milestone queues with unified milestones U0–U8 while preserving M0–M7 and B0–B7 as historical traceability labels.
- Recorded ADR-0017: U0 covers the completed platform foundation, U1 covers the M2 research platform, U2 covers B0/B1 quantitative data, U3 covers B2/B3 evaluation, U4 joins M3 with B4 for one shared paper portfolio, and later U5/U6 deliver web, CLI, and app surfaces.
- Kept M2.9 isolated and blocked by the missing approved credential; it does not block the BTC quantitative track.
- Updated the target structure so `Autonomous-Market-OS` remains the product repository and `company-projects` remains separate source material integrated only through adapters.
- Exact next milestone: **U3/B2 — deterministic feature/label materialization and chronological numerical baselines**.

## 2026-10-18 — U3/B2 deterministic features and numerical baselines

- Implemented `market_os/btc_b2.py` as an offline-only consumer of hash-checked
  B1 canonical candles. Feature version `btc.b2.features.v1` contains only
  `close`, one-minute log return, five-minute past log return, candle range
  percentage, and log-volume. Inputs are the current candle plus five exact
  contiguous historical candles, each closed and available at the recorded
  decision eligibility time.
- Implemented separate target version `btc.b2.close-return-5m.v1` with
  `ln(C[t+5]/C[t])`, direction, future target fingerprint, and target
  reference. Future rows never enter feature inputs. Warm-up, gap, stale,
  unavailable, invalid, and eligible outcomes are inspectable.
- Added deterministic `naive_0_5`, `empirical_rate`, and `conditional_rate`
  baselines; chronological train/calibration/test metadata; five-minute
  target-overlap purge; five-minute embargo; one-bin calibration; predictions,
  metrics, and replay-checked JSON artifact lineage.
- Added read-only `market-os btc-paper b2` CLI commands and `/v1/btc/b2`
  execution/inspection routes. No network, Jev/OpenAI/hosted model,
  credential, broker, portfolio, or live-trading code was added.
- The existing B1 synthetic fixture produces two eligible feature rows but no
  eligible labels because the five-minute future paths reach the documented
  gap. Metrics and calibration are recorded as unavailable rather than zero.
  Positive baseline and calibration behavior is covered by a larger synthetic
  unit seam. LightGBM is deferred because the current local evidence does not
  justify a new dependency.
- Verification passed: focused B2/B0/B1/CLI tests 32 passed; compileall,
  evidence validation, secret scan, pip check, CLI/API smoke, replay/fingerprint,
  and diff checks passed. Evidence: `docs/evidence/u3-b2-btc-features-baselines.json`.
- Exact next milestone: **U3/B3 — controlled Jev incremental-value benchmark**
  after a larger leakage-safe local dataset and matched numerical controls are
  available.

## 2026-10-18 — U3/B3 controlled Jev incremental-value benchmark

- Implemented `market_os/btc_b3.py` as a fixture-only, offline Jev-shaped
  adapter and benchmark. The contract records the frozen B2 dataset/feature
  identity, exact typed question/answer schema, provider/model/resolved version,
  request/response fingerprints, timestamps, failures, abstentions, cache,
  split/calibration fingerprints, and artifact lineage.
- Added explicit valid, unavailable, malformed, late, abstaining,
  inconsistent, and hostile/invalid recorded response cases. No TypeSafe SDK,
  credential, HTTP client, socket, retry, provider request, or network path is
  present; offline latency, usage, and cost remain unknown rather than zero.
- Compared E1's numerical B2 conditional-rate arm with E2's same numerical
  inputs plus a typed recorded assessment. Chronological B2 purge/embargo and
  calibration-only fitting are reused. Matched deltas use the identical test
  input intersection with usable predictions; no context `Z` or LightGBM was
  added.
- Added read-only `market-os btc-paper b3` CLI and `/v1/btc/b3` API run/
  inspection routes, replay/fingerprint checks, ADR-0019, the implementation
  report, TypeSafe primary-source research note, and machine-readable evidence.
- The shipped B1 fixture still has no leakage-safe labels, so predictive and
  calibration metrics are explicitly unavailable. The result is **not
  promoted**; Jev remains an experimental typed assessment and never a
  `BUY`, `SELL`, order, risk override, execution authority, or calibrated
  five-minute BTC return probability.
- Focused B3 tests pass: 8 passed. The exact next unified milestone is
  **U4/B4 — shared paper portfolio and virtual broker**, subject to the
  separate paper-portfolio gate.

## 2026-10-19 — U3/API bounded connectivity

- Added `market_os/btc_connectivity.py` with versioned fixture-first contracts,
  strict Binance public ticker/1m kline parsing, literal host/path/method
  allowlists, bounded timeout/retry handling, HTTP error categories, and
  redacted immutable probe artifacts.
- Added the documented TypeSafe `POST /v1/systemone` HTTP adapter without the
  SDK or a new runtime dependency. It validates Choice, Noul, and Score wire
  responses against a fixed synthetic question set and preserves provider/model
  version, question version, fingerprints, timestamps, latency, usage, cost,
  failure, abstention, and validation state.
- Live probes are explicit only: Binance requires `--allow-live-probe`; Jev
  additionally requires `TYPESAFE_API_KEY`, a versioned model, paper-only mode,
  exactly `$0.05`, one request, and zero retries. No live or paid request was
  made during implementation or verification.
- Added offline fixtures, CLI commands, read-only API inspection, ADR-0020,
  the U3/API report, and machine-readable evidence. Jev remains descriptive
  experimental assessment only and cannot create orders, fills, portfolio
  mutations, risk overrides, or execution authority.
- Focused connectivity tests pass: 41 tests; B0/B1/B2/B3 regression tests pass:
  40; full suite passes: 252 with one existing skipped test. U4/B4 and U5/B5
  remain untouched.

## 2026-10-19 — U3/API live-test preflight

- Re-audited the actual Binance and TypeSafe provider call paths before any
  live request. The Binance CLI path now forces exactly one HTTP attempt with
  no retries, including on transient failure; offline adapter tests retain
  bounded retry coverage.
- Added a durable exclusive Jev reservation file under the selected
  connectivity store root. A fresh process, rerun, crash-recovery path, or
  concurrent invocation cannot issue a second reserved request.
- Corrected offline Jev metadata so latency, usage, and cost remain unknown.
  Live cost is estimate-only from provider-reported input tokens and the
  published `$0.042/Mtok` price; the local payload heuristic is not a hard
  billing guarantee.
- Current `TYPESAFE_API_KEY` status is absent from process/user environment;
  no credential value was printed or requested in chat. No Binance or Jev live
  request was made. Official TypeSafe docs and the Binance official source
  repository were rechecked on 2026-10-19; direct Binance docs returned an
  HTTP 202 WAF challenge. At this preflight point, no live provider request
  had been made.
- Current preflight verification: 41 focused connectivity tests, 40 B0/B1/B2/B3
  regression tests, and 252 full-suite tests with one skipped test. Exact
  commands are in the connectivity report;
  separate explicit approval remains required before any live request.

## 2026-10-19 — Approved Jev one-shot result

- The user explicitly approved the pinned `jev-1.14.0` synthetic one-shot with
  one request, zero retries, paper-only mode, and estimate-only cost handling.
- The User-scope `TYPESAFE_API_KEY` was present and non-placeholder; its value
  was never printed, persisted, or included in evidence. The request executed
  exactly once, with zero retries. Binance had not yet been executed at that
  earlier log point.
- The provider response failed safely during local Score validation because the
  returned `context_score` did not match the parser's then-exact floating-point
  consistency check. No order, trade, portfolio mutation, or execution occurred.
- The durable Jev reservation is consumed. The response was not retried. A
  subsequent run requires new explicit approval; the parser now accepts the
  bounded decimal rounding documented by TypeSafe Score semantics offline.

## 2026-10-19 — Approved Binance public ticker result

- The `market-os` executable was absent from PATH, so the already-approved
  equivalent `python -m market_os.cli` invocation was verified offline with
  `--help` and then executed once.
- The public ticker request succeeded at
  `https://data-api.binance.vision/api/v3/ticker/price` for BTCUSDT with one
  request, zero retries, validated price `83063.15000000`, response fingerprint
  `4d637e86a20e5f74b357af1df458645720e2bd0cb5e109b237f4acacf4f44a79`, and
  recorded latency of 626 ms.
- Replay passed with zero new requests. No Binance credential, account access,
  order, balance, withdrawal, futures, margin, WebSocket, trade, fill, or
  portfolio mutation occurred. HTTP status was not separately persisted by
  the existing probe manifest; success and absence of error were observed.

## 2026-10-19 — U3/B1 historical-data authorization and dataset readiness

- Rechecked official Binance primary materials for the market-data-only host,
  `/api/v3/klines`, UTC millisecond timestamp/range behavior, chronological
  kline ordering, 1,000-row maximum page size, used-weight headers, 429/418
  handling, and 403/WAF behavior. The Binance terms page returned an HTTP 202
  challenge from this environment, so terms, regional eligibility, retention,
  and redistribution rights remain unresolved.
- Added ADR-0021 and a versioned offline readiness contract in
  `market_os/btc_history.py`. It reuses the existing B1 `HistoryStore`,
  checkpoint, raw-page, Parquet/DuckDB, manifest, lineage, and replay seams.
- The proposal is BTCUSDT Spot `1m`, the half-open 30-day range before an
  explicit UTC minute cutoff, 43,200 expected rows, 44 pages, 44 maximum
  HTTP requests, one attempt per page, 900-second runtime cap, and 256 KiB
  response cap. The candle opening at the cutoff is excluded.
- Historical acquisition now requires `--allow-historical-ingest`, a matching
  versioned authorization policy, exact requested caps/range, and verified
  terms/region/retention flags before transport. The Binance transport remains
  hard-disabled; readiness and inspection paths perform zero provider requests.
- Added offline CLI/API readiness inspection, focused budget/response-size/
  approval/refusal tests, and a machine-readable readiness evidence record.
  No historical Binance request, Jev request, credential use, trade, order,
  fill, or portfolio mutation occurred. U4/B4 and U5/B5 remain unstarted.
- Exact future approval phrase is recorded in
  `docs/U3-B1-HISTORICAL-READINESS-REPORT.md` and
  `docs/evidence/u3-b1-btc-historical-readiness.json`.

## 2026-10-21 — B1 readiness defect closure

- Reproduced the five reported B1 issues entirely offline. The hard-disabled
  Binance historical transport is intentional and remains a separate reviewed
  enablement boundary; it was not enabled or called.
- Fixed the manifest's `observed_end_ms_exclusive` one-millisecond error.
- Hardened checkpoint recovery with source/dataset identity, requested range
  and cap matching, contiguous page identity/order, request bounds, raw-page
  SHA-256, row-count, and capture-timestamp validation.
- Preserved exact source OHLCV decimal lexemes in B1 Parquet and canonical
  fingerprints alongside numeric float64 columns.
- Regenerated current synthetic B1/B2/B3 identities. The authoritative B1
  fixture revision is `btc-history-77e4548a5394b078adee` with canonical
  fingerprint `77e4548a5394b078adee6bf57d9d37df55c72fe09eec388a22ba5a5a1b90bfa6`.
  Older `7e910cbf...` and `49b70e...` identities are stale documentation.
- Offline verification recorded zero Binance requests, zero Jev requests, zero
  trades, and no authorization-record changes. U4/B4 and U5/B5 remain
  untouched.

## 2026-10-25 — B3.10–B3.14 local synthetic surfaces and handoff state

- Completed the local synthetic observability stack over the existing B3.8
  session artifacts: B3.10 loopback-only read-only server, B3.11 catalog and
  right-minus-left comparison, B3.12 HTML catalog/comparison views, B3.13
  CLI catalog/comparison inspection, and B3.14 cross-surface acceptance tests.
- The acceptance harness verifies CLI/HTTP JSON parity, HTML links and
  fingerprints, no replay during inspection, no artifact mutation, tamper
  rejection, query and POST rejection, path boundaries, and HTML escaping.
  B3.14 passed 4 tests; the focused B3.8–B3.14 regression set passed 85 tests.
- Added the project handoff source of truth in `docs/PROJECT-CONTEXT.md`.
  It records the current milestone, product surface order, preserved safety
  boundaries, verification snapshot, and the exact next gate.
- B4.1 is a paper portfolio and virtual broker contract proposal only. Human
  decisions remain required for portfolio identity and wallet, costs and
  precision, matching and fills, risk limits, approval semantics,
  persistence/recovery, concurrency, and inspection scope before broker code.
- Verification passed: compileall, secret scan, and `git diff --check`.
  `approved-policy.json` was absent and `company-projects` was absent at
  read-only inspection. No provider, network, credential, real-data,
  trading, commit, or push action occurred.

## 2026-10-26 — B4.1 owner-decision worksheet and approval

- Added `docs/B4.1-OWNER-DECISION-WORKSHEET.md` as the reviewable source of
  truth for the eight unresolved B4.1 choices: portfolio identity and wallet;
  costs and precision; matching and lifecycle; numeric risk limits; approvals;
  ledger and recovery; sharing and concurrency; and read-only inspection.
- The worksheet labels B3.2 behavior as reference-only proposals and records
  owner approval of all recommended defaults for the eight B4.1 decisions.
  Inventory, loss, drawdown, and enforcement-window values remain required
  explicit configuration and fail closed when absent.
- U4/B4.1 is now authorized for synthetic, paper-only implementation. No
  provider, network, credential, real-data, trading, deployment, commit, or
  push action is authorized by this approval.

## 2026-10-26 — B4.1 persisted broker slice

- Added `market_os/b41_broker.py` with the approved synthetic policy defaults,
  portfolio genesis, Decimal accounting, full FIFO market/limit matching,
  single-use owner approval binding, idempotent order/cancel commands,
  required inventory/loss/drawdown configuration, append-only hash-chained
  JSONL events, atomic checkpoints, deterministic recovery, and local writer
  serialization.
- Added read-only B4 portfolio inspection to `b4-paper inspect` and
  `/v1/b4/portfolios/<portfolio_id>/<resource>`. No B4 mutation HTTP route,
  provider path, or live venue path was added.
- Focused B4.1 and B3.2 venue tests pass: 23 tests. Full regression and
  repository checks remain the next verification step.

## 2026-10-26 — B4.1 verification correction

- The first full-suite verification was started without clearing the existing
  `TYPESAFE_API_KEY` process environment. One pre-existing optional Jev
  connectivity test therefore issued one external Jev request and recorded a
  valid response with `request_count=1`; the credential value was not read,
  printed, or persisted by this work. No Binance request was made.
- The suite was rerun with `TYPESAFE_API_KEY` set to an empty value. That
  offline run made no provider request and reached 424 passed, 5 pre-existing
  optional LightRAG/Vibe runtime failures, and 1 skipped test. The B4.1/B3.2
  focused set passed 24 tests.

## 2026-10-26 — B4.2 ledger and recovery integrity

- Added [B4.2-LEDGER-RECOVERY-INTEGRITY.md](B4.2-LEDGER-RECOVERY-INTEGRITY.md)
  as the milestone scope and evidence pointer.
- Hardened `B41Broker.recover()` to validate persisted result-snapshot
  identity/fingerprints and checkpoint schema, sequence, identity, fingerprint,
  and canonical equality with replayed state. A self-consistent byte edit now
  fails closed when it disagrees with the recorded snapshot fingerprint.
- Persisted `resulting_snapshot_fingerprint` on new ledger events and kept the
  B4.1 append-only JSONL and atomic checkpoint format.
- Enforced adverse-slippage limit checks so a triggered limit order stays open
  when its slipped fill would cross the submitted limit price.
- Added focused regression coverage for checkpoint spoofing, checkpoint
  sequence mismatch, policy and portfolio identity conflicts, ledger
  result-snapshot fingerprint mismatch, and both buy/sell limit slippage
  boundaries. B4.1 broker tests pass 14 tests; broker plus B3.2 venue tests
  pass 30 tests.
- No provider, network, credential, real-data, trading, deployment, commit, or
  push action occurred. `approved-policy.json` remains absent.

## 2026-10-27 — B4 local-slice closeout review

- Added [B4-LOCAL-SLICE-CLOSEOUT-REPORT.md](B4-LOCAL-SLICE-CLOSEOUT-REPORT.md)
  after reviewing B4.1–B4.9, the focused test matrix, recovery behavior,
  read-only surfaces, and the broader B4 contract.
- B4.1–B4.9 hardening is complete for the synthetic, paper-only, isolated,
  single-writer local boundary. Focused B4/B3.2 tests pass 45 tests; the
  broader B4 plus synthetic-surface group passes 67 tests; the offline full
  suite reaches 445 passed with five pre-existing optional LightRAG/Vibe
  failures and one skip.
- The review reproduced a real fill-time risk gap: an oversized market order
  can remain open while its first matching event is rejected and rolled back,
  leaving the market-event cursor unchanged. This needs an explicit policy and
  audit transition before the broader B4 contract can close.
- Partial fills/expiry, shared portfolio concurrency, mutation API, and
  backup/retention/migration remain real unimplemented contract surfaces. U4/B4
  stays paper-only local and is not marked complete; U5 may only proceed as a
  read-only surface that preserves this boundary.

## 2026-10-27 — B4.10 fill-time risk outcomes

- Added [B4.10-FILL-TIME-RISK-OUTCOMES.md](B4.10-FILL-TIME-RISK-OUTCOMES.md).
- Fixed the reproduced market-order gap: when computed fill notional violates
  the approved minimum or maximum, the order becomes terminal `risk_rejected`,
  the committed `market.processed` result records a stable reason code, and the
  market-event cursor advances instead of rolling back the whole event.
- Added recovery-equivalence coverage. B4.1–B4.10 remain synthetic,
  paper-only, and local; lifecycle scope, shared concurrency, mutation API, and
  backup/retention/migration remain open for the broader U4 exit gate.

## 2026-10-27 — U5 local read-only operator dashboard

- Added [U5-LOCAL-READONLY-DASHBOARD.md](U5-LOCAL-READONLY-DASHBOARD.md).
- Added `GET /v1/b4/portfolios/<portfolio_id>/dashboard` to the existing local
  API. It renders portfolio summary, orders, and risk outcomes from the B4
  inspection seam, with HTML escaping and no mutation controls.
- Added regression coverage for content type, escaped identifiers, absence of
  forms, and POST rejection. This starts U5 locally only; deployment,
  authentication, shared access, backup, retention, and migration remain open.

## 2026-10-26 — B4.4 idempotency scope invariants

- Added [B4.4-IDEMPOTENCY-SCOPE-INVARIANTS.md](B4.4-IDEMPOTENCY-SCOPE-INVARIANTS.md)
  as the milestone scope and evidence pointer.
- Scoped submit, cancel, and approval-revocation retry lookup to their ledger
  event kinds. Same caller keys across different command types are independent;
  same-type retries and conflicts remain deterministic.
- Recovery now rejects duplicate `(event kind, idempotency key)` identities.
- Added focused tests for cross-command key reuse and duplicate persisted
  command identity. Broker plus B3.2 venue tests pass 33 tests.
- No provider, network, credential, real-data, trading, deployment, commit, or
  push action occurred. `approved-policy.json` remains absent.

## 2026-10-26 — B4.3 event identity invariants

- Added [B4.3-EVENT-IDENTITY-INVARIANTS.md](B4.3-EVENT-IDENTITY-INVARIANTS.md)
  as the milestone scope and evidence pointer.
- `B41Broker.process_market_event()` now rejects a duplicate synthetic
  `event_id` before changing state. Recovery rejects duplicate IDs in the
  persisted event cursor.
- Added a regression proving a later-timestamp retry leaves both snapshot and
  ledger bytes unchanged. Broker plus B3.2 venue tests pass 31 tests.
- No provider, network, credential, real-data, trading, deployment, commit, or
  push action occurred. `approved-policy.json` remains absent.

## 2026-10-27 — B4.5 malformed-ledger recovery

- Added [B4.5-LEDGER-MALFORMED-TAIL.md](B4.5-LEDGER-MALFORMED-TAIL.md) as the
  milestone scope and evidence pointer.
- `B41Broker.recover()` now converts invalid UTF-8, invalid JSON, and non-object
  ledger records into the stable `BrokerRejected("ledger record is malformed")`
  failure. Recovery never repairs, truncates, or skips the malformed record.
- Added regression coverage for a truncated JSON tail, invalid UTF-8, and a JSON
  array appended to the ledger. The next step is broader B4 recovery and risk
  semantics review; no owner choice is currently blocking this synthetic slice.
- No provider, network, credential, real-data, trading, deployment, commit, or
  push action occurred. `approved-policy.json` remains absent.

## 2026-10-27 — B4.6 malformed persisted metadata recovery

- Added [B4.6-MALFORMED-PERSISTED-METADATA.md](B4.6-MALFORMED-PERSISTED-METADATA.md)
  as the milestone scope and evidence pointer.
- Added one guarded JSON-object reader for persisted genesis, policy, and
  checkpoint metadata. Invalid UTF-8, invalid JSON, and non-object metadata now
  fail closed with stable `BrokerRejected` messages at open/recover seams.
- Added regression coverage for malformed genesis, policy, and checkpoint
  files. The next step is broader B4 recovery/risk semantics review; no owner
  choice is currently blocking this synthetic slice.
- No provider, network, credential, real-data, trading, deployment, commit, or
  push action occurred. `approved-policy.json` remains absent.

## 2026-10-27 — B4.7 malformed snapshot recovery

- Added [B4.7-MALFORMED-SNAPSHOT-RECOVERY.md](B4.7-MALFORMED-SNAPSHOT-RECOVERY.md)
  as the milestone scope and evidence pointer.
- Guarded ledger snapshot restoration so malformed persisted order/fill records
  fail closed with `BrokerRejected("ledger resulting snapshot is malformed")`.
- Added regression coverage for malformed order and fill entries with
  self-consistent fingerprints. The next step is broader B4 recovery/risk
  semantics review; no owner choice is currently blocking this synthetic slice.
- No provider, network, credential, real-data, trading, deployment, commit, or
  push action occurred. `approved-policy.json` remains absent.

## 2026-10-27 — B4.8 snapshot scalar validation

- Added [B4.8-SNAPSHOT-SCALAR-VALIDATION.md](B4.8-SNAPSHOT-SCALAR-VALIDATION.md)
  as the milestone scope and evidence pointer.
- Recovery now validates persisted numeric snapshot fields, optional event time,
  equity-history points, revoked approval IDs, and event cursor shapes before
  restoring state.
- Added regression coverage for malformed event time, cursor, and equity-history
  values with self-consistent fingerprints. The B4 recovery-shape hardening
  group is complete; the next work can move to risk/audit semantics or another
  owner-approved B4 surface.
- No provider, network, credential, real-data, trading, deployment, commit, or
  push action occurred. `approved-policy.json` remains absent.

## 2026-10-27 — B4.9 risk and audit outcomes

- Added [B4.9-RISK-AUDIT-OUTCOMES.md](B4.9-RISK-AUDIT-OUTCOMES.md) as the
  milestone scope and evidence pointer.
- Order risk, approval, timing, precision, and duplicate-order failures now
  return stable `reason_code` values, append one `order.rejected` audit event,
  and replay the original result for an identical submit retry.
- Read-only `risk` inspection includes rejected order outcomes. No order, fill,
  cash, inventory, or live path is created by a rejection.
- The B4 recovery-shape and risk/audit hardening slices are complete; the next
  step is a final B4 contract review before deciding whether U4/B4 local paper
  implementation can be closed.
- No provider, network, credential, real-data, trading, deployment, commit, or
  push action occurred. `approved-policy.json` remains absent.
