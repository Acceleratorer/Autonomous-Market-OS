# ADR-0023: B4.15 shared portfolio concurrency

**Date:** 2026-10-28  
**Status:** Accepted for local implementation  
**Scope:** Synthetic, paper-only, local Python broker

## Decision

Represent a shared portfolio with an immutable, versioned genesis containing a stable shared identifier and sorted member strategy IDs. Keep one portfolio-wide local thread/process lock and one append-only ledger. Attribute orders, reservations, and ownership checks to strategy IDs while preserving the existing ledger/event/snapshot schemas for legacy isolated portfolios.

Use first committed ledger sequence as the deterministic serialization order. Reject stale in-memory writers before idempotency lookup and require reload before retry. Keep idempotency scoped to portfolio and command kind; identical retries replay, conflicts append a keyless audit event. Derive reservations from open orders, expose them through read-only inspection, and validate aggregate cash/inventory bounds during recovery.

Permit a verified checkpoint to lag the ledger and report `stale_or_missing`; never repair or rewrite the append-only history. Recovery remains snapshot restoration with fingerprint and invariant validation, not independent semantic event reduction.

## Rationale

This is the smallest change that provides shared membership and cross-strategy reservation safety using the existing broker seam. It avoids a second mutation API, distributed coordination, new dependencies, or a parallel ledger format. Lock acquisition is sufficient for the local synthetic boundary; fairness and network ownership require a separate contract.

## Consequences

Shared strategies contend for one wallet and one inventory pool. A stale writer must reload. Reservation ownership is inspectable and released by terminal order state. Legacy B4.1 histories remain readable. Partial fills, expiry, retention, migration transformation, and authenticated external mutation remain open.
