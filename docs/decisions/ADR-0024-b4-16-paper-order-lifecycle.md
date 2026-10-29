# ADR-0024: B4.16 paper order lifecycle

**Date:** 2026-10-28  
**Status:** Accepted for local implementation  
**Scope:** Synthetic, paper-only, local Python broker

## Decision

Retain the owner-approved full-fill, accepted-order FIFO, no-expiry lifecycle. Treat synthetic event volume as informational because the existing venue contract does not define it as executable liquidity. Preserve current market/limit triggers, idempotent cancellation, derived reservation release on terminal states, and whole-event rollback on failure.

## Rationale

Partial fills would require new durable semantics for liquidity allocation, residual quantities, fees, minimum notional, reservation accounting, cancellation, expiry, and replay compatibility. Adding those rules from the existing `volume` field would silently invent behavior and change the approved B4 boundary.

## Consequences

The local model stays deterministic and compatible with existing B4 fingerprints. Open unmatched limits retain reservations until a terminal transition. A future partial-fill or expiry implementation must use a new versioned contract and evidence set.
