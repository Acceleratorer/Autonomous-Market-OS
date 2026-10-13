# ADR-0005: OpenHarness promotion decision

- **Date:** 2026-10-13
- **Status:** Provisional
- **Decision:** OpenHarness remains provisional and is not promoted to the production orchestration owner.

## Evidence

M1.7 ran the same paper-only Market OS workflow in an isolated OpenHarness
interpreter with scripted no-network clients. Runtime evidence covers failure
normalization, cancellation before and during provider/tool work, session
persistence failure, idempotent replay, duplicate request handling, artifact
lineage, event trace persistence, terminal status, paper-only rejection, and
basic two-agent identity/run coordination.

The machine-readable probe report is committed at
[`docs/evidence/m1.7-openharness-recovery.json`](../evidence/m1.7-openharness-recovery.json).
It includes one record per scenario with runtime
version, environment ID, timestamps, expected and observed behavior, event
trace, artifacts, error details, recovery result, pass/fail, and
`runtime_verified`.

## Blockers

Promotion criteria are not met because:

- artifact persistence is synchronous and cannot be cooperatively cancelled;
- a Market OS event persistence failure leaves the run `running` instead of
  producing a normalized terminal failure;
- cancelled in-flight work cannot be resumed or inspected as a runtime-native
  task after restart;
- restart during a running task has no guaranteed mid-turn snapshot;
- partial teammate failure is swallowed rather than aggregated;
- duplicate teammate results have no idempotency contract;
- final multi-agent aggregation and shared artifact/failure semantics are not
  defined or runtime-verified;
- deployment and dependency requirements remain unreviewed in a deployment
  environment.

These are exact blockers from the direct probe, not inferred from fixture
parity. No real market providers, live brokers, or live execution were used.

## Consequences

- `MarketWorkflow` and `RunStore` remain the reference implementation.
- OpenHarness remains available behind the adapter for further recovery work.
- M2 is blocked from real providers until a later decision closes the recovery
  and deployment gaps.
- Paper-only enforcement remains mandatory.

## Next decision gate

Add durable task checkpoints and normalized multi-agent aggregation at the
adapter boundary, rerun the isolated probes, and complete deployment/dependency
review. Only then reconsider an `Accepted` decision.
