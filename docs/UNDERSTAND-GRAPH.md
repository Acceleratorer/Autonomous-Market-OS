# Shared Understand Anything Graph

The committed snapshot under `.ua/` gives every contributor the same source-derived map of Autonomous Market OS. It contains file, function, and class nodes; dependency and test edges; architectural layers; and a guided tour. It does not contain market candles, API credentials, or runtime data.

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

## Refresh and review

After meaningful source or architecture changes, update the current branch and run `/understand` from the repository. It uses the committed metadata and fingerprints for an incremental refresh. Use `/understand --full` when a complete rebuild is needed.

Review the graph diff with the source changes, then commit the generated updates to the same pull request or a focused graph-refresh pull request. The tracked files are the six paths listed above. Do not add `.ua/.trash-*`, batch fragments, temporary logs, market data, or credentials.

The generated graph records its analyzed commit in `project.gitCommitHash`; `meta.json` and `fingerprints.json` should refer to the same source revision. The graph itself is ignored by source-freshness comparison, so a commit that only updates generated graph artifacts does not trigger another full analysis.
