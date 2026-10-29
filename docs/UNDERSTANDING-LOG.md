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

## 2026-10-28 — B4.11 local backup and restore

- Added [B4.11-BACKUP-RESTORE.md](B4.11-BACKUP-RESTORE.md) and the opt-in
  `backup_portfolio()` / `restore_portfolio()` seams.
- Backups contain the validated genesis, policy, ledger, and checkpoint files
  with a versioned manifest and SHA-256 fingerprints. Restore validates archive
  paths, identities, fingerprints, and broker recovery before atomically
  promoting a new portfolio directory; existing destinations and source-store
  archives are rejected.
- Added CLI `b4-paper backup` and `b4-paper restore` commands. The focused
  broker/backup/venue group passes 50 tests. Retention remains indefinite and
  local; schema migration and shared/mutable surfaces remain separate gates.
- No provider, network, credential, real-data, trading, deployment, commit, or
  push action occurred. `approved-policy.json` remains absent.

## 2026-10-28 — B4.12 read-only migration preflight

- Added [B4.12-MIGRATION-PREFLIGHT.md](B4.12-MIGRATION-PREFLIGHT.md) and
  `market-os b4-paper migration-check` to classify the supported local schema.
- The preflight uses normal broker recovery validation, reports current schema
  status without changing persisted bytes, and fails closed on unsupported or
  malformed stores. It deliberately does not define or apply a future schema
  transformer.
- Added tests for current-schema classification, immutable files, unsupported
  genesis schema, and CLI JSON. Retention/archive policy and transformer remain
  open; shared concurrency and mutation API are not enabled.

## 2026-10-28 — B4 local slice closeout decision

- Closed the B4 local slice at B4.12 for the approved synthetic, paper-only,
  isolated portfolio and single-writer boundary. The evidence matrix, focused
  tests, full offline regression result, compile check, secret scan, and
  evidence validation are recorded in `B4-LOCAL-SLICE-CLOSEOUT-REPORT.md`.
- Kept broader U4/B4 open: lifecycle expansion (partial fills/expiry), shared
  portfolio membership/concurrency, mutation API and complete mutation audit,
  retention/archive operations, and a versioned migration transformer.
- U5 deployment remains deferred by owner direction; the local GET-only view is
  retained as a paper-only artifact.

## 2026-10-28 — U5 local read-only acceptance

- Added [U5-LOCAL-ACCEPTANCE.md](U5-LOCAL-ACCEPTANCE.md) and machine-readable
  evidence at `docs/evidence/u5-local-acceptance.json`.
- The loopback service acceptance covers health/readiness, B4 dashboard HTML,
  JSON summary parity, escaped content, POST rejection, and query rejection.
- The static preview passed its Node contract test and a Playwright browser
  smoke: no scripts, forms, credentials, horizontal mobile overflow, or console
  errors; one document request only.
- U5 is accepted locally. Deployment, authentication, shared access, mutation,
  retention/archive, migration transformation, and live trading remain out of
  scope.

## 2026-10-28 — B4.13 local concurrency contract

- Added [B4.13-CONCURRENCY-CONTRACT.md](B4.13-CONCURRENCY-CONTRACT.md) for the
  approved isolated portfolio and one-writer local boundary.
- Added regression coverage proving a stale broker instance is rejected until
  it reloads, independent portfolio identities keep separate ledger sequences
  and lock files, and reload preserves the committed snapshot fingerprint.
- No shared membership, distributed ownership, network lock, or mutation route
  was added. The next contract choice is whether to define a shared portfolio
  or move to a mutation API on the existing single-writer boundary.

## 2026-10-28 — B4.14 local mutation audit outcomes

- Added [B4.14-MUTATION-AUDIT-CONTRACT.md](B4.14-MUTATION-AUDIT-CONTRACT.md).
- Submit, cancel, and approval-revocation validation failures now return stable
  reason codes and append audit outcomes. Identical rejected retries replay the
  recorded result; recovery and read-only inspection preserve those outcomes.
- Idempotency conflicts remain fail-closed and append a separate audit event
  without a command idempotency key, preserving recovery identity uniqueness.
- CLI and HTTP mutation routes remain disabled. Focused B4 verification passed
  62 tests; broader U4 gaps remain lifecycle expansion, shared membership and
  concurrency, external mutation API, retention/archive, and migration transform.

## 2026-10-28 — U5.1 local service boundary hardening

