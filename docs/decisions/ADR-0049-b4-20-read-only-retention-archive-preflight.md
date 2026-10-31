# ADR-0049: B4.20 read-only retention and archive preflight

**Date:** 2026-10-30
**Status:** Accepted for local implementation
**Scope:** Synthetic, paper-only, local portfolio storage

## Decision

Add a read-only Python preflight for one portfolio and an optional backup ZIP.
Keep B4.17's indefinite source-ledger retention policy. The preflight reports
recovery, ledger/checkpoint fingerprints, shared reservations, zero-event
ambiguity, and archive validation. It always reports deletion as ineligible.

## Rationale

Deletion is not needed to make the existing backup workflow safer to inspect,
and the project has not chosen age-based eligibility, active-order guards,
archive retention, or authorization for deletion. A read-only report reuses
the broker's existing recovery authority and lets an operator verify backup
state without inventing a destructive policy. The on-disk format also cannot
distinguish an empty new store from deleted zero-event history, so that case
must remain explicitly ambiguous.

## Consequences

- Source history stays append-only and retained indefinitely.
- The archive is streamed and validated without extraction; reports contain
  no raw paths or portfolio file contents. Symlink/reparse aliases, oversized
  archives, descriptor/path replacement, and concurrent archive changes fail
  closed. Backup publication uses no-overwrite atomic linking.
- Shared membership and open reservations are visible but never authorize
  deletion.
- Any future retention mutation needs its own versioned policy, authorization,
  audit, and recovery contract.

## Alternatives considered

- **Add archive deletion now:** rejected because eligibility, authorization,
  and crash-recovery semantics have no approved policy.
- **Change to age-based retention:** rejected because it changes the owner's
  accepted indefinite-retention decision.
- **Reuse broker inspection alone:** rejected because the existing resources
  do not jointly prove archive member hashes, source-file fingerprints, or the
  zero-event ambiguity.
