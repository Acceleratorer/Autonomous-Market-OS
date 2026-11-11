# Codebase and stack understanding report

**Date:** 2026-11-02
**Scope:** Current local worktree, synthetic paper system, local operator, and
future connected-preview gate

## Executive result

The repository already has a coherent backend-first architecture. Python owns
portfolio accounting, risk, reservations, persistence, recovery, replay, and
audit. The gateway and CLI are thin Python surfaces. The Next.js application is
a server-rendered, read-only adapter over the loopback gateway. The static
preview is a separate artifact with no portfolio state or API connection.

The local exit gate is complete for continued local-only work. The disconnected
DirectAdmin static preview is deployed and read-only verified; the private
Next.js/Python runtime is not promoted. U6 now includes bounded CLI projections
for BTC datasets, ingestion manifests, and B2/B3 research inspection; the next
implementation step is a thin read-only app shell over those shared contracts.
No connected host or identity provider is available today.

## Execution flow traced from code

```text
local JSON/JSONL portfolio store
  -> B41Broker recovery and validation
  -> accounting, risk, reservations, paper fills, audit, checkpoints
  -> bounded inspection resources in market_os.api
  -> apps/gateway (loopback 127.0.0.1)
  -> apps/web/operator or apps/web/next-operator
  -> read-only operator views
```

The CLI delegates to `market_os.cli`. The gateway delegates to the existing
`serve` command. The Next.js server-only client calls only GET resources on
`http://127.0.0.1:<port>` and validates response shapes before rendering.

## Responsibility map

| Capability | Authority | Current status |
|---|---|---|
| Decimal accounting and fills | `market_os/portfolio_broker.py`, `paper_venue.py` | Implemented, synthetic paper-only |
| Shared membership and reservations | `market_os/portfolio_broker.py` | Implemented and recovered with invariants |
| Ledger/checkpoint/fingerprints/replay | `market_os/portfolio_broker.py` | Implemented and regression-tested |
| Backup/restore/archive preflight | `market_os/portfolio_backup.py` | Implemented locally; deletion disabled |
| Schema migration | `market_os/schema_migration.py` | Implemented copy-on-write v2 locally |
| Local mutation authorization | `market_os/local_mutation.py` | Implemented as in-memory HMAC seam; no HTTP/CLI mutation |
| HTTP inspection | `market_os/api.py` | Loopback, bounded, mostly GET-only inspection |
| CLI inspection | `market_os/cli.py`, `apps/cli/` | Local compatibility surface |
| HTML operator | `apps/web/operator/` | Local GET-only shell |
| Next.js operator | `apps/web/next-operator/` | Local server-rendered GET-only UI |
| Static preview | `apps/web/public/` | Disconnected, paper-only artifact |
| CI and evidence | `.github/workflows/`, `scripts/ci_checks.py` | Tests, typecheck/build, security, evidence gates |

## Stack decisions

### Keep

- **Python 3.11+** for domain, persistence, recovery, replay, accounting,
  risk, and audit.
- **Python stdlib HTTP** for the local gateway while the boundary is loopback
  and read-only.
- **TypeScript + React + Next.js App Router + Node.js 20.9+ + Tailwind CSS**
  for the local/private operator surface. Keep it thin and server-side.
- **JSONL ledger plus JSON metadata/checkpoint** as the current integrity
  authority. Do not introduce a second database without a measured need and a
  new recovery contract.
- **pytest, compileall, TypeScript checks, Next build, Playwright, and CI
  evidence** as the verification stack.

### Do not add yet

- a database or ORM;
- a second accounting implementation in TypeScript;
- a generic `apps/app` bucket;
- a public API gateway or client-side authorization;
- HTTP/CLI mutation routes;
- provider credentials, Binance, live execution, or production infrastructure.

## Gap classification

### Implemented and verified

- B4.1–B4.20 local broker/recovery hardening;
- U5.2–U5.24 local/static operator slices;
- shared portfolio membership, reservations, stale-writer handling,
  idempotency, audit, migration, and archive preflight;
- the current live worktree at the `main` tip: zero tracked changes and zero
  untracked paths after archiving the six preserved top-level workspace files;
- the current knowledge graph contains 1,991 nodes and 5,025 edges, and the
  refreshed domain graph contains 88 nodes and 96 edges with all edge targets
  resolving;
- the latest full local pack passed 613 tests, 0 failed, and 7 skipped; evidence,
  M2.8, MLOps, secret scan, compileall, Next.js typecheck/build, and diff checks
  passed, and the three hosted workflows for the verification commit are green.

### Intentional deferrals

- partial fills and expiry expansion;
- retention deletion/pruning;
- distributed broker ownership;
- externally exposed mutation;
- live/provider/network execution;
- U5.5 connected identity, host, ingress, session, authorization, storage,
  audit, rollback, and secret operations.

### Owner decision required

To move past U5.5 `defined`, choose one concrete combination:

1. always-on runtime for Python + Next.js;
2. private ingress/access path;
3. identity/login assertion source;
4. subject set and portfolio allowlist;
5. storage root/isolation policy;
6. session, secret, audit, rollback, and rate-limit policy.

Until those choices are made, connected web and deployment are correctly
blocked by contract rather than missing implementation.

## Exact next gate

U7-N is the next local evidence slice: it joins the committed U7-I pack with
hosted-verified U7-M release provenance in one deterministic register. The
slice remains offline and reuses the existing contracts. Keep mutation,
providers, credentials, and connected access disabled. U5.5 owner-VM promotion
remains a separate gate for a future VM and access path.

## Graph-backed contract boundary

The refreshed knowledge graph places `market_os/cli.py` and `market_os/api.py`
in the API layer. The CLI imports the API adapter, store, workflow, metrics,
and U5.5 access configuration; its `build_parser` and `main` functions define
the command tree and serialize the same bounded inspection envelopes. The
Next.js `market-api.ts` node is a server-only projection that parses those
versioned GET responses for pages under `apps/web/next-operator/`. The domain
graph links these operator surfaces to the orchestration, portfolio, and BTC
market-data domains while keeping the disconnected static preview separate
from the deferred private connected runtime.

## Source evidence

- [STRUCTURE.md](../STRUCTURE.md)
- [STACK-AND-RUNTIME-REVIEW.md](STACK-AND-RUNTIME-REVIEW.md)
- [NEXT-STACK-AND-DEPLOYMENT-PLAN.md](NEXT-STACK-AND-DEPLOYMENT-PLAN.md)
- [U5.5-AUTHENTICATED-CONNECTED-WEB-CONTRACT.md](U5.5-AUTHENTICATED-CONNECTED-WEB-CONTRACT.md)
- [ADR-0050](decisions/ADR-0050-u5-5-runtime-identity-contract.md)
- [WORKTREE-BASELINE-MANIFEST.json](WORKTREE-BASELINE-MANIFEST.json)
- [LOCAL-EXIT-GATE-REPORT.md](LOCAL-EXIT-GATE-REPORT.md)
