# ADR-0025: B4.17 local retention and archive

**Date:** 2026-10-28  
**Status:** Accepted for local implementation  
**Scope:** Synthetic, paper-only, local portfolio store

## Decision

Keep complete portfolio history indefinitely. Treat the existing validated ZIP backup as a non-destructive archive copy and keep migration preflight read-only. Fail closed when a checkpoint survives without its ledger. Defer pruning, deletion, remote archive, and schema transformation until each has a separate versioned contract and authorization boundary.

## Rationale

The append-only ledger is the audit and replay source of truth. Deleting or transforming it now would weaken deterministic recovery and invent an unapproved target schema. The checkpoint-without-ledger case is unambiguously incomplete and must not be blessed as a fresh portfolio.

## Consequences

Local storage grows without automatic deletion. Operators can make validated local copies, but source bytes remain unchanged. A future archive/delete operation must prove backup, restore, fingerprint, and audit equivalence before mutation.
