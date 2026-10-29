# ADR-0030: local portfolio inspection surface

**Date:** 2026-10-29  
**Status:** Accepted for local implementation

## Decision

Extend the existing plain HTML operator shell to consume the versioned B4
inspection resources for summary, genesis, reservations, orders, and risk.
Keep all accounting, authorization decisions, recovery, and audit semantics in
the Python domain package and expose no mutation route.

## Rationale

The shared portfolio and reservation contracts already exist and are tested,
but the web shell previously showed only a small balance summary. Reading the
same resources used by the CLI and API makes the browser useful for local
review without duplicating domain logic or adding a framework prematurely.

## Consequences

- Operators can inspect membership, reservations, order ownership, and risk
  outcomes from one local surface.
- The UI remains deterministic and paper-only because it renders persisted
  broker inspection results.
- Authentication, tenant isolation, deployment, and mutation remain separate
  versioned gates.
