# Codebase and stack understanding report

**Date:** 2026-11-15

**Source checkpoint:** `19367f4` (`main`; U6.4-F hosted evidence is retained in the current documentation refresh)

**Scope:** local deterministic system, synthetic paper portfolio, read-only
operator surfaces, desktop release/install path, and the permanent paper-only
decision.

## Executive result

Autonomous-Market-OS has one domain authority: the Python `market_os` package.
It owns portfolio accounting, risk, reservations, persistence, recovery,
replay, audit, and deterministic evidence generation. The CLI, loopback
gateway, Next.js operator, static preview, and Electron shell are adapters that
present or package those capabilities. They should not reproduce domain or
risk behavior.

U6.4-D validates a signed target-native artifact. U6.4-E simulates an offline
installation using staging, atomic publication, fresh mutable storage, and
post-copy verification. Neither bundles Python nor registers an operating
system service. U7-A–U7-O evidence products are complete. U8-A/U8-B remain
gated, and U8-C records the accepted permanent paper-only decision. Connected
and live-readiness work therefore stays closed unless a new explicit owner
decision reopens it.

## Execution paths

### Domain and inspection path

```text
fixture or bounded local input
  -> typed contract / deterministic workflow
  -> evaluation, accounting, risk, or paper execution in market_os
  -> append-only events and content-addressed artifacts
  -> CLI, loopback gateway, local HTML, Next.js, or static preview
```

The Next.js server-side client reads bounded GET resources from the loopback
Python gateway. The static artifact is disconnected from portfolio state and
the gateway. The CLI and gateway remain compatibility entrypoints around the
same Python contracts.

### Desktop release/install path

```text
matching Windows/Linux CI runner
  -> target-native Electron + Python source-sidecar artifact (U6.4-C)
  -> signature/manifest/storage/runtime preflight (U6.4-D)
  -> offline staging, publish, storage reset, and revalidation simulation (U6.4-E)
```

U6.4-E remains the source-sidecar installation simulation. U6.4-F now adds the
accepted portable adapter: signed embedded CPython 3.11.x, per-user staging and
atomic publish, state preservation, manual rollback, verification-failure
recovery, and uninstall retention. Native service registration and package
manager integration remain disabled; hosted Windows/Linux evidence is retained
and the U6.4-F gate is closed.

## Responsibility map

| Capability | Module / adapter | Responsibility |
|---|---|---|
| Domain orchestration | `market_os.workflow`, `market_os.orchestration/` | Run lifecycle, recovery, and provider composition |
| Portfolio, risk, recovery | `market_os.portfolio_broker`, `paper_venue`, `portfolio_backup`, `schema_migration` | Synthetic paper fills, ledger, reservations, recovery, backup, and migration |
| Research and evaluation | `market_os.research`, `btc_*`, `evaluation_protocol`, `quality_*` | Deterministic research, BTC features/evaluation, and quality evidence |
| Evidence products | `market_os/u7_*`, `u8a_readiness`, `u8b_operations`, `u8c_paper_mode` | Fail-closed reports, catalogs, readiness packs, and paper-mode decision evidence |
| CLI | `market_os.cli`, `apps/cli/` | Parse and dispatch commands against shared Python contracts |
| Local gateway | `market_os.api`, `apps/gateway/` | Loopback HTTP and bounded read-only inspection |
| Web operator | `apps/web/operator`, `apps/web/next-operator` | Local GET-only views over the shared API |
| Static preview | `apps/web/public/` | Disconnected read-only artifact; no private runtime connection |
| Desktop shell and release | `apps/desktop/electron/` | Electron lifecycle, target-native artifact packaging, signing, promotion, rollback, and U6.4-D/E tooling |
| CI and evidence | `.github/workflows/`, `scripts/`, `docs/evidence/` | Offline checks, matching-target release jobs, and machine-readable evidence |

## Module depth and seams

- The Python package is the main deep module: transport adapters use its
  versioned contracts while calculation, persistence, replay, and policy stay
  inside the implementation.
- `market_os.api` and `market_os.cli` are stable seams used by multiple
  surfaces. Keep request parsing, bounds, and serialization at those seams;
  pass domain work into the Python implementation.
- The Electron release path has a practical seam at the signed artifact and
  its manifest. U6.4-D is the validation adapter, U6.4-E is the copy/publish
  simulation, and U6.4-F is the portable per-user installation adapter. One
  shared adapter covers both accepted targets; a platform-specific installer
  abstraction remains unnecessary until the contract requires different
  mechanics.
- The interface is also the test surface: callers should be able to verify
  artifact identity, storage isolation, publish outcome, and failure behavior
  through the install result without reaching through into unrelated domain
  modules.

