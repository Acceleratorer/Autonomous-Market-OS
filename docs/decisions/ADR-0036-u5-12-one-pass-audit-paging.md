# ADR-0036: One-Pass Freshness Checks for Audit Pages

**Status:** Accepted locally  
**Date:** 2026-10-29

## Context

U5.11 bounded HTTP ledger and risk resources, but page inspection first read
the entire ledger to check its current head and then read it again to select
rows and validate cursors. Cold broker recovery had already validated the
append-only chain.

## Decision

- Keep complete cold ledger replay and existing hash-chain/checkpoint checks.
- While selecting risk, approval, or ledger page data, capture the last
  non-empty record's event fingerprint and compare it with the recovered head
  under the existing process lock.
- Return a stale-state conflict if the head changed. Do not cache recovery
  results or trust filesystem metadata.

## Consequences

Page inspection removes one full-file read and parse while preserving the
existing stale-head check. The page still scans the ledger once for totals,
cursor validation, and bounded selection; cold recovery still scans the full
ledger. Catalog indexing and recovery caches remain deferred until their
invalidation and integrity rules can be stated and tested.
