# Stack and Runtime Review

**Date:** 2026-10-30
**Status:** U5.5 target selected and locally verified; connected runtime remains disabled pending owner-VM promotion and rollback
**Scope:** Local synthetic/paper system, future private read-only preview, and disconnected static preview

## 1. Current codebase shape

The U5.5 boundary is recorded durably in
[`ADR-0050`](decisions/ADR-0050-u5-5-runtime-identity-contract.md). Its state
is `locally_verified`: the owner-controlled private Linux VM, `systemd`,
owner-only Tailscale Serve ingress, `owner-only` subject, and `paper-main`
allowlist are selected. The runtime is not enabled; owner-VM promotion and
rollback remain pending.

The repository already has a useful separation of responsibilities:

| Area | Current owner | Role | Boundary |
|---|---|---|---|
| Domain and accounting | `market_os/portfolio_broker.py`, `paper_venue.py` | Portfolio identity, shared membership, reservations, order lifecycle, risk, ledger, replay | Python is authoritative |
| Recovery and operations | `portfolio_backup.py`, `schema_migration.py`, `portfolio_migration.py`, `local_mutation.py` | Backup/restore, copy-on-write migration, capability seam, archive preflight | Local, synthetic, paper-only |
| Local transport | `market_os/api.py`, `apps/gateway/` | Loopback HTTP inspection and bounded request handling | No public listener |
| CLI | `market_os/cli.py`, `apps/cli/` | Compatibility entrypoint for inspection and explicitly local commands | No public mutation surface |
| Compatibility browser | `apps/web/operator/` | Gateway-served GET-only inspection shell | Local only |
| Component browser | `apps/web/next-operator/` | Server-rendered read-only operator UI | Node/Next loopback only |
| Disconnected preview | `apps/web/public/` | Static paper-only product preview | No portfolio data or API connection |

The intended flow is:

```text
file-backed portfolio store
        |
        v
Python broker and recovery contracts
        |
        v
loopback Python gateway
        |
        +--> compatibility HTML operator
        +--> Next.js server-rendered operator
        +--> CLI inspection
```

The browser and Node layers must remain consumers of versioned Python-owned
contracts. They must not reimplement accounting, risk, recovery, reservation,
fingerprint, or mutation semantics.

## 2. Stack decisions that are already sound

### Keep Python as the domain authority

The existing Python package owns the hard parts: Decimal accounting, append-only
ledger semantics, checkpoint validation, stale-writer rejection, shared cash and
inventory reservations, replay, audit outcomes, backup/restore, and migration.
Moving those rules into TypeScript would create two accounting implementations
and weaken deterministic equivalence.

### Keep Next.js for the operator surface

`apps/web/next-operator/` is already implemented with TypeScript, React,
Next.js App Router, Node.js 20.9+, and Tailwind CSS. It is the right fit for
server-rendered read-only views over the existing gateway. It should remain a
thin adapter with typed response validation and no portfolio state ownership.

### Keep the static preview separate

`apps/web/public/` is intentionally disconnected. DirectAdmin is suitable for
that artifact because it needs only static file hosting. It is not an approved
runtime for the private Next.js/Python operator until process supervision,
storage isolation, identity, authorization, rollback, and secret handling are
verified as a separate contract.

### Do not introduce a database yet

The JSONL ledger plus JSON metadata/checkpoint format is the current integrity
authority. A database would add a second persistence and migration contract
without solving an approved requirement. Revisit it only if a measured need for
multi-process indexing, cross-tenant queries, or transactional administration is
accepted in a new versioned contract.

## 3. Candidate connected runtime shapes

| Candidate | Fit | Main risk | Decision |
|---|---|---|---|
| DirectAdmin static artifact | Disconnected preview only | Cannot be assumed to provide the always-on private Python + Next runtime | Selected only for static preview |
| Private Linux VM with `systemd`, Next.js process, and loopback Python gateway | Single-tenant private preview | Requires host promotion, patching, backups, and origin lockdown | **Selected U5.5 target; owner-VM promotion pending** |
| Private network access in front of the same runtime | One owner or small trusted operator set | Device enrollment and identity lifecycle become part of operations | Candidate after runtime contract |
| Edge access proxy in front of the same runtime | Browser-only access | Edge identity assertions must be verified at the origin; edge-only policy is insufficient | Candidate after identity contract |
| Directly exposing the Python gateway | None | Bypasses the intended origin and authorization boundary | Rejected |

The repository therefore has two distinct deployment tracks:

1. **Static preview:** build `apps/web/public/`, verify exact artifact parity,
   and deploy manually when DirectAdmin prerequisites are available.
2. **Private operator:** run Next.js and Python together under `systemd`, behind
   owner-only Tailscale Serve, only after the owner-VM promotion gate closes.

The two tracks must not share secrets, portfolio storage, or deployment
promotion logic.

## 4. Remaining U5.5 evidence gates before connected work

The selected runtime is locally verified; the following host evidence gates
remain before connected work can be enabled:

1. **Hosting runtime:** install the selected `systemd` units on the private
   Linux VM and verify health, restart behavior, patch ownership, and the
   loopback-only origin.
2. **Identity:** apply the owner-controlled Tailscale policy and verify the
   `owner-only` subject and stable assertion path. `X-Request-ID` is diagnostic
   only and cannot identify a user.
3. **Authorization:** a server-side subject-to-portfolio allowlist with
   fail-closed behavior for missing, forged, expired, or mismatched claims.
4. **Storage isolation:** the private runtime may read only the approved local
   portfolio root; path traversal, symlink/reparse aliases, and cross-tenant
   roots must fail closed.
5. **Session:** expiry, revocation, clock tolerance, secure cookie policy,
   direct-origin denial, and replay handling.
6. **Audit:** denied requests, principal changes, portfolio decisions, backup,
   restore, and rollback events with bounded safe metadata and no secrets.
7. **Rollback:** versioned artifact promotion, one known-good rollback slot,
   health verification, and interruption recovery for both Next and Python.
8. **Secrets:** server-only injection, rotation, redaction from logs and
   bundles, repository secret names documented without values, and no browser
   `NEXT_PUBLIC_*` credentials.
9. **Abuse controls:** request/body limits, timeouts, rate limits, error
   responses, and resource budgets for inspection endpoints.
10. **Evidence:** allowed/denied, expired/replayed, forged-principal,
    cross-portfolio, direct-origin, rollback, and secret-scan tests.

## 5. Recommended next sequence

1. Keep the current local boundary and selective worktree baseline intact.
2. Run the read-only `deploy/u5-5/promotion_evidence.py --mode dry-run`
   harness and retain its schema-validated evidence.
3. Run the U5.5 auth/isolation/session/audit/rollback matrix locally, preserving
   the Python gateway as the domain owner.
4. On the owner's Linux VM, run the harness in `--mode owner-vm`, install the
   services, apply the reviewed tailnet policy, and perform promotion/rollback
   only after the owner reviews the emitted evidence.
5. Treat DirectAdmin static deployment as a separate manual release only after
   its host secrets and TLS prerequisites are supplied; never use it as proof
   that the private operator is deployable.

## 6. Explicit non-goals

This review does not authorize public exposure, connected mutation routes, live
trading, Binance credentials, provider access, distributed broker ownership,
portfolio deletion, or production infrastructure. Those remain separate
contracts and evidence gates.