## Stack and boundary decisions

### Keep

- Python 3.11+ as the domain, accounting, recovery, replay, risk, and audit
  authority.
- Python stdlib HTTP for the local gateway while it stays loopback-only and
  read-only.
- TypeScript, React, Next.js, Node.js, Tailwind, and Electron as thin local
  application adapters.
- JSONL plus JSON metadata/checkpoints as the current portfolio integrity
  authority; add no second database without a measured need and a recovery
  contract.
- Signed manifests, hashes, bounded resources, offline CI, and machine-readable
  evidence for packaging and review.

### Keep closed

- Connected/private runtime promotion, public hosting of the operator, and
  externally exposed mutation.
- Credentials, provider requests, Binance/network execution, and live trading.
- Retention deletion, distributed broker ownership, and unapproved lifecycle
  expansion.
- A second accounting/risk implementation in TypeScript or Electron.

U8-C accepts permanent paper-only mode. Reopening connected or live-readiness
work requires a new explicit owner decision and a complete U8 review.

## Gap classification

### Implemented and evidenced

- B4.1–B4.20 local synthetic paper broker, recovery, audit, backup, and
  migration hardening.
- U5.2–U5.24 local/static read-only operator surfaces.
- U6.1–U6.4-F CLI/app, Electron shell, signed target artifacts, installer
  preflight/simulation, embedded-runtime portable installation, rollback,
  uninstall-retention tooling, and matching hosted Windows/Linux evidence.
- U7-A–U7-O release, evaluation, report, and evidence products.
- U8-A/U8-B local readiness packs and U8-C permanent paper-only decision.

### Intentionally pending

- Mobile shell work.
- U5.5 connected promotion and production operations; U8-C keeps this track
  closed under the current owner decision.
- Providers, credentials, live execution, external mutation, distributed
  ownership, partial-fill/expiry expansion, and retention deletion.

## Exact next gate

U6.4-F is closed by hosted CI run `43740383177` on merged commit `19367f4`.
The target-specific runner images and CPython provenance are recorded in
[`u6-4-f-hosted-installation.json`](evidence/u6-4-f-hosted-installation.json);
the local contract validator remains the guard against reopened decisions or a
changed paper-only boundary. No U6.4-F work remains open.

The next work must be a separately scoped local, offline, synthetic,
paper-only slice. Connected promotion, providers, credentials, mutation, and
live execution remain closed by U8-C.

## Verification snapshot

The latest documented full suite passed `659 passed, 0 failed, 7 skipped` on
U8-B commit `db8c8dd`. Later U8-C and U6.4-D/E changes were committed after
that run; do not report the full-suite result as covering them. U6.4-D/E have
separate local evidence files under `docs/evidence/`, and CI is configured to
run the install checks on matching Windows/Linux runners. The current Electron
suite passed `34 passed, 0 failed`, including the U6.4-F runtime and installer
tests; the Python full suite was not rerun. Hosted CI run `43740383177` passed
15 checks with 0 failures, including both U6.4-F Windows/Linux hardening legs.

The working-tree Understand Anything graph covers all 610 scanned files: 2,250
nodes, 4,014 edges, 8 Vietnamese architecture layers, and a 10-step Vietnamese
tour.
Deterministic validation found no structural issues; it reported 125 nodes with
no incident edges as warnings. The graph and freshness metadata are in
`.ua/knowledge-graph.json` and `.ua/meta.json`.
Fingerprint generation succeeded for all 610 files; the multi-document
Kubernetes YAML manifest used the documented regex fallback after a parser
warning.

## Source evidence

- [`PROJECT-CONTEXT.md`](PROJECT-CONTEXT.md)
- [`STRUCTURE.md`](../STRUCTURE.md)
- [`ROADMAP.md`](ROADMAP.md)
- [`PHASES.md`](PHASES.md)
- [`LOCAL-EXIT-GATE-REPORT.md`](LOCAL-EXIT-GATE-REPORT.md)
- [`NEXT-WORK-HANDOFF.md`](NEXT-WORK-HANDOFF.md)
- [`U6.4-D installer preflight`](U6.4-D-INSTALLER-PREFLIGHT.md)
- [`U6.4-E offline install simulation`](U6.4-E-OFFLINE-INSTALL-SIMULATION.md)
- [`U8-C permanent paper-only decision`](U8-C-PERMANENT-PAPER-ONLY.md)
- [`U6.4-F hosted installation evidence`](evidence/u6-4-f-hosted-installation.json)
- `.ua/knowledge-graph.json` and `.ua/meta.json`
