# Worktree Baseline Report

**Date:** 2026-10-29
**Repository:** `D:\Code\Github\HKUDS\Autonomous-Market-OS`
**Branch:** `main`
**HEAD at snapshot:** `f0e832c720479f7e7ef58d7e5dd74eeb2e5f2ea0` (`docs: record U5.24 CI closeout`)

> This report and its manifest are a historical 2026-10-30 snapshot. They are
> preserved for audit context and are not a live staging recommendation.

## Decision

The current worktree is preserved as-is. No reset, clean, delete, commit, push,
or deploy operation was run for this baseline audit.

## Historical read-only reconciliation — 2026-11-01

At that audit point the repository was at `a1e007552c809b8fa45a57bd6f23fd00a7d6da78`,
which matched `origin/main`, with **12 tracked documentation/evidence edits**
and **8 preserved untracked paths**. That state is retained as historical
audit context. Use `git status --short` for the live state.

## Live read-only reconciliation — 2026-11-02

The live repository is at the `main` tip and matches `origin/main`. A fresh
read-only check found **0 tracked changes and 0 untracked paths**. The historical
2026-10-30 inventory remains **279 status paths** and the 2026-11-01 20-path
reconciliation is retained above for audit traceability. The six previously
preserved top-level scratch/workspace files were moved, without deletion, to
`D:\Code\Github\HKUDS\Autonomous-Market-OS-local-scratch-2026-11-02`.
No connected-runtime promotion was performed.

## Tracked product changes

The original baseline audit found seven tracked files. The current worktree now
includes additional B4.18 implementation and test files below; all original
artifacts remain preserved. These tracked files are suitable
for a later selective review/commit after owner approval:

| Path | Classification | Reason |
|---|---|---|
| `STRUCTURE.md` | product documentation | Aligns the repository map with the existing Next.js operator. |
| `docs/LOCAL-EXIT-GATE-REPORT.md` | product evidence/report | Reconciles the local exit gate with U5.24 and 50 evidence files. |
| `docs/PHASES.md` | product roadmap | Records U5.24 as the latest local web slice. |
| `docs/PROJECT-CONTEXT.md` | product handoff | Updates the active local boundary and latest CI closeout. |
| `docs/UNDERSTANDING-LOG.md` | product history | Records the U5.24 continuation and current boundary. |
| `docs/evidence/local-exit-gate.json` | machine evidence | Updates the evidence count and latest CI run identifiers. |
| `market_os/synthetic_server.py` | product code | Closes rejected read-only POST connections safely. |

The original seven files were the only tracked modifications at the time of the
baseline snapshot. Re-run `git status --short` before any selective staging.

## Preserved untracked artifacts

The baseline snapshot contained **182 untracked paths** totaling approximately
**16.3 MB**. Later deliverables add new untracked product documents and tests;
the current count is intentionally not used as a cleanup signal.
They are preserved and are not product-commit candidates by default:

| Group | Contents | Default treatment |
|---|---|---|
| `.playwright-cli/` | Browser inspection transcripts | Preserve as local review artifacts; do not stage by default. |
| `.tmp-*` | Historical probes, temporary stores, fixture outputs, and staged diffs | Preserve for provenance/debugging; do not stage by default. |
| `output/playwright/` | Screenshots, smoke scripts, logs, and generated synthetic stores | Preserve as review evidence; stage only when a milestone explicitly requires a bounded artifact. |
| `API.md` | Pre-existing workspace document | Preserve and review separately; do not classify as new product work without provenance. |

The untracked files are not ignored because the repository intentionally keeps
some local evidence visible. Their presence is not evidence that they belong in
the next product commit.

## Generated/ignored files

Generated Next.js output, Python bytecode, caches, and local virtual-environment
directories remain governed by the existing ignore rules. They were not
deleted or rewritten during this audit.

## Selective staging rule

When a product commit is later authorized, stage explicit paths only. The
default candidate set is the tracked product list above plus the new contract,
ADR, report, and evidence files for the selected milestone. Do not use
`git add .`, `git clean`, `git reset`, or broad generated-output staging.

## Verification

- `git status --short --untracked-files=all` was inspected.
- `git diff --name-only` and `git diff --stat` were inspected.
- Untracked path count and byte size were measured without modifying files.
- No cleanup or staging command was executed.

## Next gate

The B4.18 local migration gate is implemented in `market_os/schema_migration.py`
with contract, decision record, evidence, target-native recovery,
interruption-safe promotion, and focused regression coverage. B4.20 adds a
read-only archive/retention preflight; source retention remains indefinite and
deletion remains disabled. The current audit observed 13 tracked modified
entries and 248 untracked file paths totaling 16,508,178 bytes; all remain
preserved. Connected access and deployment remain separate gates.


