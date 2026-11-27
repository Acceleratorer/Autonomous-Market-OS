# Shared Understand Anything Graph

The committed snapshot under `.ua/` gives every contributor and coding agent the same source-derived map of Autonomous Market OS. It contains file, function, and class nodes; dependency and test edges; architectural layers; and a guided tour. It does not contain market candles, API credentials, private packets, or runtime data. The repository's project goal, decisions, research, and evidence remain the authoritative written knowledge; the graph helps people find and connect that material. Follow the [collaborator workflow](COLLABORATION-WORKFLOW.md) for the shared start, update, and pull-request routine.

## Shared files

These files are versioned so a fresh clone has both the current graph and the baseline needed for incremental updates:

- `.ua/knowledge-graph.json` — graph, layers, and tour.
- `.ua/meta.json` — analyzed source commit and graph version.
- `.ua/fingerprints.json` — structural fingerprints used to detect changed files.
- `.ua/intermediate/scan-result.json` — analyzed file inventory reused by incremental scans.
- `.ua/config.json` and `.ua/.understandignore` — output-language and scan rules.

Other `.ua/` files, including `.trash-*` directories, logs, and intermediate batch output, remain local scratch and are ignored by Git.

## Explore the shared graph

Open `.ua/knowledge-graph.json` in the repository, or use the Understand Anything skills with the repository as the current project:

The slash commands require Understand Anything installed in your Codex environment. See the [official Understand Anything project](https://github.com/Egonex-AI/Understand-Anything). A fresh clone can still inspect the committed JSON graph without installing the skills.

- `/understand-chat` asks questions against the shared graph.
- `/understand-explain` explains a file or module.
- `/understand-onboard` builds a newcomer guide.
- `/understand-dashboard` opens a local interactive view of the graph.

The dashboard URL uses `127.0.0.1`, so it is reachable only on the machine running it. Share the repository or a pull request for a common snapshot; each contributor can start their own dashboard from the committed graph.

## Keep team knowledge current

Use the project files as shared memory so work can continue across contributors,
agents, machines, and chats. Update the live handoff and append to the dated log
after each meaningful slice; update README when the stable orientation,
onboarding, setup, or project boundary changes:

- [`README.md`](../README.md) is the short orientation and project boundary.
- [`GOAL-PROMPT.md`](GOAL-PROMPT.md) records the north star and execution
  constraints; [`NEXT-WORK-HANDOFF.md`](NEXT-WORK-HANDOFF.md) records the active
  implementation checkpoint and immediate next steps.
- `docs/decisions/` holds durable owner-approved decisions. Contract documents
  define behavior. `docs/research/` holds dated source checks and uncertainty;
  `docs/evidence/` holds sanitized, reproducible results.
- `.ua/knowledge-graph.json` is a generated map of code and documentation, not
  a replacement for those source-of-truth records.

When a pull request changes behavior, architecture, a product boundary, a
decision, or a research conclusion, update the affected canonical document in
the same pull request. Add new evidence with its date, provenance, scope, and
limits. Do not copy chat history into the repository; retain the decisions and
facts future contributors need. Never put credentials, private BTC packets, or
local runtime data into graph or knowledge artifacts.

## Refresh and review

After meaningful source, architecture, or contributor-facing documentation
changes, update the current branch and run `/understand` from the repository.
It uses the committed metadata and fingerprints for an incremental refresh. Use
`/understand --full` only when the existing graph/baseline is missing or
invalid, or the scan rules changed enough to require a full rebuild.

To keep the graph's source checkpoint accurate, commit the code and canonical
documentation changes first, then run `/understand` against that commit. Review
the graph diff alongside the source diff and commit the generated updates to the
same pull request, usually as a second commit. The tracked files are the six
paths listed above. Do not add `.ua/.trash-*`, batch fragments, temporary logs,
market data, private packets, or credentials.

The generated graph records its analyzed commit in `project.gitCommitHash`;
`meta.json` and `fingerprints.json` should refer to that same source revision.
The graph itself is ignored by source-freshness comparison, so a commit that
only updates generated graph artifacts does not trigger another full analysis.
Before merging, check graph/meta/fingerprint commit agreement, complete file
coverage, resolved edge endpoints, and `git diff --check`. If the Understand
skill is not installed, the committed JSON remains available to read; record
that refresh limitation in the pull request so a maintainer can regenerate it.
