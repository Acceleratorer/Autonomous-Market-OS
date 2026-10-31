# ADR-0048: B4.19 local mutation capability seam

**Date:** 2026-10-29
**Status:** Accepted and implemented locally
**Scope:** Synthetic, paper-only, local portfolio broker

## Context

B4.14 already records typed mutation outcomes, but direct Python broker methods
do not carry a caller capability. Connected web work is intentionally deferred,
so the next useful gate is a local capability seam that can be exercised and
audited without adding a transport or deployment boundary. This is not human
authentication: the subject is issuer-bound until U5.5 supplies a trusted
principal path.

## Decision

Add `LocalMutationAuthority` and a versioned HMAC capability token. The token
binds a stable subject, portfolio, operation, exact command fingerprint,
idempotency key, and issue/expiry times. The authority verifies the token in
memory and passes only a safe audit context to the existing broker mutation
methods.

Keep the current broker methods as compatibility-friendly internal methods so
the existing local tests and domain callers do not require a broad migration.
Future authenticated adapters must use the authority seam. No HTTP or CLI
mutation route is added.

## Alternatives rejected

- **HTTP or CLI authentication now:** would create an unversioned transport
  and session boundary before the connected runtime, identity, and isolation
  decisions are complete.
- **Persisting capability secrets or nonce tables:** would add a second secret
  and replay authority to the file-backed ledger without a need.
- **Changing every existing broker caller at once:** broad compatibility churn
  is unnecessary while the local seam can wrap the existing public methods.
- **Unsigned subject parameters:** caller-supplied identity without a signed
  command binding would not provide a capability-authorization boundary.

## Consequences

The local caller must keep the signing secret and current clock in memory.
Capability rejection is fail-closed and leaves the portfolio unchanged. A
successful capability check preserves existing locks, reservations, append-only
events, checkpoints, fingerprints, recovery, and idempotent retry semantics.
The seam is not human authentication or a connected identity system and must
not be presented as one.
