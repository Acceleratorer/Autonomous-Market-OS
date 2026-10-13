# Deployment and dependency review

**Review date:** 2026-10-14
**Result:** the M1.9 launched-service probe verifies the local deployment shape,
but deployment controls remain incomplete, so OpenHarness remains provisional.

The executable evidence is recorded in
[`docs/evidence/m1.9-deployment-validation.json`](evidence/m1.9-deployment-validation.json)
and the reproduction steps are in
[`docs/M1.9-DEPLOYMENT-VALIDATION.md`](M1.9-DEPLOYMENT-VALIDATION.md).

## Runtime and dependencies

- Fusion package: Python 3.11 or newer, dependency-free reference workflow.
- OpenHarness probe: `openharness-ai:0.1.9` in the isolated interpreter at
  `C:\Temp\autonomous-market-os-openharness-venv`.
- OpenHarness is optional and is not a fusion package dependency. Install it in
  a separate virtual environment from the child repository metadata.
- Required runtime dependencies belong to the selected OpenHarness environment;
  optional UI, channel, MCP, provider, and model integrations stay out of the
  recovery probe.

## Configuration and secrets

The probe passes temporary `OPENHARNESS_CONFIG_DIR`, `OPENHARNESS_DATA_DIR`,
`OPENHARNESS_LOGS_DIR`, and `OHMO_WORKSPACE` directories. No credentials are
stored in the repository or accepted by the no-network probe. Production
secrets must come from the service secret provider and must never enter task,
event, artifact, or log payloads.

## Filesystem and storage

The reference store uses a private directory containing JSONL run/event,
recovery, idempotency, and artifact indexes plus immutable JSON artifacts.
Production deployment must use a private service account, restrictive
directory permissions, atomic snapshot/index replacement, backups, and a
retention policy. `recovery.jsonl` preserves failed-write metadata and partial
artifact state for inspection.

## Process recovery and limits

On startup, `MarketWorkflow.recover_inflight_runs()` marks abandoned `running`
runs failed with `restart_interrupted:resume_unsupported`. It does not resume
provider or backtest work. Deployments must add bounded task, provider, tool,
and shutdown timeouts, memory/CPU limits, and an explicit queue/concurrency
limit before accepting external workloads.

## Network and logging policy

The recovery probe is local and no-network. A deployed runtime needs an
allow-list for provider/document endpoints, egress denial by default, request
timeouts, and audit logging for provider/tool calls. Retain terminal events,
recovery records, artifact lineage, and security-relevant errors for the
configured operational retention period; redact secrets and personal data.

## Multi-user isolation

The current reference slice is single-user. A service deployment must add
authenticated tenant/user identity, per-tenant storage roots or database
partitions, artifact access checks, and concurrency isolation before sharing a
runtime between users.

## Service/container deployment

The reproducible shape is a pinned Python base image, a separate pinned
OpenHarness environment or image, read-only application code, writable private
state volumes, non-root execution, health/readiness checks, and a worker
shutdown grace period. No live broker or execution process is part of this
milestone.

## Upgrade and rollback

Pin the fusion and OpenHarness versions independently. Upgrade in a disposable
environment, rerun the parity and recovery probes, inspect the evidence JSON,
and promote only after review. Roll back by restoring the previous image and
state volume snapshot; never rewrite event or artifact history.

## Open deployment gaps

The M1.9 service probe now proves local startup, readiness, health, paper task
execution, audit persistence, startup recovery, clean restart, forced shutdown,
filesystem state isolation, and the no-secret fixture boundary. Resource
limits, request/shutdown timeouts, structured logs, production service-account
permissions, and image-based upgrade/rollback remain unproven or unsupported.
Those gaps remain promotion blockers.

M1.10 adds a bounded local wrapper that owns loopback startup, paper-only
configuration, lifecycle timeouts, graceful/forced termination, exit status,
and wrapper JSONL logs. It explicitly rejects CPU/memory limits without an
external supervisor. The wrapper is suitable for local paper-only probes; it is
not a production host isolation layer.
