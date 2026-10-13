# ADR-0006: OpenHarness promotion decision after M1.8

- **Date:** 2026-10-14
- **Status:** Provisional
- **Decision:** OpenHarness remains provisional and is not promoted to the production orchestration owner.

## Evidence

M1.8 ran the shared paper-only workflow through the dependency-free reference
path and through OpenHarness 0.1.9 in an isolated environment with scripted,
no-network clients. The committed evidence is
[`docs/evidence/m1.8-openharness-recovery.json`](../evidence/m1.8-openharness-recovery.json).

The fusion repository now has deterministic terminalization for persistence
failures, cancellation checkpoints, abandoned-run cleanup, idempotent artifact
indexing, and the versioned `market-os.multi-agent.v1` aggregation contract.

## Decision basis

The promotion gate is not satisfied. Direct runtime evidence still shows no
runtime-native resume after cancellation or restart, no mid-turn checkpoint
guarantee, swallowed partial teammate exceptions, and no runtime-native
duplicate-result contract. Deployment and dependency requirements are now
documented but have not been proven in a deployed service/container.

## Consequences

- `MarketWorkflow`, `RunStore`, and the adapter recovery contract remain the
  safety reference.
- OpenHarness may continue to run behind the adapter for no-network probes.
- M2 cannot connect real providers, document services, brokers, or live
  execution.
- The next gate must exercise a deployed isolated runtime or explicitly reject
  the unsupported runtime behaviors with an alternate orchestration owner.
