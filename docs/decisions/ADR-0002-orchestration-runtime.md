# ADR-0002: Provisional orchestration runtime

- **Date:** 2026-10-13
- **Status:** Proposed; requires human confirmation before a production adapter is accepted
- **Scope:** `market-os.v1` orchestration boundary

## Decision

Adopt **OpenHarness as the provisional orchestration owner** for the Autonomous Market OS. Integrate it through a narrow adapter that speaks the root-owned `market-os.v1` contracts. Keep nanobot and DeepCode as independent adapters or reference implementations until fixture-parity and recovery checks pass.

## Why OpenHarness

Source inspection found the best first-slice coverage across tools, skills, memory, multi-agent coordination, CLI entry points, and a gateway/service surface. Its existing runtime, session storage, memory, bridge, and in-process swarm paths give the fusion a broad orchestration seam without moving domain logic into the child repository.

DeepCode has the strongest explicit durable event, SQLite persistence, checkpoint, cancellation, and recovery model, but its architecture is larger and primarily shaped around coding-agent workflows. Nanobot is the lightest path to channels and personal-assistant behavior, but it has a weaker explicit durable orchestration and audit model for the first trading workflow.

The evidence is source-based. No direct child-runtime execution was performed in this milestone.

## Adapter responsibilities

The OpenHarness adapter must:

1. map a Market OS `Task` to an isolated runtime task/session;
2. pass only approved tools, skills, memory scope, and paper permissions;
3. translate runtime lifecycle/tool/model events into `RunEvent` records;
4. persist and replay `Run`, `Artifact`, and idempotency state through the root-owned store;
5. expose cancellation and restart inspection at the Market OS boundary;
6. keep OpenHarness types and provider configuration out of `market_os/contracts.py`;
7. reject any request that attempts live execution before the live safety gates are approved.

## Migration plan

1. Keep the current dependency-free workflow as the contract reference implementation.
2. Add one OpenHarness adapter behind a protocol; do not copy its repository into the fusion package.
3. Run the same valid/invalid fixtures through both paths.
4. Compare event kinds, artifact lineage, cancellation, restart inspection, idempotency, and paper-only behavior.
5. Connect real retrieval and market providers only after adapter parity is demonstrated.
6. Revisit nanobot and DeepCode after the first adapter's operational evidence exists.

## Risks

- OpenHarness's dependency and provider configuration surface may be too large for a small deployment.
- Runtime events may not map one-to-one to the root event contract without losing provenance.
- Session recovery and cancellation may be weaker under provider failure than the source layout suggests.
- A runtime selection does not validate research quality, backtest correctness, or trading safety.

## Human decisions still required

- Confirm OpenHarness as the production orchestration owner.
- Approve the adapter's process and permission isolation model.
- Choose production metadata/artifact storage and retention policy.
- Approve the first real market-data and document providers.
- Approve paper risk limits and the later live-trading gate checklist.
