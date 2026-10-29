# Autonomous Market OS

## Workspace layout

This repository is the separate fusion project. The original HKUDS repositories live under `company-projects/` and remain independent Git repositories with their own histories, branches, dependencies, and working changes.

```text
HKUDS/
├── company-projects/        # Original repositories; do not merge into this Git history
│   ├── AI-Trader/
│   ├── ClawWork/
│   ├── CLI-Anything/
│   ├── DeepCode/
│   ├── DeepTutor/
│   ├── LightRAG/
│   ├── MiniRAG/
│   ├── nanobot/
│   ├── OpenHarness/
│   ├── Paper2Slides/
│   ├── RAG-Anything/
│   ├── Vibe-Trading/
│   └── ViMax/
├── market_os/               # Fusion product implementation; see STRUCTURE.md
├── apps/                    # thin web, CLI, and gateway surfaces
├── docs/                    # Fusion plans, decisions, and evidence
└── pyproject.toml
```

The fusion project consumes the original repositories through adapters and documented contracts. It does not own their source trees.

This is a personal project for market research, reproducible backtesting, paper trading, and later controlled execution.

This repository owns the shared contracts, workflow orchestration boundary, persistence model, CLI, and service API. The source projects remain independent repositories and are connected through narrow adapters:

- `Vibe-Trading`: research and backtesting
- `LightRAG` / `RAG-Anything`: retrieval and document understanding
- `AI-Trader`: signals and paper execution
- `OpenHarness`: proposed orchestration runtime
- `nanobot` / `DeepCode`: future runtime and channel adapters

## Current Slice

The Phase 0 slice runs a deterministic US equities/ETF workflow:

1. Create a research task.
2. Retrieve timestamped market and document evidence.
3. Produce cited research.
4. Run a reproducible backtest.
5. Create a paper-only order plan.
6. Apply risk checks.
7. Persist events and artifacts.
8. Expose the workflow through the CLI and service API.

Live execution is disabled in `market-os.v1`.

## Checks

```text
python -m pytest -q market_os/tests
python -m compileall -q market_os
```

See `STRUCTURE.md`, `docs/PRODUCT-VISION.md`, `docs/PHASES.md`, `docs/ROADMAP.md`, `docs/TARGET-STRUCTURE.md`, `docs/APP-SURFACES-CONTRACT.md`, `docs/WEB-STACK-OPTIONS.md`, `docs/U5.5-AUTHENTICATED-CONNECTED-WEB-CONTRACT.md`, `docs/U5.2-STATIC-DEPLOYMENT-READINESS.md`, `docs/FUSION-MAP.md`, `docs/INTEGRATION-GUIDE.md`, and `docs/decisions/ADR-0001-phase-0.md` for the product boundary and next milestone.

The current web surface is a static, read-only paper-only preview. Build it
with `python scripts/build_web_artifact.py --output <new-directory>`; public
deployment and authenticated access remain separate gates.
