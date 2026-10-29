# ADR-0027: web stack selection gate

**Date:** 2026-10-28  
**Status:** Accepted for the current local phase; framework selection deferred

## Decision

Keep `apps/web/public` as the active static source while the product surface is
read-only and disconnected from portfolio state. Do not add a JavaScript
framework or package manager speculatively.

Use this promotion rule:

1. Choose Astro if the next approved workflow remains static-first and needs
   componentized pages with minimal client JavaScript.
2. Choose React/Next only when an approved workflow needs authenticated,
   interactive application state and the service/API boundary is versioned for
   that use.
3. Keep the current plain HTML source when it remains the smallest surface that
   satisfies the approved contract.

## Rationale

The current U5.2 gate proves deterministic static packaging, exact file parity,
no scripts, no network calls, no credentials, and no mutation controls. Adding
a framework now would increase dependencies and deployment surface without a
real consumer requirement. The decision can be revisited without moving domain
logic out of `market_os`.

## Consequences

- Static artifact packaging remains the first deployable web milestone.
- A future framework must live under `apps/web` and consume versioned contracts.
- Framework code cannot own portfolio accounting, risk, persistence, or order
  mutation.
- Public deployment and authenticated access remain separate approvals.
