# Prompt for the next implementation chat

Copy the following prompt into a new Codex chat after reviewing the current repository state. The unified roadmap is in `docs/ROADMAP.md`; this prompt targets U3/B2.

```text
Start unified milestone U3/B2 in D:\Code\Github\Autonomous-Market-OS.

Use these documents as the source of truth:
- docs/ROADMAP.md
- docs/PHASES.md
- docs/TARGET-STRUCTURE.md
- docs/decisions/ADR-0017-unified-roadmap.md
- TECH_DOCS.md
- docs/BTC-PAPER-EXPERIMENT-ROADMAP.md
- docs/B0-BTC-PAPER-REPLAY-REPORT.md
- docs/B1-BTC-HISTORICAL-INGESTION-REPORT.md
- docs/UNDERSTANDING-LOG.md
- STACK.md

Read the repository AGENTS.md guidance and use the narrowest relevant skills. For coding work use ecc-harness, cautious-coding, and ponytail. Inspect the actual market_os code, tests, contracts, B0/B1 implementation, CLI, API, persistence, and evidence before editing. Preserve pre-existing .gitignore, README.md, .tmp-* directories, and unrelated changes. Never modify D:\Code\Github\company-projects.

Implement only U3/B2:
1. Materialize deterministic point-in-time BTCUSDT feature rows from the B1 canonical local dataset.
2. Materialize separate five-minute labels with explicit future-data lineage.
3. Define and validate warm-up, gap, stale-data, availability, and no-look-ahead outcomes.
4. Add hand-checkable features first; keep the set small and documented.
5. Add naïve and statistical numerical baselines before considering LightGBM. If LightGBM is not already justified by the current environment, leave it as a documented follow-up rather than adding speculative dependencies.
6. Use chronological train/calibration/test splits with a documented purge/embargo rule for overlapping five-minute labels.
7. Persist configurations, feature/label fingerprints, predictions, metrics, calibration results, split metadata, and artifact lineage.
8. Add read-only CLI/API inspection and deterministic replay evidence.
9. Update the unified roadmap, BTC roadmap, ADRs if needed, and docs/UNDERSTANDING-LOG.md.

Hard boundaries:
- Offline fixtures/local B1 data only; do not enable network ingestion.
- No Jev request, OpenAI request, hosted model, credentials, broker, live exchange endpoint, live trading, or virtual portfolio implementation in B2.
- Models are numerical experiment inputs only; deterministic policy and risk remain authoritative.
- Do not rename historical M/B reports or rewrite unrelated code.

Verification:
- Run focused B2 tests first, then the full suite.
- Run compileall, evidence JSON validation, secret/dependency checks, CLI/API smoke tests, replay/fingerprint checks, and git diff --check.
- Review the final diff and report exact tests, evidence, remaining risks, and the next unified milestone.
- Commit and push the completed work to origin/main, preserving unrelated unstaged changes. Include the commit SHA and remote verification in the final report.
```