- Added [U5.1-LOCAL-SERVICE-BOUNDARY.md](U5.1-LOCAL-SERVICE-BOUNDARY.md).
- The HTTP service now rejects non-loopback bind addresses and untrusted Host
  headers, completes startup recovery before opening the listener, and records
  only URL paths in structured request logs.
- Added regression coverage for all three boundaries. Authentication, shared
  access, retention, and production deployment remain separate gates.
- The initial U5.1 verification snapshot reached 477 passed and 1 skipped in the
  non-integration suite (5 integration tests deselected). The full suite reached
  477 passed, 5 optional LightRAG/Vibe integration failures from separate
  reference-environment dependency issues, and 1 skipped. Those runtime
  discovery failures were later resolved; see the final verification entry
  below.

## 2026-10-28 — Optional provider runtime discovery repair and final B4 verification

- Added a test-only optional-runtime resolver that honors explicit environment
  overrides, scans the local temporary runtime family, validates executable
  files, and requires deep import probes before selecting LightRAG or
  Vibe-Trading. Stale broken virtualenvs are ignored; Market OS core
  dependencies and the separate reference repositories remain unchanged.
- Re-ran the complete suite with `TYPESAFE_API_KEY=''`: **482 passed, 0
  failed, 1 skipped**. All five optional LightRAG/Vibe integration tests pass;
  the CI-compatible non-integration run remains 477 passed, 1 skipped, with
  five integration tests deselected.
- Compileall, secret scan, evidence validation, and `git diff --check` also
  passed. B4 remains closed only for the synthetic, paper-only, isolated
  single-writer local boundary; the documented lifecycle, shared concurrency,
  mutation API, retention, and migration-transformer gaps remain open.

## 2026-10-28 — B4.15 shared paper portfolio

- Added [B4.15-SHARED-PORTFOLIO-CONTRACT.md](B4.15-SHARED-PORTFOLIO-CONTRACT.md)
  and ADR-0023 for immutable shared membership, strategy attribution, portfolio-wide
  reservations, local ledger ordering, stale writers, retries, and recovery.
- Kept the existing append-only ledger and legacy isolated identities; shared
  recovery validates membership and reservations and accepts a verified lagging
  checkpoint without rewriting history. CLI and HTTP remain read-only.
- The boundary remains synthetic, paper-only, and local; lifecycle expansion,
  authenticated mutation, retention/archive, and migration transformation remain open.

## 2026-10-28 — B4.16 paper order lifecycle

- Confirmed the owner-approved full-fill, accepted-order FIFO and disabled
  expiry policy in [B4.16-LIFECYCLE-CONTRACT.md](B4.16-LIFECYCLE-CONTRACT.md)
  and ADR-0024. Synthetic volume is informational, not fill capacity.
- Added lifecycle regression cases for full fills, unmatched limits and retained
  reservations, FIFO, cancellation, risk rejection, and recovery. Partial fills
  and order expiry require a separate versioned contract before implementation.
- Re-ran the B4.16 full suite with an empty `TYPESAFE_API_KEY`: 494 passed and
  1 skipped. Corrected the earlier B4.15 evidence that conflated full and
  non-integration results.

## 2026-10-28 — B4.17 local retention and archive integrity

- Added [B4.17-RETENTION-ARCHIVE-CONTRACT.md](B4.17-RETENTION-ARCHIVE-CONTRACT.md)
  and ADR-0025. The ledger remains indefinite and local; validated ZIP backup is
  a non-destructive copy; pruning, deletion, remote archive, and schema transforms
  remain disabled.
- Recovery, backup, and migration preflight now fail closed when a checkpoint
  exists without its ledger. Shared backup/restore tests preserve reservations,
  audit inspection, fingerprints, and source bytes. Migration preflight reports
  the actual isolated or shared genesis schema.

## 2026-10-28 — application surfaces and naming

- Added `apps/web/public`, `apps/cli`, and `apps/gateway` as thin surfaces over
  the existing canonical package. Existing `market_os.api` and `market_os.cli`
  names remain stable for compatibility.
- Added `scripts/build_web_artifact.py` and a parity check between the canonical
  web source and `docs/hosting/market-os/`. The artifact remains static,
  synthetic, paper-only, and read-only; public deployment and authentication
  remain separate U5 gates.
- Verified the product-facing folder split in `STRUCTURE.md`, with canonical
  domain compatibility kept under `market_os/` and thin web, CLI, and gateway
  surfaces under `apps/`. No module rename or public deployment was performed.

