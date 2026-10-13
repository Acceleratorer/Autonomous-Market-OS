# ADR-0008: OpenHarness promotion decision after M1.10

- **Date:** 2026-10-14
- **Status:** Provisional
- **Decision:** Keep OpenHarness provisional; accept the bounded wrapper only for local paper-only deployment.

## Wrapper decision

The stdlib-only `BoundedService` wrapper is accepted for the local deployment
shape. It fails closed on unsafe paths, non-loopback hosts, live mode, missing
configuration, and unsupported host CPU/memory limits. It enforces lifecycle
timeouts, graceful/forced shutdown, exit normalization, startup recovery, and
structured wrapper logs.

## Evidence

M1.10 ran 48 named recovery, restart, teammate, duplicate, service, and wrapper
scenarios. The machine-readable report is
[`docs/evidence/m1.10-openharness-blockers.json`](../evidence/m1.10-openharness-blockers.json).

The isolated OpenHarness 0.1.9 runtime still lacks native guarantees for
cancellation during synchronous artifact persistence, checkpoint/resume across
restarts, teammate failure and cancellation propagation, and duplicate-result
and duplicate-artifact handling.

The Market OS adapter handles these cases with terminal recovery, inspect-only
restart behavior, ordered partial aggregation, fingerprints, duplicate
suppression, and same-agent conflict records. Adapter behavior is separate from
runtime evidence.

## Consequences

- `MarketWorkflow`, `RunStore`, and the adapter remain the safety reference.
- OpenHarness remains allowed only behind the adapter for local no-network probes and paper-only workflows.
- M2 remains blocked from real providers, brokers, credentials, and live execution.
- M1.11 must add a supported external supervisor or reject the deployment shape and obtain direct native evidence before promotion.
