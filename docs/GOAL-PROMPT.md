# Goal prompt for the next implementation chat

Continue Autonomous-Market-OS from the current worktree. Read
`docs/PROJECT-CONTEXT.md` first, then inspect `STRUCTURE.md`, the active
milestone contracts, the local exit report, the roadmap, and the current
worktree status before editing.

## Objective

Finish the remaining **local, synthetic, paper-only** work that is justified by
the repository's contracts. Close one explicit gate at a time, with a
versioned contract, focused regression tests, machine-readable evidence, and a
closeout report. Keep Python as the domain, accounting, persistence, recovery,
risk, reservation, replay, and audit authority. Keep `apps/` surfaces thin.

## Current baseline

- B4.1–B4.20 local broker and recovery slices are implemented and verified.
- U5.2–U5.24 local/static operator slices are implemented and verified.
- The local exit gate remains local-only: the latest historical clean full run passed 605 tests, 0 failed, and 7 skipped. The 2026-11-02 verification pack passed 608 tests, 0 failed, and 7 skipped on two full runs; rejected-POST isolated retries passed 5/5, and U5.5 focused evidence and browser smoke are recorded.
- The Next.js operator is loopback-only and read-only. DirectAdmin is only a
  disconnected static-preview target; no connected deployment is authorized.
- U5.5 runtime/identity contract v1 has a selected owner-controlled Linux VM,
  systemd supervisor, owner-only Tailscale Serve ingress, subject, portfolio
  allowlist, fixed storage root, session policy, and rollback procedure.
  Connected access remains disabled until owner-VM promotion evidence passes.
- The worktree contains existing uncommitted product changes and preserved
  scratch/Playwright/output artifacts. Keep all of them intact.

## Execution rules

1. Build an evidence-backed gap list first. Classify each item as implemented,
   intentional deferral, or an actual local defect. Do not invent work merely
   because a target-tree folder or old report mentions it.
2. Choose one next gate. If it changes behavior or persistence, write its
   versioned contract and decision record before implementation. Prefer the
   smallest capability-based change that reuses existing helpers.
3. Add regression coverage before or with the implementation for ordering,
   conflicts, stale writers, retries, recovery, fingerprints, replay, audit,
   and inspection parity when applicable.
4. Update `STRUCTURE.md`, `docs/PROJECT-CONTEXT.md`, `docs/PHASES.md`,
   `docs/ROADMAP.md`, `docs/UNDERSTANDING-LOG.md`, and the relevant evidence
   JSON when the gate closes.
5. Run the narrow focused checks first, then the required local checks:
   `python -m pytest -q`, `python -m compileall -q market_os scripts`,
   `python scripts/ci_checks.py secret-scan`,
   `python scripts/ci_checks.py validate-evidence`, and `git diff --check`.
6. Preserve the synthetic, paper-only, local boundary. Do not add Binance,
   live trading, credentials, providers, public listeners, production
   infrastructure, or network-backed execution.
7. Do not add HTTP or CLI mutation routes without a separate versioned
   contract and authentication boundary. Do not rename or delete historical
   files or unrelated worktree artifacts during polish.
8. Do not reset, clean, commit, push, deploy, or expose secrets unless a later
   user request explicitly authorizes that separate operation.

## Web/deployment gate

Do not start connected web or hosting work merely because the local UI exists.
Before connected implementation, select and verify a concrete U5.5 runtime and
identity path against the v1 contract: hosting process model, identity
assertion, subject-to-portfolio authorization, storage isolation, session
expiry/revocation/replay handling, principal and denied-request audit,
health/rollback, server-only secret injection and rotation, rate/body/time
limits, and the evidence matrix. Static DirectAdmin preview and private
connected operator remain separate tracks.

## Final report

Report the milestone read, gap classification, files changed, tests and
evidence run, remaining intentional deferrals, risks, and the exact next gate.
Only move to web/deploy after the local exit criteria and the connected runtime
contract are both satisfied.
