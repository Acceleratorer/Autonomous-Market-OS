# ADR-0010: Final orchestration owner

- **Date:** 2026-10-14
- **Status:** Accepted
- **Decision:** **Accepted — Market OS owns orchestration; OpenHarness is optional**

## Context

M1.5 through M1.11 tested the dependency-free Market OS workflow, the
OpenHarness 0.1.9 runtime in isolation, the adapter recovery behavior, and the
local deployment wrapper. The evidence closes the safety behaviors at the
Market OS seam, but does not establish native OpenHarness guarantees for
synchronous persistence cancellation, checkpoint/resume, teammate failure or
cancellation propagation, duplicate results, provider execution deadlines,
process quotas, or service identity and filesystem permissions.

The fusion package does not require OpenHarness to run its paper-only workflow.
Keeping two possible production owners would leave event, persistence, and
recovery semantics ambiguous.

## Ownership

| Responsibility | Single owner | Rule |
|---|---|---|
| Production orchestration | `MarketWorkflow` in Market OS | All production runs enter through the root workflow. |
| Safety policies | Market OS contracts and workflow | Paper-only mode, risk checks, cancellation checkpoints, and live-execution rejection stay root-owned. |
| Adapter responsibility | `OpenHarnessAdapter` when enabled | Map optional runtime sessions and events to Market OS contracts; never replace root policy or persistence. |
| Event ownership | Market OS `RunEvent` and `RunStore` | Runtime events are translated and persisted as root events. |
| Persistence | Market OS `RunStore` | Run, event, artifact, idempotency, and recovery records are authoritative here. |
| Cancellation | Market OS workflow | The root workflow decides terminal cancellation and records partial state. |
| Restart/recovery | Market OS startup recovery | Abandoned work is terminalized as `resume_unsupported`; no runtime claims are inferred. |
| Multi-agent aggregation | Market OS aggregation contract | `AgentAggregate` owns ordering, duplicates, conflicts, partial status, and lineage. |
| Deployment boundary | Market OS service and bounded wrapper | Loopback, paper-only, paths, lifecycle, request limits, and logs are enforced at the root deployment seam. |

OpenHarness is therefore an **optional agent/runtime adapter** for local,
no-network, paper-only capabilities such as tools, skills, memory, and
multi-agent sessions. It is not the production orchestration owner.

## Options considered

| Option | Result | Reason |
|---|---|---|
| A — OpenHarness owns orchestration | Rejected | Native gaps leave safety, cancellation, persistence, and restart ownership unclear; deployment controls are external and unproven. |
| B — Market OS owns orchestration | **Accepted** | One dependency-free owner already exercises the required safety semantics and can use OpenHarness without depending on it. |
| C — Reject OpenHarness integration | Not selected | The adapter remains useful for optional local agent capabilities, and historical runtime evidence is still valuable. |

Option B is the smallest architecture that gives every safety-critical
behavior one owner and lets M2 begin with deterministic fixtures.

## Migration consequences

- `MarketWorkflow` remains the production reference path and is the only path
  allowed to create paper runs and terminal states.
- OpenHarness imports remain optional and outside the core contract modules.
- Existing OpenHarness probes, ADRs, and evidence stay as historical records;
  they are not erased or reclassified as native guarantees.
- M2 adapters must return Market OS contracts and cannot persist directly into
  OpenHarness storage or introduce credentials.
- Deployment may run without OpenHarness. Enabling it is an explicit adapter
  choice inside the same root-owned safety and persistence boundary.

## Supersession

ADR-0010 supersedes the ownership or promotion direction in ADR-0002 and the
provisional promotion decisions in ADR-0004, ADR-0005, ADR-0006, ADR-0007,
ADR-0008, and ADR-0009. Those documents remain authoritative historical
evidence for what was proposed or tested. ADR-0003 is reaffirmed where it
places OpenHarness behind a narrow adapter and keeps Market OS as the
reference path.

## Revisit conditions

Revisit this decision only after a separately approved milestone supplies
repeatable evidence for all of the following in the intended deployment
shape: native persistence cancellation, durable checkpoint/resume, teammate
failure and cancellation propagation, duplicate-result handling, provider and
workflow deadlines, process quotas, service identity and filesystem ACLs,
upgrade/rollback behavior, and parity with the root safety contracts. A new
runtime must also reduce operational complexity without creating a second
owner for safety-critical state.
