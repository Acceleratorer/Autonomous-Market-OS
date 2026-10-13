# ADR-0001: Phase 0 product and integration boundary

- **Date:** 2026-10-13
- **Status:** Proposed, pending the human decisions listed below
- **Scope:** first verified paper-trading vertical slice

## Decisions

### 1. First target user

An individual or small research team that wants an evidence-backed answer before placing a simulated allocation. The user can write a natural-language objective, inspect sources and assumptions, reproduce the backtest, and approve a paper order plan. The first user is not an unattended live trader.

### 2. Supported markets

Phase 0 supports **US listed equities and ETFs**, priced in USD, using daily bars and a deterministic local fixture provider. The contract leaves room for other instruments, but crypto, options, prediction markets, FX, and live broker venues are out of the first slice. This keeps calendars, corporate actions, and risk rules bounded while the event and provenance model is proved.

### 3. Orchestration runtime

**OpenHarness** is the proposed orchestration owner because it already exposes tools, skills, memory, multi-agent coordination, CLI, and a service surface. `nanobot` remains a lightweight channel/runtime adapter and `DeepCode` remains a specialized coding-agent adapter. The root workflow depends on a narrow `Orchestrator` protocol, so the decision can be changed without moving domain logic.

### 4. Shared API and domain contracts

The first version is `market-os.v1` and uses typed Python dataclasses serialized as JSON:

- `Task`, `Run`, `RunEvent`, `Artifact`
- `Evidence`, `ResearchResult`
- `BacktestResult`, `OrderPlan`, `RiskDecision`

Every long-running action has a task/run id, UTC timestamp, status, provenance, and artifact lineage. Provider-specific objects stay inside adapters. Live execution is not a valid execution mode in v1.

### 5. First vertical workflow

`create_research_task(objective, symbols, start, end)` runs:

1. retrieve timestamped fixture market evidence and document evidence;
2. produce cited research from those records;
3. run a deterministic equal-weight buy-and-hold backtest;
4. create a paper order plan from the ending allocation;
5. apply a notional and symbol-count risk policy;
6. persist events and JSON artifacts;
7. return a complete run summary through CLI and HTTP.

Failure, cancellation, restart, and duplicate request behavior are explicit test seams.

### 6. Repository and package boundaries

- `market_os/contracts.py`: versioned domain contracts only.
- `market_os/store.py`: root-owned persistence; JSONL events and immutable JSON artifacts.
- `market_os/workflow.py`: application workflow and policy orchestration.
- `market_os/providers.py`: deterministic providers plus narrow adapter protocols.
- `market_os/api.py`: transport only; it calls the workflow and never owns trading rules.
- `market_os/cli.py`: terminal transport only; it calls the same workflow as the API.
- Child repositories remain independent. Vibe-Trading is the future research/backtest adapter; LightRAG/RAG-Anything are future evidence adapters; AI-Trader is the future paper broker and signal adapter.

### 7. Major risks and unknowns

- OpenHarness, nanobot, and DeepCode have overlapping runtime/state models; an integration benchmark is still needed.
- Child repositories have incompatible Python/dependency floors and provider configuration styles.
- Real market data freshness, corporate actions, and document licensing need a production policy.
- A deterministic fixture backtest proves reproducibility, not strategy quality or market realism.
- Persistent storage needs concurrency, retention, encryption, and multi-tenant isolation before deployment.
- Live execution needs separate credentials, reconciliation, kill switch, approval, and recovery gates.

### 8. Decisions requiring human input

1. Confirm the first user: individual researcher or small research team.
2. Confirm US equities/ETFs as the initial market scope.
3. Approve OpenHarness as orchestration owner, with adapters for nanobot and DeepCode.
4. Choose the production metadata/artifact store after the local JSONL proof.
5. Choose the first real market-data and document providers, including licensing and freshness requirements.
6. Approve the risk limits for paper trading and the later live-trading gate checklist.

## Exit evidence

The Phase 0 inventory is recorded in `docs/PROJECT-INDEX.md` and `docs/UNDERSTANDING-LOG.md`. The executable proof for this ADR is the root-owned paper workflow and its contract/integration tests.
