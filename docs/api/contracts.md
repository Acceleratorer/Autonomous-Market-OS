# `market-os.v1` Contracts

The contract module is the boundary between applications, orchestration, storage, and provider adapters. It uses standard-library dataclasses so adapters do not inherit each other's dependency graphs.

## Rules

- Every contract carries `api_version: "market-os.v1"` where it crosses a durable or remote boundary.
- IDs are stable ASCII identifiers no longer than 128 characters.
- Dates are calendar dates in `YYYY-MM-DD`; timestamps are ISO-8601 strings.
- A `Task` is paper-only in v1. Any other `execution_mode` is rejected at construction.
- An idempotency key is optional for local calls and required by retrying remote clients.
- A `Run` is terminal only with `completed`, `failed`, `cancelled`, or `rejected`; failed and rejected runs include an error.
- `RunEvent` carries actor, tool/model, input/output references, cost, error, and provenance fields even when a provider does not populate all of them yet.
- `Artifact` stores immutable content metadata, SHA-256, lineage, and access policy.
- Provider-specific payloads stay behind adapters; core contracts use
  `MarketObject`, `KnowledgeDocument`, `Evidence`, and the dependency-free
  provider seam types in `market_os.providers`.

## Example task

```json
{
  "task_id": "task-example-1",
  "objective": "Compare diversified low-risk candidates",
  "symbols": ["SPY", "QQQ"],
  "start": "2026-01-02",
  "end": "2026-01-06",
  "created_at": "2026-10-13T00:00:00+00:00",
  "execution_mode": "paper",
  "idempotency_key": "research-2026-01-02-1",
  "api_version": "market-os.v1"
}
```

Adapters should call `task_from_dict` and `order_plan_from_dict` at the transport boundary. Contract failures expose a stable `code`, human-readable `message`, and optional `field` through `error_response`.

## Deferred fields

Authentication, tenant isolation, and persistent approval storage remain
deferred. Normalized provider seam types are now defined; concrete network
providers remain deferred until an adapter passes the M2 contract and
operational gates. See [ADR-0010](../decisions/ADR-0010-final-orchestration-owner.md).

## Explicit provider selection

The CLI `research` command accepts `--provider fixture|vibe-trading` and an
optional `--backtest-provider`. The service `POST /v1/tasks` accepts matching
`provider` and `backtest_provider` fields. Omitted fields preserve the fixture
default. Optional provider failures are returned as errors; adapters do not
silently substitute another backtest engine.

For M2.2, `--provider lightrag --backtest-provider vibe-trading` selects the
document retrieval adapter and preserves the existing backtest adapter. The
result includes normalized `documents` and `retrieval` records; their artifact
lineage is rooted in the Market OS store.

`retrieval` carries `query`, document IDs, cited passage IDs/excerpts, provider
identity/version, retrieval time, query/content fingerprints, and partial/error
metadata. Root research citations include the same adapter citation references
alongside any market-evidence citations in the combined workflow.

The cited synthesis is available in the versioned `cited-research` artifact;
inspection endpoints are read-only and validate hashes and artifact lineage.
