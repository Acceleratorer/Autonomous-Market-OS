# Local Exit Gate Report

**Date:** 2026-11-02
**Scope:** Autonomous-Market-OS local deterministic engine, paper broker, bounded BTC evaluation, local inspection/API, and CI evidence.

## Decision

The approved local-first implementation boundary is green for continued local work and review. The repository is **not** promoted to connected web, public hosting, live trading, or externally exposed mutation.

## Verified

- Backend/domain: B4.1–B4.20 synthetic paper broker, shared membership, reservations, lifecycle, backup/restore, migration preflight, copy-on-write schema migration, read-only retention/archive preflight, audit outcomes, and local capability authorization.
- API/service: loopback host checks, same-origin POST protection, bounded JSON request bodies, bounded drain/connection handling for rejected POSTs on Windows clients, read-only BTC history/connectivity/B2/B3 inspection, and non-mutating portfolio inspection.
- Quantitative processing: deterministic BTC history, feature/label materialization, chronological splits, explicit unavailable handling for insufficient samples, a continuous synthetic positive B2/B3 evaluation path through persistence, replay, CLI, and API inspection, recorded-response B3 evaluation, and not-promoted status.
- Recovery/integrity: append-only ledger, fingerprints, checkpoints, stale-writer rejection, recovery parity, and no-create read-only lock behavior.
- Verification history: an earlier clean full run passed `588 passed, 0 failed, 7 skipped`; the focused workflow and B4 regression suites passed 118 tests, including rejected-POST body handling; the focused portfolio/recovery group passed 110 tests and the focused B4.20 suite passed 21 tests. That historical pack also passed Python compile, dependency consistency, TypeScript contract, Next.js typecheck/build, static artifact parity, secret scan, M2.8 evidence, 55 evidence JSON files, and `git diff --check`; the dependency audit reported zero vulnerabilities. Current reproductions use the pinned pnpm lockfile.
- Current 2026-11-02 verification pack: the final full suite passed `613 passed, 0 failed, 7 skipped`; the focused BTC inspection group passed 7 tests, including CLI/API parity for bounded ingestion manifests, details, outcomes, gaps, provenance, and cursors. One preceding full-suite attempt hit the known Windows `WinError 10053` socket flake in `test_server_rejects_query_parameters_and_writes`; the isolated test passed 10/10, the complete server test file passed 10/10, the direct HTTP harness passed 20/20 requests, and the subsequent full rerun passed. Evidence validation covered 63 JSON files; M2.8, MLOps, secret scan, graph validation, compileall, Next.js typecheck/build, and `git diff --check` passed.
- Hosted checks: GitHub CI (`41345129472`), DevSecOps (`41345129459`), and Security/package checks (`41345129404`) passed on commit `f6ba90a`; the package-readonly-dashboard artifact job (`124963977482`) also passed. GitHub reported only non-blocking action-runtime/runner migration warnings.
- Hosted U7-M confirmation: GitHub CI run `43056896652` passed on commit `7d33e08`; the `u7-release-catalog` job completed Windows/Linux target-native evidence validation, catalog generation, and drift auditing with `drift_count: 0`, retaining the JSON/Markdown report artifact.
- Hosted U7-N/O confirmation: GitHub CI run `43090213351` passed on commit `65a37aa`; offline-tests rendered U7-N and U7-O, and the downloaded U7-O artifact matched the committed catalog fingerprint `5c484710bc7007f90406352b660e5dbe4492c7662d6cdf9875a278c77649655e2` with the same boundary.
- Review: the final focused security review found no actionable defects in the new read-only CLI/store paths, B4.1 inspection locks, or bounded POST handling.
- Deployment: the disconnected DirectAdmin static preview is live and was revalidated read-only on 2026-11-02. `/market-os/` returned 200 with a SHA-256 matching `apps/web/public/index.html`; `/`, `/waifu/`, and `/wuwa-map/` returned 200; `DEPLOYMENT.txt` returned 403; no forms or scripts were present. The private Next.js/Python runtime remains unpromoted.
- Worktree source of truth: `main` and `origin/main` are aligned; there are zero tracked changes and zero untracked paths. The 2026-10-30 279-path manifest and 2026-11-01 20-path reconciliation remain historical. Six preserved top-level scratch/workspace files were moved, without deletion, to `D:\Code\Github\HKUDS\Autonomous-Market-OS-local-scratch-2026-11-02`.

## Explicitly deferred gates

These remain documented decisions, not hidden bugs: partial fills and expiry semantics, retention deletion/pruning, authenticated externally exposed mutation, connected identity/authorization/isolation, distributed locks, live providers, credentials, Binance/network execution, and production infrastructure.

