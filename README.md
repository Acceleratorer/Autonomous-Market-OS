# HKUDS Autonomous Market OS

The fusion repository for HKUDS market research, reproducible backtesting, paper trading, and later controlled execution.

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

See `docs/PRODUCT-VISION.md`, `docs/PHASES.md`, `docs/ROADMAP.md`, `docs/TARGET-STRUCTURE.md`, `docs/FUSION-MAP.md`, `docs/INTEGRATION-GUIDE.md`, and `docs/decisions/ADR-0001-phase-0.md` for the product boundary and next milestone.
