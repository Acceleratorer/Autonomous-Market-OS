# ADR-0033: Bounded Local Portfolio Inspection

**Status:** Accepted locally  
**Date:** 2026-10-29

## Context

The U5.8 Next.js route fetched the complete order and risk history. Its risk
consumer then sliced the response to eight rows, which limited display but not
response size. The compatibility HTML shell also made separate requests for
each detail resource.

## Decision

Use one versioned GET aggregate, `market-os.b4-portfolio-inspection@v1`, for the
two local browser surfaces. Keep summary data compact, page orders and risk
outcomes with independent exclusive cursors, cap requested page sizes at 100,
and project risk rows to stable audit fields. Preserve legacy detail routes for
local clients during migration.

Python remains authoritative for recovery, identity, portfolio state, order
selection, and risk classification. The web surfaces only display returned
values. No domain behavior moves into TypeScript or browser code.

## Consequences

- Each browser page has bounded order and risk response lists and can browse
  older records without loading the full histories.
- The compatibility shell and Next.js UI use the same endpoint and cursor
  semantics.
- Broker recovery and risk-page selection still scan the ledger. Genesis
  membership and reservation rows remain complete, cardinality-dependent views.
- The legacy full-history `/risk` route remains local-only until an explicit
  compatibility/deprecation step.
- U5.5 deployment and identity decisions remain required before shared access.

## Rejected alternatives

- Slicing the full response in the UI: this hides rows but does not bound
  network or memory use.
- Removing the old endpoints immediately: that would break the existing
  versioned local inspection contract.
- Moving risk classification into Next.js: that would duplicate B4 ownership
  and make client behavior dependent on ledger internals.