## Current preserved snapshot — 2026-10-29 (B4.19 continuation)

A fresh read-only status reconciliation after the B4.19 local capability work found **11 tracked modified paths** and **244 untracked paths**. The increase from the prior 10/239 snapshot is the B4.19 broker/doc/test work plus preserved generated and scratch artifacts. No reset, clean, delete, staging, commit, push, or deployment operation was performed.

New product candidates are limited to `market_os/local_mutation.py`, `market_os/tests/test_local_mutation.py`, `docs/B4.19-LOCAL-MUTATION-CAPABILITY-CONTRACT.md`, `docs/decisions/ADR-0048-b4-19-local-mutation-capability.md`, and `docs/evidence/b4-19-local-mutation-capability-readiness.json`, plus the explicitly updated tracked documentation and broker seam. The existing `.playwright-cli/`, `.tmp-*`, `output/playwright/`, `API.md`, and earlier B4.18 candidates remain preserved and are not cleanup targets.

## Historical verified reconciliation — 2026-10-30

A read-only reconciliation counted 13 tracked modified paths and 248 untracked file paths
(16,508,178 bytes). The untracked paths classify as:

| Classification | Paths | Bytes | Treatment |
|---|---:|---:|---|
| B4.18/B4.19/B4.20/docs product candidates | 15 | 118,974 | Preserve; selectively stage only with explicit product review |
| `.tmp-*` scratch/probe artifacts | 120 | 3,876,865 | Preserve; never clean as part of this work |
| `.playwright-cli/` inspection artifacts | 12 | 167,884 | Preserve; do not stage by default |
| `output/playwright/` review artifacts | 100 | 12,302,686 | Preserve; stage only when evidence explicitly requires it |
| Pre-existing `API.md` | 1 | 41,769 | Preserve; provenance not established as new product work |

No `git clean`, reset, delete, staging, commit, push, or deployment operation was
used for this reconciliation. The 13 tracked changes remain a mixed snapshot of
product fixes and documentation reconciliation and require selective review before
any commit.

The B4.20 follow-up added only local archive validation hardening and two
symlink-parent regression cases. These remain uncommitted product candidates;
no preserved artifact was removed or rewritten.

The exact current path classification is machine-readable in
`docs/WORKTREE-BASELINE-MANIFEST.json`. It records the 13 tracked modified
paths, the 251 untracked paths after adding the manifest and runtime review
artifacts, the 31 selectable product candidates, and the preserved
scratch/inspection groups.
Selective staging must use that explicit list and owner review; `git add .`,
`git clean`, and reset remain prohibited.


## Current status after review artifacts — 2026-10-30

The subsequent read-only status contains 15 tracked modified paths and 254
untracked paths. The increase includes the U5.5 runtime/identity decision
record and the refreshed manifest; no prior artifact was removed or rewritten.
This status is informational and is not a staging recommendation. Reconcile
the manifest again immediately before any future selective staging.

## Current machine-readable reconciliation — 2026-10-30

`docs/WORKTREE-BASELINE-MANIFEST.json` now records 269 status paths: 15 tracked
modified paths, 254 untracked paths, 34 product candidates, and 235 preserved
scratch/inspection paths. It includes ADR-0050 and the refreshed U5.5 planning
documents while keeping `unclassified_paths` empty. No reset, clean, delete,
staging, commit, push, or deployment operation was used.

## Current read-only reconciliation — 2026-10-30

The current status contains 15 tracked modified paths and 256 untracked paths:
271 status paths in total. The two additional untracked product candidates are
the codebase/stack understanding report and its evidence JSON. This inventory
update preserves all existing artifacts and records no cleanup, staging,
commit, push, or deployment action.



## Current read-only reconciliation — 2026-10-30 final local closeout

The current status contains **22 tracked modified paths** and **257 untracked
paths**, for **279 status paths**. The machine-readable manifest classifies
**43 product candidates** (22 tracked plus 21 untracked `docs/` or `market_os/`
files) and **236 preserved scratch/inspection paths** totaling **16,569,828
bytes**. The preserved groups are `.tmp-*`, `.playwright-cli/`,
`output/playwright/`, and the pre-existing `API.md`; no path was deleted,
reset, cleaned, staged, committed, pushed, or deployed.

The current manifest is `docs/WORKTREE-BASELINE-MANIFEST.json` with
`unclassified_paths: []`. Selective staging remains owner-controlled and must
use explicit paths only.
