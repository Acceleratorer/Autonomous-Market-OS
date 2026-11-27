# Shared knowledge maintenance

This repository is the shared memory for collaborators, coding agents, and
future chats. A fresh clone must contain enough context to continue without a
private chat, local notes, credentials, or runtime state.

## Canonical knowledge chain

Keep one source of truth for each kind of knowledge:

| Need | Canonical file | Update when |
| --- | --- | --- |
| Product boundary and short orientation | [`README.md`](../README.md) | setup, entry points, or product boundaries change |
| North star and constraints | [`GOAL-PROMPT.md`](GOAL-PROMPT.md) | the project goal or a hard constraint changes |
| Live checkpoint and next action | [`NEXT-WORK-HANDOFF.md`](NEXT-WORK-HANDOFF.md) | a gate closes, opens, or the next action changes |
| Durable decision or contract | [`decisions/`](decisions/) and the relevant contract | an owner-approved behavior or interface changes |
| Sourced finding | [`research/`](research/) | a provider, runtime, legal, or technical claim is checked |
| Reproducible result | [`evidence/`](evidence/) | a bounded run produces machine-checkable evidence |
| Append-only history | [`UNDERSTANDING-LOG.md`](UNDERSTANDING-LOG.md) | every meaningful slice closes |
| Code and document navigation | [`.ua/knowledge-graph.json`](../.ua/knowledge-graph.json) | source, architecture, or contributor docs change materially |

Do not create a competing summary when an existing canonical file can be
updated. Do not commit chat transcripts, private BTC packets, credentials,
local model state, or API responses containing sensitive data.

## Update cadence and close-out

Update the canonical file in the same pull request as the change it describes.
At the end of every meaningful slice:

1. Update the handoff with the current state, unresolved gates, and one
   concrete next action.
2. Append a dated entry to `UNDERSTANDING-LOG.md` with files, evidence,
   checks, limits, and the next gate.
3. Update `README.md` only when the stable orientation, setup, entry points, or
   product boundary changed; keep it short and link to detail.
4. Refresh the English Understand graph when source, architecture, file
   inventory, or contributor-facing documentation changed.

The graph is a generated map, not the authority for behavior. Verify important
claims against source and the canonical documents.

## Graph refresh sequence

Keep the graph checkpoint reproducible by separating source and generated
commits:

```powershell
# 1. Finish and commit source plus canonical knowledge first.
git status --short
git add <source-and-knowledge-files>
git commit -m "docs: update shared project knowledge"

# 2. From the new source commit, run the Understand incremental refresh.
#    In Codex use: /understand --language en

# 3. Review the generated six tracked files and validate the checkpoint.
python scripts/ci_checks.py validate-shared-knowledge
git diff --check
git status --short

# 4. Commit only the graph snapshot and its tracked baseline.
git add .ua/knowledge-graph.json .ua/meta.json .ua/fingerprints.json .ua/config.json .ua/.understandignore .ua/intermediate/scan-result.json
git commit -m "docs: refresh shared Understand graph"
```

Use `/understand --full --language en` only when the graph or baseline is
missing/invalid or the scan rules changed. Keep `.ua/.trash-*`, batch shards,
logs, temporary output, market data, private packets, and runtime state out of
Git. The validator fails when project files changed after the graph checkpoint,
when graph metadata disagrees, or when an edge points to a missing node.

## Dashboard and handoff for collaborators

The dashboard reads the committed graph but binds to the machine that starts
it. Each collaborator can clone or pull the repository and run
`/understand-dashboard` locally; the committed graph gives everyone the same
snapshot. Use the handoff and understanding log for progress visible in Git.
Do not expose the loopback dashboard or a live BTC/JeV packet stream as a
collaboration mechanism.

## Pull-request checklist

- [ ] Canonical contract, decision, research, or evidence file updated.
- [ ] `NEXT-WORK-HANDOFF.md` and `UNDERSTANDING-LOG.md` updated when the slice
      is meaningful.
- [ ] `README.md` updated when stable orientation or boundary changed.
- [ ] Understand graph refreshed from the committed source checkpoint.
- [ ] `python scripts/ci_checks.py validate-shared-knowledge` passes.
- [ ] PR description names the graph checkpoint, checks run, and unresolved
      provider/data boundaries.
