# ADR-0003: OpenHarness adapter parity boundary

- **Date:** 2026-10-13
- **Status:** Implemented as a fixture/runtime-double harness; OpenHarness remains provisional
- **Scope:** M1.5 orchestration adapter parity

## Decision

Keep the dependency-free `MarketWorkflow` as the reference path and place OpenHarness behind `market_os.orchestration.protocol.OrchestrationAdapter`. The first adapter uses an OpenHarness-shaped fixture runtime so parity can be exercised without importing the child repository or installing its dependency graph.

## Boundary

The adapter owns:

- mapping task creation into the existing Market OS task contract;
- translating session/tool lifecycle events into validated `RunEvent` records;
- delegating domain work to the existing workflow and providers;
- preserving the root store's run, artifact, lineage, and idempotency behavior;
- exposing restart inspection and cooperative cancellation through the same protocol;
- retaining `runtime_verified=false` until the actual OpenHarness runtime is executed.

OpenHarness-specific event objects and runtime details stay in `openharness_adapter.py`. Contracts, providers, and the reference workflow do not depend on OpenHarness types.

## Parity evidence

The harness compares task/result behavior, event order and UTC timestamps, completion/failure, cancellation, restart inspection, idempotency, content-addressed artifacts, lineage, evidence/citations, risk decisions, paper-only enforcement, error normalization, contract serialization, and shared CLI/API result shape.

The fixture path currently has no mismatches. Event names require translation, and actual OpenHarness execution is explicitly unsupported/unverified in this environment.

## Rejected approaches

- **Hard dependency on OpenHarness:** rejected for M1.5 because its provider/UI/channel dependency graph is not required to verify the root contract and would make the harness non-runnable in the current environment.
- **Copying OpenHarness into the fusion package:** rejected because it breaks repository ownership and hides the adapter boundary.
- **Replacing `MarketWorkflow`:** rejected because the dependency-free workflow is the current behavior reference and must remain functional.

## Risks and promotion gate

The fixture runtime cannot prove actual OpenHarness event timing, cancellation propagation, session resume, or deployment behavior. Runtime promotion requires isolated execution of the real child runtime against the same fixtures, with no mismatches or unsupported safety behavior. Live trading remains disabled regardless of runtime selection.
