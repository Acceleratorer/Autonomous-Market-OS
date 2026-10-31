# ADR-0047: B4.18 versioned schema migration

**Date:** 2026-10-29
**Status:** Accepted and implemented locally; connected use remains gated
**Scope:** Synthetic, paper-only, local portfolio persistence

## Context

B4.12 provides read-only migration preflight. B4.11 provides validated local
backup and restore. The broker currently owns append-only events, checkpoints,
shared membership, reservations, recovery, fingerprints, and deterministic
replay. The first transformer is a local copy-on-write envelope migration; the
source remains authoritative so changing schemas in place cannot make recovery
or rollback ambiguous.

## Decision

Implement B4.18 as a local backend gate with a copy-on-write,
versioned transformer:

- recover and back up the source first;
- transform into a new destination under the trusted local root;
- recover the target envelope natively and validate source-projection semantic replay equivalence independently;
- preserve source bytes and the rollback copy;
- promote only a fully validated destination;
- record a bounded migration manifest and idempotent migration identity.

The first target is `market-os.b4-18.*@v2`, with explicit mappings from the
current isolated and shared B4 schemas. Target-native recovery validates the
v2 metadata, policy/genesis identity, event ordering and fingerprints, snapshots,
shared reservations, and checkpoint relation. A separate source-projection
replay must match semantic state and inspection resources before promotion. No
automatic startup migration or in-place rewrite is allowed.

## Alternatives rejected

- **In-place rewrite:** weakens rollback and makes source fingerprints
  unverifiable after a failed transform.
- **Retention deletion first:** would remove evidence before schema meaning is
  stable and would complicate recovery equivalence.
- **Connected/authenticated mutation first:** would expose an unstable storage
  contract and multiply the number of states needing authorization tests.
- **Database replacement:** adds a new persistence authority without a need;
  the existing file-backed ledger remains authoritative for the local scope.

## Consequences

Migration requires temporary local disk space and explicit operator review. The
source store remains authoritative until promotion. Connected web/deployment
work remains gated on U5.5 and does not start from this ADR alone.

## Promotion criteria

The implementation requires the B4.18 contract, field mapping and interruption
tests, backup and rollback evidence, source/destination fingerprint checks,
target-native recovery, replay equivalence, conflict-safe retries, and full
local verification. The explicit local maintenance seam is `migrate_portfolio()`;
connected web, HTTP mutation, and deployment remain separate gates.
