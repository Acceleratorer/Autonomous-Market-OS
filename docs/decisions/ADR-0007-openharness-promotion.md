# ADR-0007: OpenHarness promotion decision after M1.9

- **Date:** 2026-10-14
- **Status:** Provisional
- **Decision:** OpenHarness remains provisional and is not promoted to the production orchestration owner.

## Evidence

M1.9 exercised the dependency-free service as a launched local process and ran
the actual OpenHarness 0.1.9 recovery probe in its isolated Python 3.12.0
environment. The combined report is
[`docs/evidence/m1.9-deployment-validation.json`](../evidence/m1.9-deployment-validation.json).

The service probe passed startup, readiness, health, paper task execution,
event/artifact inspection, startup recovery, clean restart, forced shutdown,
filesystem state isolation, and the no-secret fixture boundary. The OpenHarness
probe passed the supported runtime failure, cancellation, replay, artifact
lineage, terminal status, paper-only, and coordination cases.

## Remaining blockers

- synchronous artifact persistence is not runtime-native cancellable;
- in-flight cancellation and restart have no durable checkpoint or resume;
- partial teammate exceptions are swallowed;
- native duplicate teammate handling is absent;
- the service has no process CPU/memory limits;
- request and shutdown timeout policy is not configured;
- structured operational logging is not configured;
- production service-account filesystem permissions are not proven;
- upgrade and rollback are documented assumptions rather than deployed-image evidence.

These are observed probe results. The adapter-level terminalization,
inspection, aggregation, and deduplication contract remains the safety boundary;
it is not counted as native OpenHarness support.

## Consequences

- `MarketWorkflow`, `RunStore`, and the adapter recovery contract remain the reference implementation.
- OpenHarness may continue behind the adapter for local, no-network probes.
- M2 stays blocked from real providers, brokers, credentials, and live trading.
- The next gate must close the deployment controls and obtain direct runtime evidence for checkpoint/resume, partial failure propagation, and duplicates, or explicitly reject this runtime/deployment shape.