## 2026-10-28 — U5.2 static deployment readiness

- Added [U5.2-STATIC-DEPLOYMENT-READINESS.md](U5.2-STATIC-DEPLOYMENT-READINESS.md)
  and `docs/evidence/u5-2-static-deployment.json`.
- `scripts/build_web_artifact.py` now validates the exact three-file artifact,
  source and compatibility-copy byte parity, deterministic packaging, and
  rejects scripts, forms, browser network APIs, external URLs, credentials, or
  extra files.
- Browser review at desktop and 375px mobile found zero console errors, no
  horizontal overflow, and one document request. This prepares a static
  artifact only; public deployment, authentication, and connected API access
  remain separate gates.

## 2026-10-28 — web stack selection gate

- Added [ADR-0027](decisions/ADR-0027-web-stack-selection.md).
- Kept plain HTML as the active web source. Astro is the static-first candidate
  for a future componentized read-only surface; React/Next requires an approved
  authenticated or interactive workflow. No framework dependency was added.

## 2026-10-28 — U5.3 deployment handoff and local diagnostics

- Added [U5.3-DEPLOYMENT-ACCESS-OBSERVABILITY-CONTRACT.md](U5.3-DEPLOYMENT-ACCESS-OBSERVABILITY-CONTRACT.md),
  ADR-0028, and machine-readable evidence.
- Static packaging can now emit a deterministic manifest with exact file hashes
  and the paper-only boundary. Local gateway responses carry `X-Request-ID`,
  which is copied into query-free JSONL audit records.
- No public listener, authentication provider, shared tenant access, mutation
  route, credential, provider, or live venue was enabled.

## 2026-10-29 — U5.4 local operator shell

- Added [U5.4-LOCAL-OPERATOR-SHELL.md](U5.4-LOCAL-OPERATOR-SHELL.md) and
  `docs/evidence/u5-4-local-operator-shell.json`.
- Added a GET-only `/operator/<portfolio-id>/` shell with fixed local assets,
  summary parity, accessible focus states, responsive layout, and explicit
  paper-only boundary copy. The summary contract now exposes `open_orders` as a
  stable derived count.
- Route tests reject query parameters, POST, traversal/private assets, and
  untrusted hosts. No public deployment, authentication, mutation route,
  provider, credential, or live venue was enabled.

## 2026-10-29 — U5.5 web stack gate and surface naming polish

- Added [WEB-STACK-OPTIONS.md](WEB-STACK-OPTIONS.md),
  [U5.5-AUTHENTICATED-CONNECTED-WEB-CONTRACT.md](U5.5-AUTHENTICATED-CONNECTED-WEB-CONTRACT.md),
  ADR-0029, and machine-readable U5.5 evidence.
- Kept plain HTML active, selected Astro as the next static-first candidate,
  reserved React + Vite for richer client interaction, and deferred Next.js
  until authenticated server rendering and a separately operated runtime are
  approved.
- Polished the local operator asset names to `operator.js` and `operator.css`.
  The gateway keeps `app.js` and `styles.css` as compatibility aliases so
  existing local bookmarks and tests continue to work.
- Clarified `apps/web`, `apps/cli`, and `apps/gateway` as the active product
  surface split. Desktop/mobile folders remain reserved for concrete shell
  workflows; no generic `apps/app` folder or framework dependency was added.
- The next gate is a concrete deployment target and identity boundary. The
  system remains loopback-only, synthetic, paper-only, read-only, and local.

## 2026-10-29 — U5.6 local portfolio inspection

- Added [U5.6-LOCAL-PORTFOLIO-INSPECTION.md](U5.6-LOCAL-PORTFOLIO-INSPECTION.md),
  ADR-0030, and machine-readable U5.6 evidence.
- Extended the local operator shell to read the existing B4 `summary`,
  `genesis`, `reservations`, `orders`, and `risk` resources in parallel.
- Added a GET-only `/operator/` portfolio directory and `/v1/b4/portfolios`
  JSON catalog. Only portfolios that pass normal broker recovery validation are
  listed.
- Added responsive identity, reservation, order, and append-only risk-audit
  panels. Values are rendered with DOM text nodes and the Python broker remains
  authoritative for all accounting, membership, recovery, and fingerprints.
- Focused operator, U5 acceptance, and application-surface tests remain green.
  No framework, credential, provider, public listener, mutation route, or live
  venue was added.

