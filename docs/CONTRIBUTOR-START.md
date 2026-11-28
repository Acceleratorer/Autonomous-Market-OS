# Contributor start packet

This packet is the shortest path for a new human, coding agent, or later chat
to reach the same project context. Git is the shared memory; a private chat,
local model, or machine-specific dashboard is never the source of truth.

## Start from a fresh clone or pull

```powershell
git switch main
git pull --ff-only
python scripts/shared_knowledge_status.py
python scripts/ci_checks.py validate-shared-knowledge
```

Then read these files in order:

1. [`README.md`](../README.md) — boundary, setup, and entry points.
2. [`GOAL-PROMPT.md`](GOAL-PROMPT.md) — north star and hard constraints.
3. [`NEXT-WORK-HANDOFF.md`](NEXT-WORK-HANDOFF.md) — current checkpoint and next gate.
4. The newest entry in [`UNDERSTANDING-LOG.md`](UNDERSTANDING-LOG.md) — recent evidence and limits.
5. The relevant contract, ADR, research note, or evidence record for the slice.

Use the committed [Understand graph](../.ua/knowledge-graph.json) to find the
code path and related documents. Run `/understand-dashboard` locally when a
visual graph helps; the dashboard is local to the machine that starts it.
Important behavior must still be checked against source and canonical docs.

## Keep knowledge in Git

Each fact has one home:

| Fact | Update |
| --- | --- |
| Product orientation or setup | [`README.md`](../README.md) |
| Goal and constraints | [`GOAL-PROMPT.md`](GOAL-PROMPT.md) |
| Current state and next action | [`NEXT-WORK-HANDOFF.md`](NEXT-WORK-HANDOFF.md) |
| Durable behavior or owner decision | `docs/decisions/` and the relevant contract |
| Sourced external finding | `docs/research/` |
| Reproducible run | `docs/evidence/` |
| Append-only history | [`UNDERSTANDING-LOG.md`](UNDERSTANDING-LOG.md) |
| Code and document navigation | `.ua/knowledge-graph.json` and its tracked baselines |

Do not add chat transcripts, credentials, private BTC packets, local model
state, or unsourced guesses. Update the existing canonical file when a fact
changes instead of creating a competing summary.

## Close a meaningful slice

1. Update the canonical knowledge file, the handoff, and the understanding log.
2. Update `README.md` only when stable orientation, setup, entry points, or the
   product boundary changed.
3. Commit source and canonical knowledge first.
4. Refresh the English graph from that source commit with
   `/understand --language en`.
5. Review and commit the tracked graph snapshot and baseline files.
6. Run `python scripts/ci_checks.py validate-shared-knowledge` and
   `git diff --check` before opening the PR.

The graph checkpoint must name the source commit it analyzed. A graph-only
commit is expected; do not edit generated graph JSON by hand. The exact file
allowlist, refresh rules, and failure behavior are in
[`KNOWLEDGE-MAINTENANCE.md`](KNOWLEDGE-MAINTENANCE.md).

## PR handoff

Every PR should state the canonical files changed, the graph source checkpoint,
checks actually run, and any unresolved gate. The repository PR template keeps
this visible so the next collaborator can continue from Git without asking for
private context.
