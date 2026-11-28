# Shared collaborator workflow

For a one-page start, use the [contributor start packet](CONTRIBUTOR-START.md).
This document is the detailed routine behind that packet.

For the compact artifact-to-file mapping, cadence, graph commit sequence, and
CI gate, read [KNOWLEDGE-MAINTENANCE.md](KNOWLEDGE-MAINTENANCE.md). This file
keeps the start, update, and handoff procedure explicit.

This repository is the shared memory for contributors and coding agents. A new
collaborator should be able to continue from Git without access to anyone's
private chat, local notes, or model context. Keep project knowledge reviewable
in this repository and treat the source, decisions, and evidence as authority.

## Start a work slice

1. Check `git status`, the current branch, and the latest commit before editing.
   Do not assume another collaborator left a clean tree.
2. Read [README.md](../README.md), [the active goal](GOAL-PROMPT.md), and the
   [current handoff](NEXT-WORK-HANDOFF.md).
3. Read the newest relevant entry in [UNDERSTANDING-LOG.md](UNDERSTANDING-LOG.md),
   then open the contracts, accepted ADRs, research notes, and evidence for the
   area being changed.
4. Use the committed [Understand graph](../.ua/knowledge-graph.json) to navigate
   the code only after checking its source checkpoint and freshness. Confirm
   important behavior in current code and canonical docs; the graph is a map,
   not a source of truth.
5. Run `python scripts/shared_knowledge_status.py` so the handoff starts with
   the same checkpoint and stale/current result for every collaborator.

## Keep the shared knowledge coherent

Each file has one job:

- `README.md` gives the short project orientation, boundary, setup, and links.
- `docs/GOAL-PROMPT.md` keeps the north star and execution constraints for a
  future contributor or chat.
- `docs/NEXT-WORK-HANDOFF.md` describes the live checkpoint, unresolved gates,
  and the exact next action. Update its current section when those change.
- `docs/UNDERSTANDING-LOG.md` is append-only work history. Add a dated entry
  with material changes, evidence, checks, limits, and the next gate; do not
  rewrite old results as if they were current.
- Contracts and accepted ADRs define behavior and owner decisions. `docs/research/`
  records sourced findings and uncertainty. `docs/evidence/` stores sanitized,
  reproducible outcomes.
- `.ua/knowledge-graph.json` is the generated source map; its tracked metadata
  and scan baseline make updates reproducible.

Never store chat transcripts, credentials, private BTC packets, raw local
runtime state, or unsourced guesses in shared knowledge. When a finding changes,
update its canonical document instead of adding a competing summary elsewhere.

## Close out each meaningful slice

Before the pull request is ready for review:

1. Update the canonical contract, decision, research, or evidence document that
   the work changes.
2. Refresh `NEXT-WORK-HANDOFF.md` with the current state and a concrete next
   action, and append a dated `UNDERSTANDING-LOG.md` entry. Update README when
   project orientation, setup, entry points, or product boundaries change; keep
   it short and link to detailed documents.
3. Refresh the Understand graph after meaningful source, architecture, file
   inventory, or contributor-documentation changes. Run `/understand
   --language en` for the incremental refresh. Use `/understand --full
   --language en` only if the graph/baseline is missing or invalid, or the scan
   rules changed. The repository's `.ua/config.json` keeps graph text in
   English.
4. Commit code and canonical documents first, then run Understand against that
   source commit. Review and commit the generated graph update in the same pull
   request. The graph checkpoint intentionally names the source commit it
   analyzed, not the later graph-only commit or merge commit.
5. Review the graph diff and confirm `project.gitCommitHash`, `meta.json`, and
   `fingerprints.json` agree; the scan covers the expected project files; every
   edge endpoint exists; and only the six documented shared `.ua/` files are
   staged. Keep `.ua/.trash-*`, intermediate batches, logs, credentials, and
   runtime data out of Git.

The status helper is deliberately read-only. It does not rewrite the graph or
silently stage files; the collaborator who changes source or canonical knowledge
owns the source commit, graph refresh, validation, and PR handoff.

If the Understand skill is unavailable, read the committed graph and continue
from source and canonical docs. Do not edit generated graph JSON by hand or
claim it is refreshed; note the limitation in the PR so a collaborator with
the skill can update it.

## Pull request handoff

Every PR should state its scope, canonical knowledge files updated, verification
actually run, and any unresolved boundary. Say whether the graph was refreshed
and identify its source checkpoint. Leave the branch and worktree clean after
the PR is merged; preserve other collaborators' uncommitted work.