## 2026-10-29 — U5.7 web stack and deployment matrix

- Added [U5.7-WEB-STACK-DEPLOYMENT-MATRIX.md](U5.7-WEB-STACK-DEPLOYMENT-MATRIX.md),
  ADR-0031, and machine-readable evidence.
- Separated framework selection from deployment selection. Plain HTML remains
  active; Astro is the first framework candidate, React + Vite requires real
  client-side interaction scope, and Next.js requires authenticated server
  rendering plus an operated runtime.
- Kept loopback service and static artifact handoff as the only active targets.
  Private authenticated preview and public connected deployment remain
  unselected until identity, tenant isolation, session, secret, rate-limit,
  audit, backup, rollback, and operator access inputs are concrete.

## 2026-10-29 — U5.9 bounded local inspection

- Added [U5.9-BOUNDED-LOCAL-INSPECTION.md](U5.9-BOUNDED-LOCAL-INSPECTION.md),
  ADR-0033, and `docs/evidence/u5-9-bounded-local-inspection.json`.
- Added a single versioned aggregate GET for both local web surfaces, compacted
  the summary event cursor to a count, and added exclusive pages for orders and
  risk outcomes with a 1–100 page-size limit.
- Verified latest/older navigation in Next.js and the compatibility HTML shell
  against 27 synthetic open orders and 10 synthetic rejection outcomes. The two
  cursors remain independent. The production browser had no console errors and
  the 375px document had no horizontal overflow.
- Ledger recovery and risk-page selection remain linear. Complete genesis
  membership/reservation sets and the old full-history `/risk` route remain
  local-only; U5.5 still gates any connected deployment.

## 2026-10-29 — U5.10 bounded members and reservations

- Added [U5.10](U5.10-BOUNDED-MEMBERS-RESERVATIONS.md),
  [ADR-0034](decisions/ADR-0034-u5-10-bounded-members-reservations.md), and
  `docs/evidence/u5-10-bounded-members-reservations.json`.
- Added a v2 read-only aggregate that pages sorted members and current open
  reservations while retaining portfolio-wide reservation totals. The Next.js
  operator and HTML shell now expose four independent page cursors; v1 remains
  unchanged for compatibility.
- Verified 30 members, 27 open reservations, 37 orders, and 10 risk outcomes
  across both surfaces. All cursors remained independent, the browser console
  had no errors, and both 375px documents fit the viewport after fixing a
  min-content overflow in the HTML shell.
- The v1 aggregate, legacy routes, and catalog remain compatibility paths;
  connected access remains behind U5.5, and B4 deletion/schema transformation
  remain separate gates.

## 2026-10-29 — U5.11 bounded catalog and legacy resources

- Added [U5.11](U5.11-BOUNDED-CATALOG-LEGACY-RESOURCES.md),
  [ADR-0035](decisions/ADR-0035-u5-11-bounded-catalog-legacy-resources.md),
  and `docs/evidence/u5-11-bounded-catalog-legacy-resources.json`.
- Added bounded catalog paging to both local registries. Catalog rows now
  return a member count instead of every strategy ID. Unrecoverable entries
  are counted and announced; a concurrent ledger change returns HTTP 409.
- Added 1–100 row cursors for legacy B4 member, reservation, order, fill, risk,
  approval, and ledger resources. The v1 aggregate now pages members and
  reservations as well. The full snapshot HTTP export is rejected.
- Verified 28 synthetic portfolios plus one unreadable synthetic directory
  through production Next.js and the HTML compatibility shell. Pages returned
  25/3 and 2/2 rows; both surfaces announced the skipped directory, browser
  errors were zero, and the Next.js document fit at 375px.
- Focused regression suite: 50 passed, including invalid cursor rejection and
  concurrent catalog state-change conflicts. TypeScript check, production
  build, and compile/diff checks passed.
- Catalog enumeration, per-portfolio recovery, and one-pass ledger-page scans
  remain linear. Connected access remains behind U5.5; B4 deletion and schema
  transformation remain separate gates.

## 2026-10-29 — U5.12 one-pass audit page freshness

- Added [U5.12](U5.12-ONE-PASS-AUDIT-PAGING.md), [ADR-0036](decisions/ADR-0036-u5-12-one-pass-audit-paging.md), and its machine-readable evidence.
- Risk and ledger page selection now captures the final event fingerprint in
  the same pass used to validate the recovered head, cursor, totals, and rows.
  Cold recovery and append-only chain validation are unchanged.
