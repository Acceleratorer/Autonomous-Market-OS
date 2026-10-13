# ADR-0004: Runtime-verified OpenHarness boundary

- **Date:** 2026-10-13
- **Status:** Provisional; runtime evidence exists but promotion criteria are incomplete
- **Scope:** M1.6 isolated OpenHarness integration

## Decision

Run OpenHarness only through an isolated interpreter selected explicitly by the
operator. Keep `MarketWorkflow` and `RunStore` as the reference domain path,
and keep OpenHarness imports inside `market_os/orchestration/openharness_probe.py`
and the adapter boundary.

## Evidence

The real OpenHarness runtime successfully built and closed a session, loaded an
extra skill, invoked a registered Market OS workflow tool, persisted a session
snapshot, reloaded it by ID, and replayed an idempotent task. The same task's
research, backtest, paper order plan, risk decision, artifacts, citations,
lineage, event order, timestamps, and contract serialization matched the
dependency-free reference path.

## Non-decisions

This milestone does not promote OpenHarness, connect a real provider, or enable
live execution. Runtime-native failure, cancellation, and multi-agent behavior
remain unsupported until directly tested.

## Consequences

- The fusion package stays dependency-light and runnable without OpenHarness.
- Runtime verification requires a separately provisioned environment.
- Child session IDs and event names require explicit translation into
  `market-os.v1` records.
- Any future promotion must include direct recovery evidence and deployment
  review, not source-based inference.
