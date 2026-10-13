# Autonomous Market OS: Phases

## Phase 0 — Alignment and inventory

**Outcome:** a fixed product boundary and an evidence-backed map of existing capabilities.

**Work:** choose the initial user, define paper-trading scope, inventory public entry points, record licenses and dependencies, select the orchestration owner, and freeze the first vertical workflow.

**Exit gate:** product brief, capability ownership table, dependency baseline, and contract list are approved.

## Phase 1 — Platform contracts

**Outcome:** stable interfaces that let independent projects work together.

**Work:** define `AgentProfile`, `Task`, `Run`, `RunEvent`, `Artifact`, `KnowledgeDocument`, `MarketObject`, `Portfolio`, `OrderPlan`, `RiskDecision`, and `Approval` schemas. Define authentication, configuration, errors, idempotency, cancellation, and provenance rules.

**Exit gate:** schemas have examples, runtime validation, versioning rules, and focused contract tests.

**Status:** contract foundation implemented in `market_os/contracts.py`; the remaining gate is approval of the production adapter and storage choices.

## Phase 2 — Research MVP

**Outcome:** one user can request evidence-backed market research through an API and CLI.

**Work:** connect the selected agent runtime, Vibe-Trading research/backtesting capabilities, and LightRAG/RAG-Anything retrieval. Store citations, timestamps, assumptions, and run events.

**Exit gate:** the first vertical slice produces a reproducible cited research result and a retrievable event trace.

## Phase 3 — Paper trading and risk

**Outcome:** research can become a simulated order plan and portfolio update.

**Work:** connect AI-Trader signal and experiment concepts, implement paper broker adapters, risk limits, approval gates, portfolio accounting, and recovery behavior.

**Exit gate:** paper orders are deterministic, idempotent, auditable, cancellable, and cannot reach a live broker.

## Phase 4 — Operator surfaces

**Outcome:** CLI, web, desktop/mobile shell, and chat channels expose the same capabilities.

**Work:** build the versioned gateway API, authentication, run history, portfolio views, research views, approval UI, notifications, and CLI commands.

**Exit gate:** all surfaces invoke the same backend workflow and show consistent run state.

## Phase 5 — Evaluation and learning

**Outcome:** platform quality and agent economics are measurable.

**Work:** connect ClawWork-style task, cost, quality, and survival metrics. Add benchmark scenarios, strategy evaluation, user explanations from DeepTutor, and artifact/report generation from Paper2Slides.

**Exit gate:** regression benchmarks cover research quality, cost, latency, risk checks, and failure recovery.

## Phase 6 — Live execution readiness

**Outcome:** controlled live execution is possible for explicitly enabled accounts.

**Work:** broker authentication, account permissions, exposure limits, pre-trade checks, kill switch, reconciliation, alerts, immutable audit records, and staged rollout.

**Exit gate:** paper/live parity, recovery drills, security review, and explicit human approval are complete.

## Phase 7 — Creative and ecosystem expansion

**Outcome:** the platform becomes a broader agent economy and media surface.

**Work:** add ViMax market videos, CLI-Anything tool registry, strategy sharing, agent marketplace, community signals, billing, and tenant isolation.

**Exit gate:** expansion features do not weaken core trading safety, provenance, or data isolation.
