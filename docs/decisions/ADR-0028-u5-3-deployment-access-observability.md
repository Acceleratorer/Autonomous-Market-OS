# ADR-0028: U5.3 deployment handoff and local observability

**Date:** 2026-10-28  
**Status:** Accepted for local implementation

## Decision

Add a deterministic static artifact manifest and request correlation IDs to the
existing local gateway. Keep deployment handoff, access control, and
observability verification separate from public deployment.

## Rationale

The artifact needs a reviewable identity before a hosting handoff, and the
loopback API needs a safe way to correlate a response with its audit record.
Both changes are local, reversible, dependency-free, and do not grant access
or mutate portfolio state.

## Consequences

- Static handoffs can verify exact file hashes before copying files.
- Local request diagnostics are easier to correlate without storing query data.
- `X-Request-ID` is not a user identity or authorization mechanism.
- Authenticated shared deployment remains a future contract and approval gate.
