# ADR-0009: OpenHarness promotion readiness after M1.11

- **Date:** 2026-10-14
- **Status:** Provisional
- **Decision:** Keep OpenHarness provisional; accept only the tested Market OS adapter and local paper-only deployment boundary.

## Evidence

M1.11 records a 14-entry blocker matrix and refreshed isolated evidence in
[`docs/evidence/m1.11-openharness-blockers.json`](../evidence/m1.11-openharness-blockers.json).
The OpenHarness 0.1.9 runtime was exercised without providers, credentials,
brokers, or network access. The deployment probe now includes a direct stalled
HTTP-body timeout check and structured service-log validation.

## Accepted boundary guarantees

- Market OS terminalizes persistence failures and cancellation safely.
- Startup recovery marks abandoned work failed and inspectable.
- Adapter aggregation preserves partial failures and artifact lineage.
- Adapter fingerprints classify duplicates and conflicts.
- The local wrapper enforces loopback, paper-only mode, explicit paths, and
  bounded lifecycle shutdown.
- The service bounds HTTP request-body reads and emits structured JSONL request
  outcomes.

## Promotion blockers

- OpenHarness persistence is synchronous and lacks native cancellation.
- OpenHarness has no durable in-flight checkpoint/resume path.
- Teammate failure and cancellation outcomes are not propagated natively.
- Native duplicate-result handling is absent.
- Provider/workflow execution deadlines are not established by the service.
- CPU and memory quotas require an external supervisor.
- Production service identity and filesystem ACLs are not configured or proven.

## Consequences

OpenHarness may remain behind the adapter for local, no-network, paper-only
workflows. M2 real-provider implementation is deferred until the blockers have
explicit owners and a supported closure path. No live execution is enabled.