- A 100-record synthetic ledger showed ledger-page median moving from 28.8 ms
  to 20.6 ms and risk-page median from 26.4 ms to 20.3 ms; cold recovery
  remained around 408 ms. The measurements are diagnostic samples, not CI
  thresholds.
- The focused Python group passed 53 tests. Catalog enumeration and
  per-portfolio recovery remain the next local performance gate; connected
  access and B4 deletion/schema transformation remain separate decisions.

## 2026-10-29 — U5.13 streamed ledger-head validation

- Added [U5.13](U5.13-STREAMED-LEDGER-HEAD.md), [ADR-0037](decisions/ADR-0037-u5-13-streamed-ledger-head.md), and its machine-readable evidence.
- `_ledger_head()` now decodes the full file in bounded chunks, retains only
  the candidate final non-empty line for parsing, and parses only that record.
  Interior invalid UTF-8 and raw-tab corruption at a chunk boundary remain
  fail-closed; blank Unicode whitespace lines are discarded and 1 MiB
  same-line whitespace is preserved through parsing.
- On a synthetic 100-record ledger, compact summary freshness median moved
  from 5.47 ms to 4.44 ms. Cold recovery timings varied; the focused Python
  group passed 60 tests.
- Catalog enumeration and per-portfolio cold recovery remain linear. Connected
  access and B4 deletion/schema transformation remain separate decisions.

## 2026-10-29 — U5.14 cursor-aware catalog sorting

- Added [U5.14](U5.14-CURSOR-AWARE-CATALOG-SORT.md), [ADR-0038](decisions/ADR-0038-u5-14-cursor-aware-catalog-sort.md), and its machine-readable evidence.
- Later catalog pages now filter directory names at or before the exclusive
  cursor before sorting. Cursor validation, skip counts, page ordering, and
  full candidate recovery remain intact.
- Synthetic temporary trees (100, 1,000, 10,000 directories) scanned every
  entry as before; middle/last pages reduced sort inputs to N/2 and 1.
  Cursor paths remain inside the catalog root and symlink/reparse paths fail
  closed. Linked writer-lock files, including dangling targets, are rejected
  without an external write. Diagnostic timings exclude portfolio recovery.
  Focused Python group: 65 passed; Windows drive-qualified path regression ran.
- Full directory enumeration and cold portfolio replay remain the integrity
  floor under the current store contract. Connected deployment and the
  separate B4 retention/schema gates remain open.

## 2026-10-29 — U5.15 Next.js local BTC dataset registry

- Added the bounded, revision-ordered `GET /v1/btc/history/datasets` catalog
  and server-rendered `/datasets` route. The endpoint is bound to the configured
  HistoryStore, does not initialize an absent store, opens existing DuckDB
  catalogs read-only, and returns metadata without filesystem paths.
- Added strict query, response-shape, pagination, and UTC timestamp validation.
  Code review found that a regular file at `btc-history` could be mislabeled as
  an empty store and that timestamps outside JavaScript's `Date` range could
  fail rendering. Both now return an integrity error and have regressions;
  two independent review follow-ups confirmed the fixes and found no further
  issue in this slice.
- The initial focused suite passed 66 tests; the API/HistoryStore suite passed
  37 tests after the review fixes. TypeScript checking and the production build
  passed. Browser smoke covered populated paging, desktop/mobile layout,
  375px width, and zero console errors; empty-store no-initialization is covered
  by the API regression. Screenshots are under `output/playwright/u5-15/`.
- The registry displays metadata only. Candle details, ingestion manifests,
  and experiment/report views still require bounded contracts before exposure;
  U5.5 connected deployment and the U5.14 enumeration/recovery limits remain.

## 2026-10-29 — U5.16 Next.js bounded BTC candle detail

- Added `GET /v1/btc/history/datasets/<revision>/candles` with a fixed
  configured store, read-only catalog access, 1–100 row pages, ascending open
  timestamps, and an exclusive cursor that must identify a stored candle.
- Verified the expected relative Parquet path and streamed its file hash before
  each page. The response contains only bounded timestamps and decimal strings;
  path/hash tampering fails with an integrity response. Canonical replay remains
  necessary to validate the dataset fingerprint.
- Added `/datasets/<revision>` as a server-rendered detail page linked from the
  registry. It displays dataset coverage/fingerprint and a seven-column candle
  table with GET pagination. The labelled table scrolls inside its region at
  375px, while the document width matches the viewport; browser errors were
  zero. Focused API/HistoryStore tests passed 39 cases; Next.js build passed.
