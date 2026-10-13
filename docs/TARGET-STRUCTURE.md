# Target Repository Structure

```text
market-os/
  apps/
    gateway/                 # Authenticated HTTP/WebSocket API
    cli/                     # Terminal client
    web/                     # Browser operator console
    desktop/                 # Desktop shell
    mobile/                  # Mobile shell
  packages/
    contracts/               # Versioned Pydantic/OpenAPI/domain schemas
    orchestration/           # Tasks, agents, runs, approvals, cancellation
    events/                  # Event bus, tracing, audit records
    knowledge/               # LightRAG/RAG-Anything adapters
    market/                  # Instruments, prices, calendars, provenance
    research/                # Research plans, evidence, citations
    backtest/                # Reproducible strategy evaluation
    portfolio/               # Positions, cash, accounting, performance
    risk/                    # Limits, checks, risk decisions, kill switch
    execution/               # Paper broker and later live broker adapters
    tools/                   # CLI-Anything and other typed tool adapters
    evaluation/              # ClawWork metrics and benchmark scenarios
    artifacts/               # Reports, slides, media, lineage, storage
    education/               # DeepTutor explanations and coaching
  plugins/
    providers/               # LLM, embeddings, market data, broker providers
    strategies/              # Versioned strategies and experiment definitions
    media/                   # Paper2Slides and ViMax workflows
  infra/
    compose/                 # Local and deployment environments
    migrations/              # Database migrations
    observability/           # Logs, metrics, traces, alerts
  tests/
    contract/
    integration/
    e2e/
    benchmarks/
  docs/
    decisions/
    api/
    operations/
```

## Structural rules

- Domain packages contain business rules; apps contain presentation and transport.
- Providers are adapters and cannot define core domain schemas.
- Every long-running action emits `RunEvent` records.
- Every artifact carries task/run lineage and access policy.
- Live execution is a plugin behind the same interface as paper execution.
- Generated tools run with explicit permissions and resource limits.
- Shared code moves only after an adapter proves its contract.