## Next gate

U7-M is complete locally. The release catalog CI job now audits the full
Windows/Linux evidence chain from U6.4-C through U7-A/U7-B/U7-D/U7-E and emits
a fail-closed drift report for schema/status, manifest provenance, signatures,
four-route smoke, promotion/rollback, and the shared private/read-only/
paper-only/execution-disabled boundary. Target-native archive and manifest
hash differences remain expected variance when each target is internally
consistent.

U7-N is now hosted-verified in CI, and U7-O catalogs the committed U7-N/J/K/L
evidence surface with normalized source/report fingerprints and one shared
boundary. U8-A records the local live-readiness decision pack and U8-B records
the local operational-readiness pack: local preflight and operational controls
pass, but connected runtime and production operations are not verified. Both
results are gated with paper-only as the default and no execution-boundary
change. Owner VM/access, Tailscale Serve, production retention/alerting,
connected promotion/reconciliation, credentials/provider approval, and live
authorization remain blocked. Mobile, mutation routes, and providers remain
deferred; U6.4-F portable installation is implemented locally and awaits hosted
Windows/Linux evidence.

## U8-B hosted confirmation (2026-11-14)

The U8-B local operational-readiness pack was verified on commit `db8c8dd`.
The full local suite passed `659 passed, 0 failed, 7 skipped`; evidence
validation covered 83 JSON files. GitHub CI `43485964489`, DevSecOps
`43485964548`, and Security/package checks `43485964375` all passed. The
hosted U8-B JSON and Markdown artifacts matched the committed evidence
exactly, including operations fingerprint
`2c5b46000f88076f578bf9dfb4f2a75539db91c7f974737d29c2217d09f461a4`.

This confirms local operational controls only. Owner VM/access, production
retention and alerting, connected reconciliation, credentials, and live
authorization remain blocked; the private, synthetic, read-only, paper-only,
execution-disabled boundary is unchanged.

## Post-U8-B continuation state (updated 2026-11-15)

After the U8-B full-suite/hosted verification, U8-C accepted permanent
paper-only mode. U6.4-D added signed-artifact preflight and U6.4-E added an
offline install simulation. Their local evidence is recorded in
`docs/evidence/u6-4-install-preflight.json` and
`docs/evidence/u6-4-install-simulation.json`; the workflows are configured to
run on matching Windows/Linux runners. The U8-B full-suite count above is not a
verification result for these later commits.

The connected/live track is closed by the U8-C decision. U6.4-F is now an
accepted local implementation with embedded runtime validation, portable
install/upgrade/rollback, verification-failure recovery, and uninstall state
retention. Matching hosted Windows/Linux evidence closed the U6.4-F gate in CI
run `43740383177`; see
[`u6-4-f-hosted-installation.json`](evidence/u6-4-f-hosted-installation.json)
for exact runner images and runtime hashes.

The full Understand Anything graph now covers 616 scanned files and has 2,274
nodes, 4,062 edges, 8 Vietnamese layers, and an 11-step tour. Structural
validation passed with 0 issues; 125 pre-existing no-edge node warnings remain.
The graph and metadata live under `.ua/`. The Electron suite passed 34 tests,
including the U6.4-F runtime and portable-install checks; the Python full suite
passed 669 tests with 0 failures and 7 skips.

## U6.4-F hosted installation confirmation (2026-11-16)

CI run `43740383177` on merged commit `19367f4` passed both the Windows and
Linux U6.4-F hardening legs. Each target verified signed package identity,
CPython 3.11 provenance and SHA-256, fresh install, state-preserving upgrade,
manual rollback, verification-failure recovery, uninstall retention, and the
unchanged private/synthetic/read-only/paper-only boundary. Exact runner images,
runtime hashes, and candidate archive hashes are recorded in
[`u6-4-f-hosted-installation.json`](evidence/u6-4-f-hosted-installation.json).

The U6.4-F gate is closed. The connected/live track remains permanently
paper-only under U8-C.

## U7-P reproducibility confirmation (2026-11-16)

The U7-P local audit regenerated U7-N/J/K/L twice from committed offline inputs,
rebuilt U7-O twice, and matched the committed catalog body, fingerprint, source
hashes, lineage, and shared private/synthetic/read-only/paper-only boundary.
The reproducibility evidence fingerprint is
146c332a386d83ece76a02d717aea658d09d687b0f336f41ced1706efb3d5d2d; the
focused U7 suite passed 13 tests and the full Python suite passed 669 tests with
0 failures and 7 skips. This remains a local, synthetic, paper-only check.