- UI search supported a dense data table and keyboard-scrollable region. A
  screenshot review caught the mobile boundary separator overriding its hidden
  rule; the more specific mobile selector now hides it. No chart or decorative
  animation was added.
- A follow-up security review found that symlink loops could escape the typed
  error response. Path-resolution failures now become a generic integrity
  response, with a route regression; spec and security reviewers confirmed the
  fix and evidence count, with no remaining actionable findings.
- Detail and candle-page links disable background prefetch so viewport
  observation does not trigger a full-file hash read.
- Per-page hashing remains linear in file bytes. Ingestion-manifest and
  experiment/report views still need bounded contracts; connected deployment
  remains behind U5.5 decisions.

## 2026-10-29 — U5.17 Next.js bounded BTC ingestion manifests

- Added fixed-store read-only manifest endpoints for revision-bound catalog
  paging and manifest detail. Pages return at most 100 summaries with an
  exclusive manifest cursor; details use ID-derived paths, stay within local
  manifest storage, read at most 8 MiB, and verify file SHA-256 against the
  DuckDB catalog before parsing.
- Added `/datasets/<revision>/manifests` and a per-manifest detail page. The
  response displays fixed scalar metadata, outcome counts, and counts for raw
  pages, gaps, and parent revisions. Paths, raw arrays, and provenance are not
  sent to the browser; all inspection remains GET-only.
- A security review found a configured-root resolution failure could include a
  local path in the error body. The route now returns a fixed integrity message;
  its regression passed, and the reviewer confirmed closure with no further
  findings. The independent security review found no actionable issues.
- The focused operator/API/HistoryStore group passed 41 tests; Next.js
  typecheck and production build passed. Desktop and 375px browser smoke
  exercised the registry → dataset → manifest list → detail flow and next-page
  navigation. The mobile document stayed 375px wide with the 912px manifest
  table contained in a 341px scroll region; console errors were zero. Screenshots
  are in `output/playwright/u5-17/`.
- Manifest details above 8 MiB fail closed. Outcome rows, gap rows, raw
  provenance, and B2/B3 experiment/report views remain separate bounded local
  web slices. U5.5 connected deployment remains gated on target, identity,
  isolation, and operations decisions.

## 2026-10-29 — U5.18 Next.js bounded BTC research inspection

- Added configured-root B2/B3 run catalogs with strict, exclusive run-ID
  pagination and no store creation on GET. Legacy B2/B3 resource stores now
  also use read-only mode and cannot persist through those instances.
- Detail requests read only the fixed metrics/report artifact, cap run
  manifests and result files at 256 KiB, and verify result bytes against stored
  size and SHA-256 before parsing. B2 metric counts match the run sample count;
  B3 report checks include fixture lineage, matching inputs, offline request
  counts, and the `not-promoted` boundary.
- Added `/experiments` B2/B3 catalogs and server-rendered detail pages. The
  375px browser pass contained the 1,205px B2 and 698px B3 tables in 341px
  scroll regions; the document stayed 375px wide and 61 browser requests stayed
  on loopback, with no console errors. Screenshots are in
  `output/playwright/u5-18/`.
- Focused research/operator tests passed 29 cases; Next.js typecheck and
  production build passed. The B1 fixture's empty leakage-safe test set remains
  explicitly unavailable; the U5.5 connected deployment gate remains.

## 2026-10-29 — U5.19 Next.js bounded BTC ingestion records

- Added manifest-scoped, fixed-store GET pages for outcomes, gaps, and raw
  provenance. Each page returns at most 100 ordered rows, enforces a strict
  exclusive cursor, rejects caller roots and duplicate/unknown query fields,
  and opens the configured HistoryStore read-only.
- Outcome status totals match the hash-verified manifest and each page row is
  checked against its raw provenance fingerprint. Gaps are shape/order checked
  after validating the manifest file hash and 8 MiB cap. Provenance full-row
  SHA-256 is checked for payloads up to 256 KiB; the browser receives a maximum
  512-character escaped preview only.
- Added responsive server-rendered views and navigation from manifest detail.
  Synthetic cursor smoke passed across all three resources. Next.js typecheck
  and production build passed. Desktop and mobile browser smoke passed with a
  375 px document and contained 610 px table inside a 341 px scroll region;
  all 78 browser requests stayed on the local operator and console errors were
  zero. Screenshots are in `output/playwright/u5-19/screenshots/`.
