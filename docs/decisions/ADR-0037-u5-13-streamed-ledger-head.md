# ADR-0037: Stream Ledger Head Validation

**Status:** Accepted locally  
**Date:** 2026-10-29

## Context

After U5.12, summary and other in-memory inspections still called
`_ledger_head()`, which decoded and split the entire JSONL file just to read the
last event fingerprint. The check must still detect invalid UTF-8 in earlier
records, as the previous full-file decode did.

## Decision

- Stream the file in bounded text chunks, validate UTF-8 across the whole
  ledger, and retain the current candidate line for JSON parsing. Drop only
  permitted leading JSON whitespace; preserve record contents across chunks
  so malformed JSON or a changed fingerprint cannot be hidden at a boundary.
  Whitespace-only physical lines use constant-size state until their boundary
  is known, then are discarded.
- Preserve the existing zero fingerprint for a missing or empty ledger and
  fail closed on unreadable or malformed records.
- Keep complete cold recovery and chain validation unchanged.

## Consequences

Freshness checks remain linear in ledger bytes, but no longer materialize the
full text or line list. Memory depends on the largest non-empty line rather
than total ledger size; the current format has no maximum line length. Interior
UTF-8 corruption and record contents remain detectable. Cold recovery and
resource-page scans remain linear. A durable cache or index still requires a
separate integrity and invalidation decision.
