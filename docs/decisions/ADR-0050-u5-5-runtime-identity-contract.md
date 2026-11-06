# ADR-0050: U5.5 runtime and identity contract v1

**Date:** 2026-10-30
**Status:** Locally verified, not enabled
**Scope:** Future private, authenticated, read-only operator preview

## Context

The local synthetic and paper-only operator is complete through U5.24. The
repository has selected Next.js for the private preview direction and
DirectAdmin for a separate disconnected static artifact. The connected target
is now selected as an owner-controlled private Linux VM with systemd and
Tailscale Serve, but it is not enabled until the local U5.5 matrix and host
promotion evidence pass.

The U5.5 contract needs a durable decision record so later implementation does
not silently turn a host, proxy header, or deployment secret into an identity
boundary.

## Decision

Adopt `market-os.u5-5.connected-runtime-identity@v1` as the contract for any
future connected read-only preview.

- Keep Python authoritative for accounting, risk, persistence, recovery,
  reservations, fingerprints, and audit outcomes.
- Keep Next.js as a thin server-side read-only adapter. It may consume only
  bounded, versioned Python inspection resources.
- Place a selected reverse proxy or private ingress in front of loopback-only
  Next.js and Python processes. The Python origin must reject direct access and
  caller-supplied principal headers.
- Trust only a verified, versioned principal envelope containing bounded
  `issuer`, `subject`, `audience`, `issued_at`, `expires_at`, `jti`, and the
  verified assertion method. Diagnostic request IDs never grant identity.
- Authorize server-side with an explicit versioned
  `subject -> tenant -> portfolio_id -> inspection resource` mapping. Missing,
  stale, cross-tenant, or ambiguous mappings deny by default.
- Keep portfolio storage isolated and fail closed on traversal, symlink or
  reparse aliases, descriptor replacement, and cross-tenant roots.
- Require short-lived, revocable, replay-resistant sessions with documented
  clock tolerance, bounded request/page/body/time budgets, safe audit records,
  health-gated copy-on-write promotion, and one known-good rollback slot.
- Inject secrets only into server processes through the selected host mechanism;
  never place credentials, raw assertions, signatures, or capability tokens in
  browser bundles, HTML, manifests, logs, ledger, checkpoints, or snapshots.
- Keep all mutations out of connected web until a separate versioned,
  authenticated, idempotent, audited mutation contract is approved.

### Concrete owner selections (2026-10-30)

- Runtime: owner-controlled private Linux VM; `systemd` supervises Python and
  Next.js.
- Ingress: owner-controlled private Tailscale tailnet with Tailscale Serve;
  only the owner's Tailscale identity is admitted.
- Subject: `owner-only` (one owner subject only).
- Portfolio allowlist: `paper-main` only.
- Portfolio root: `/var/lib/autonomous-market-os/portfolios`, with no
  traversal, symlink, reparse, bind-alias, or cross-portfolio access.
- Session: 15-minute expiry, 60-second clock tolerance, revocable hashed
  `jti`, one-time replay protection, and fail-closed missing/invalid identity.
- Backup/rollback: project owner owns operations; encrypted backup before
  promotion, one known-good release slot, and health failure keeps the active
  version unchanged or restores the known-good slot.
- Connected mutation, provider credentials, Binance, live trading, public
  deployment, retention deletion, partial fills, expiry, and distributed
  ownership remain disabled.

The promotion state is monotonic:

```text
defined -> target_selected -> locally_verified -> enabled
```

The repository is now at `locally_verified`. Local application-boundary,
authorization, storage, audit, browser, health, and rollback-procedure evidence
passes; the owner Linux VM/Tailscale promotion and rollback have not been run.
The runtime remains disabled. See
[`u5-5-promotion-evidence.json`](../evidence/u5-5-promotion-evidence.json).
This status does not enable a listener, accept credentials, or authorize
deployment.

## Rationale

The existing local contracts already protect deterministic replay and paper
accounting. A thin connected adapter preserves one authority and keeps identity,
authorization, storage, session, and rollback controls explicit before access
leaves the loopback boundary. A separate ADR also prevents the disconnected
DirectAdmin static preview from being mistaken for a connected runtime.

## Consequences

- Promotion is blocked until the owner VM health, Tailscale ingress, encrypted
  backup, and rollback evidence pass.
- The local gateway, CLI, static artifact, append-only ledger, checkpoints,
  fingerprints, replay, reservations, and audit behavior stay unchanged.
- Cloudflare Tunnel + Access and WireGuard/OIDC remain candidates only; the
  connected Tailscale/Linux/systemd target is the approved U5.5 direction.
- No HTTP or CLI mutation route, provider, exchange credential, network
  execution path, or live-trading capability is introduced.

## Alternatives considered

- **Expose the Python gateway directly:** rejected because it bypasses the
  intended origin and authorization boundary.
- **Trust a caller-provided `X-User` or `X-Request-ID` header:** rejected
  because an origin cannot distinguish a forged header without a verified
  ingress assertion.
- **Use DirectAdmin as the connected Next.js/Python host:** rejected until its
  process supervision, ingress, identity, storage isolation, secrets,
  rollback, and audit capabilities are separately verified.
- **Add a database or move accounting into TypeScript:** rejected because no
  approved requirement needs a second persistence/accounting authority.

## Promotion gate

Before moving beyond `locally_verified`, run the selected host, ingress, identity
method, subject set, portfolio allowlist, storage root, session policy, secret
mechanism, rate/body/time limits, audit retention, backup/restore policy, and
rollback procedure. Then run the cases in
[`U5.5-AUTHENTICATED-CONNECTED-WEB-CONTRACT.md`](../U5.5-AUTHENTICATED-CONNECTED-WEB-CONTRACT.md)
for allowed, denied, expired, replayed, forged-principal, direct-origin,
cross-portfolio, path-alias, abuse-limit, rollback, and secret-scan behavior.