- Local bounded B1 detail is complete. The shipped B1 fixture still has no
  leakage-safe B2/B3 test labels. The local TypeScript/React/Node.js/Next.js/
  Tailwind stack is selected and in use. Connected deployment remains behind
  U5.5 target, identity, isolation, and operations decisions.

## 2026-10-29 — U5.20 Local operator overview

- Added `/overview` as a server-rendered entry page across the existing local
  portfolio, BTC history, and B2/B3 research catalogs. Each request is capped
  at three rows, runs independently, and preserves per-resource failure states.
- Added Overview navigation and kept `/` as the existing portfolio registry.
  Catalog summaries identify themselves as first-page previews and do not
  invent whole-catalog totals or performance measures. B3 remains marked
  offline and not promoted.
- The gateway status panel and unavailable guidance now use the configured
  local API port. The page adds no API contract, client-side code, or motion.
- Verification: Next.js typecheck and production build passed. A production
  browser pass covered 375, 768, 1024, and 1440 px, verified local navigation,
  checked the unavailable-gateway state on the configured port, and recorded
  no console errors or page-level horizontal overflow. Standards and spec
  rechecks found no residual issues; security review found no actionable
  issues. Screenshots are in `output/playwright/u5-20/screenshots/`.
- The shipped B1 fixture still lacks leakage-safe B2/B3 labels. Connected
  deployment remains behind the U5.5 target, identity, isolation, and
  operations decisions; select another product surface before the next slice.

## 2026-10-29 — U5.21 Bounded BTC candle visualization

- Added a static server-rendered SVG chart for the current U5.16 candle page,
  capped at 100 rows. Empty cursor pages omit the chart; the exact seven-column
  OHLCV table remains the reference for precise values.
- The chart states its USDT quote unit and bounded page range, displays exact
  page extrema, and distinguishes rising, falling, and flat candles through
  fill, outline, and wick pattern plus a text legend. It adds no client state,
  API request, dependency, provider call, or motion.
- Updated the page design contract and U5 milestone handoff. Typecheck, build,
  browser smoke, screenshot review, and spec/standards/security review results
  are recorded in `docs/evidence/u5-21-bounded-btc-candle-visualization.json`.
- The chart covers only the displayed page and its plot geometry uses numeric
  conversion; exact stored decimal strings remain available in the table.
  Connected deployment remains behind the U5.5 target, identity, isolation,
  and operations decisions.

## 2026-10-29 — U5.22 Bounded portfolio equity history

- Added `GET /v3/b4/portfolios/{portfolio_id}/inspection`, extending the v2
  aggregate with the latest 100 equity samples from the broker's policy-retained
  risk window. Existing v1 and v2 shapes remain unchanged. Python returns exact
  decimal strings, exact extrema for the returned page, total retained count,
  and non-decreasing event-time samples; duplicate timestamps are preserved.
- Switched the local Next.js portfolio detail consumer to v3 and added runtime
  contract validation. The page now displays a static SVG and a bounded exact
  timestamp/value table, with explicit empty, single-point, and truncated-page
  states. TypeScript uses numeric conversion only for approximate SVG geometry.
- No chart library, client component, motion, mutation route, or connected
  deployment behavior was added. Python compileall, the focused API test (1
  passed), and Next.js typecheck/build passed. Production browser smoke passed
  at 375 px and 1440 px with 100 rows/markers and the empty-history state. A
  synthetic one-sample response fixture showed one exact table row and no chart
  at 375 px. There was no horizontal overflow, browser requests stayed local,
  and console errors were zero. Mobile, desktop, empty-state, and single-sample
  screenshots were visually reviewed. Review findings and machine-readable
  evidence are in
  `docs/evidence/u5-22-bounded-portfolio-equity-history.json`.
- The page covers only the latest 100 observations. The broker's configured
  risk window remains the history retention boundary; lifetime history and
  connected access are not implied. U5.5 target, identity, isolation, and
  operations decisions remain the next connected-web gate.

## 2026-10-29 — U5.5 Private single-tenant preview scope

- The owner selected a private, single-tenant, read-only preview direction and
  the TypeScript/React/Node.js/Next.js/Tailwind CSS stack. ADR-0045 records
  these choices; no host, identity provider, or deployment has been selected
  or enabled.
