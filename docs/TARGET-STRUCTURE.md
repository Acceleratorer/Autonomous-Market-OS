# Autonomous Market OS: Target Structure

The fusion repository is the product. The repositories under
`D:\Code\Github\company-projects` are source projects and remain independent.
Do not merge their histories or copy their entire trees into this repository.
Integrate them through narrow adapters and versioned contracts.

## Current repository shape

```text
Autonomous-Market-OS/
  market_os/                 # root-owned contracts, workflows, storage, CLI/API
  scripts/                   # bounded probes, evidence, and maintenance tools
  docs/                      # roadmap, ADRs, reports, evidence, operations
  .github/workflows/         # offline CI and security checks
  pyproject.toml             # root package and test configuration
```

## Staged target shape

```text
Autonomous-Market-OS/
  apps/
    gateway/                 # HTTP/WebSocket transport over root services
    cli/                     # CLI entry points; domain logic stays in packages
    web/                     # browser operator console
    desktop/                 # thin desktop shell
    mobile/                  # thin mobile shell
  market_os/
    contracts/               # versioned domain and API contracts
    orchestration/           # tasks, runs, approvals, cancellation, recovery
    events/                  # event and audit persistence
    knowledge/               # LightRAG/RAG-Anything adapters
    market/                  # instruments, candles, provenance, datasets
    research/                # documents, citations, claims, summaries
    backtest/                # reproducible numerical evaluation
    features/                # deterministic feature/label materialization
    models/                  # statistical baselines and optional providers
    evaluation/              # splits, calibration, metrics, benchmarks
    portfolio/               # virtual wallet, ledger, accounting, performance
    risk/                    # limits, decisions, kill switch, no-trade policy
    execution/               # paper broker; live boundary remains disabled
    artifacts/               # content addressing, lineage, reports
    providers/               # narrow external adapters and disabled transports
  plugins/
    strategies/              # versioned experiment configurations
    tools/                   # typed CLI-Anything integrations
    media/                   # Paper2Slides and ViMax artifact workflows
    education/               # DeepTutor workflows over shared evidence
  infra/
    compose/                 # local and deployment shape
    observability/            # logs, metrics, traces, alerts
  tests/
    contract/
    integration/
    e2e/
    benchmarks/
  docs/
    decisions/
    api/
    operations/
    evidence/
```

## Ownership rules

- `market_os` owns domain truth, safety, state transitions, persistence, and replay.
- `apps` own transport and presentation only.
- `providers` and `plugins` adapt external projects; they cannot define core schemas.
- The web, CLI, desktop, and mobile surfaces call the same API/contracts.
- Every long-running action emits events and produces inspectable artifacts.
- Every artifact records task/run lineage, content identity, provenance, and access policy.
- The paper broker is the only execution implementation in the normal roadmap.
- A live broker, if ever considered, must be isolated behind a new decision record and separate approval.

## Integration order

1. Audit a source project and its entry points.
2. Define the root contract and fixture.
3. Implement the narrowest adapter.
4. Verify parity, replay, lineage, and failure behavior.
5. Promote the adapter only when its evidence passes.
6. Reuse the capability through the shared API and CLI.

Do not create a package merely because the target tree contains a directory name. Add a module when a real workflow needs it.
