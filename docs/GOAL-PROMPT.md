# Goal prompt for the next implementation chat

Continue Autonomous-Market-OS from the live repository state. Read
`docs/PROJECT-CONTEXT.md`, `docs/NEXT-WORK-HANDOFF.md`, `STRUCTURE.md`,
`docs/ROADMAP.md`, `docs/PHASES.md`, the relevant U6.4 contracts, and
`git status` before editing. The checkpoint commit recorded by this handoff is merged commit `19367f4`;
local documentation and graph refresh artifacts may be uncommitted, so the
live status is authoritative.

## Current baseline

- U6.4-D signed-artifact installer preflight and U6.4-E offline install
  simulation are complete. E publishes through a staging directory and one
  rename, resets mutable storage, and revalidates the copied artifact. Neither
  registers a service nor bundles Python.
- U7-A through U7-O evidence and evaluation products are complete.
- U8-A and U8-B readiness packs remain gated. U8-C records the owner's
  accepted permanent paper-only decision. Do not reopen connected or live
  work without a new explicit owner decision and complete U8 review.
- The current product boundary remains local, synthetic, private,
  paper-only, read-only, and offline. Credentials, providers, mutation routes,
  public listeners, and live execution remain disabled.
- The latest documented full-suite result is `659 passed, 0 failed, 7
  skipped` on U8-B commit `db8c8dd`. Do not describe that as a full-suite run
  on later commits. U6.4-D/E have their own local evidence and focused test
  coverage; inspect those artifacts before making verification claims.
- U6.4-F is now an accepted implementation scope: signed portable tar.gz,
  per-user/no-elevation installation, CI-frozen CPython 3.11.x, preserved
  mutable state, manual rollback, and no native service. Read
  `docs/NEXT-WORK-HANDOFF.md` and verify the local slice before extending CI.
- The full Vietnamese Understand graph is available at `.ua/knowledge-graph.json`:
  611 scanned files, 2,251 nodes, 4,016 edges, 8 layers, and 10 tour steps.
  Check `.ua/meta.json` and fingerprints against the live source and docs first.
- U6.4-F is merged under accepted ADR-0055: portable signed install,
  embedded-runtime identity, state preservation, rollback, uninstall retention,
  and evidence rendering. Hosted Windows/Linux evidence is complete and
  retained in `docs/evidence/u6-4-f-hosted-installation.json`.

## Objective

Continue from merged U6.4-F commit `19367f4`. The hosted Windows/Linux gate is
closed and its evidence is retained in
`docs/evidence/u6-4-f-hosted-installation.json`. Choose the next scoped local,
offline, synthetic, paper-only slice while keeping Python authoritative and
Electron as a thin adapter over the existing release artifact and validation
contracts.

## Execution rules

1. Inspect the live Git state, existing U6.4-C/D/E contracts, Windows/Linux
   release workflow, installer scripts, evidence schemas, and the updated
   knowledge graph. Treat old reports as historical when their checkpoint is
   behind HEAD.
2. Treat ADR-0055 and the accepted U6.4-F contract as authoritative for
   package format, install scope, runtime provenance, lifecycle, and rollback.
3. Preserve the U8-C permanent paper-only decision and the local/offline
   execution boundary. Do not add provider or credential access, network
   execution, mutation routes, a public listener, connected hosting, or live
   trading.
4. Reuse the existing artifact signature, manifest, preflight, install
   simulation, storage-isolation, and rollback concepts. Avoid a second domain
   implementation in TypeScript or Electron.
5. Retain machine-readable JSON/Markdown CI evidence, rerun focused local
   checks after hosted evidence arrives, and keep the current docs/graph
   snapshots synchronized with the live worktree.
6. Preserve unrelated worktree files. Do not reset, clean, commit, push,
   deploy, install software on the host, or expose secrets unless separately
   requested.

## Final report

State the chosen gate, decisions made, files changed, checks and evidence
actually run, remaining deferrals, and the exact next step. Distinguish local
verification from hosted CI evidence.