- Research compares Tailscale Serve for tailnet-only clients, Cloudflare Tunnel
  + Access for browser access without a VPN client, and self-operated WireGuard
  with application OIDC. The proposed storage boundary keeps one active Python
  service and an explicit portfolio allowlist.
- Identity propagation from ingress through Next.js to Python, the number of
  allowed subjects in the tenant, exact session and operations policies, and
  the concrete host remain open. U5.5 connected-access code remains gated on
  these decisions and an allowed/denied/expired/replay/forged-principal/
  direct-origin/cross-tenant test matrix.

## 2026-10-29 — U5.23 Responsive operator navigation

- Removed the root's fixed 320px minimum after production-browser inspection
  showed a 15px horizontal overflow at a 320px viewport with a classic
  scrollbar. The dashboard now fits at 320, 375, 768, 1024, and 1440px.
- Kept primary navigation's 44px touch targets and source order; made the
  skip-link target focusable and added a visible keyboard focus outline to
  scrollable table regions. Tab then Enter moves focus from the skip link to
  `main#main-content`.
- Next.js typecheck and optimized build passed. Playwright checked `/overview`,
  `/`, `/datasets`, and `/experiments` at all five widths. The local API was
  unavailable during this shell pass, so catalog routes showed their existing
  unavailable states; backend and detail-data rendering were not exercised.
- Design rules and machine-readable evidence are in
  `design-system/autonomous-market-os/pages/dashboard.md` and
  `docs/evidence/u5-23-responsive-operator-navigation.json`. Connected access
  remains gated by U5.5 owner decisions.
- Commit `a10d594` pushed the U5.23 closeout. CI offline tests and security/package
  checks passed; the static preview artifact build passed. Production deployment
  was skipped after DirectAdmin secret validation failed, so no deployment ran.

## 2026-10-29 — U5.5 access deferral and static preview deployment

- The owner confirmed that the Next.js operator stays loopback-only. Revisit
  Tailscale Serve or Cloudflare Tunnel after the hosting runtime, identity,
  authorization, and portfolio isolation are defined. DirectAdmin applies only
  to the disconnected static preview (see ADR-0045 and ADR-0046).
- Workflow run
  [40853177838](https://github.com/Acceleratorer/Autonomous-Market-OS/actions/runs/40853177838)
  passed the static contract, source parity, and artifact build/upload. It then
  failed validation because the DirectAdmin Actions secrets were unavailable;
  the deployment step was skipped, so no site files changed.
- Deployment is deferred while local milestones are closed. The workflow now
  requires manual dispatch on `main`; pushes do not deploy. Secret values must
  stay out of source, logs, and chat.

## 2026-10-29 — Local-first exit gate audit

- Read `docs/PROJECT-CONTEXT.md` first and continued from the active U5.23/local boundary.
- Preserved the existing uncommitted code, documents, scratch directories, Playwright artifacts, and output files.
- Verified the current local fixes for bounded POST bodies, same-origin browser POSTs, non-creating read-only BTC stores, explicit B2/B3 insufficient-sample outcomes, and non-mutating portfolio inspection locks.
- Full verification passed: 546 tests passed, 0 failed, 7 skipped with provider credentials cleared; compileall, `pip check`, Next.js typecheck/build, the TypeScript static contract, artifact parity, secret scan, M2.8 and evidence validation, and `git diff --check` passed. `npm ci` reported zero vulnerabilities.
- Added `docs/LOCAL-EXIT-GATE-REPORT.md` and `docs/evidence/local-exit-gate.json` as the current local completion record.
- Final security review found no actionable defects in the new read-only CLI/store paths, B4.1 inspection locks, or bounded POST handling. No DirectAdmin deployment was run; push cannot publish the static preview.
- Commit `9aff897` was pushed. GitHub CI run [40865631843](https://github.com/Acceleratorer/Autonomous-Market-OS/actions/runs/40865631843) and Security/package run [40865631753](https://github.com/Acceleratorer/Autonomous-Market-OS/actions/runs/40865631753) passed, including the static artifact job. GitHub emitted only non-blocking runner/action-runtime migration warnings.
- U5.23 is the latest defined web slice. The local gate is closed, but the next feature is unspecified; continue only with a defined loopback-local web task. Connected access remains deferred and no DirectAdmin deployment was triggered.
- Connected web, public deployment, authenticated mutation, partial-fill/expiry expansion, retention deletion, schema transformation, distributed ownership, providers, credentials, and live trading remain deferred gates.
