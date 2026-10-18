# Autonomous Market OS: Unified Roadmap

## Purpose

This is the forward roadmap for the fusion repository. It merges the original platform roadmap (`M0–M7`) and the BTC experiment roadmap (`B0–B7`) into one sequence (`U0–U8`). Historical milestone names remain valid in implementation reports and ADRs.

## Roadmap

| Milestone | Scope | Main result | Current state |
|---|---|---|---|
| U0 | M0–M1 | Foundation, contracts, Market OS orchestration ownership, persistence, recovery, and paper-only boundaries | Complete |
| U1 | M2 | Cited research, Vibe-Trading and LightRAG adapters, model-summary gate, quality benchmark, CI/CD | Built offline; M2.9 blocked on credential boundary |
| U2 | B0–B1 | BTCUSDT data contracts, fixture replay, canonical Parquet/DuckDB dataset, provenance, gaps, and stored replay | Complete offline |
| U3 | B2–B3 + M5 controls | Features, labels, numerical baselines, calibration, walk-forward evaluation, and Jev incremental-value benchmark | Next |
| U4 | M3 + B4 | Shared paper portfolio, virtual broker, costs, fills, risk, approvals, and shadow mode | Planned |
| U5 | M4 web + B5 | Web deployment and operator views over the shared API | Planned |
| U6 | M4 CLI/app + B6–B7 | Mature CLI, then desktop/mobile shell over the same contracts | Planned |
| U7 | M5 + selected M7 | Evaluation, education, reports, slides, media, and safe tool integrations | Planned selectively |
| U8 | M6 | Separate live-readiness review or explicit permanent paper mode | Deferred; no automatic live trading |

## Execution order

```text
U0 foundation
  -> U1 research platform
  -> U2 BTC data foundation
  -> U3 quantitative evaluation
  -> U4 paper portfolio
  -> U5 web operations
  -> U6 CLI and app surfaces
  -> U7 evaluation and artifact products
  -> U8 separate live-readiness decision
```

The immediate work is U3/B2. It must remain local, deterministic, and offline. It may reuse the B1 dataset and existing Market OS artifact, lineage, persistence, CLI, and API conventions. It must not wait for M2.9.

## U3/B2 next work

1. Read the repository guidance, unified phase documents, BTC technical specification, B0/B1 reports, ADRs, and existing feature/data code.
2. Materialize deterministic point-in-time features and separate five-minute labels from the B1 canonical dataset.
3. Define warm-up, gap, stale-data, and eligibility behavior as inspectable outcomes.
4. Implement naïve and statistical baselines before adding LightGBM.
5. Use chronological train/calibration/test splits with purge/embargo for overlapping labels.
6. Record predictions, calibration, metrics, configurations, fingerprints, and lineage.
7. Add read-only CLI/API inspection and reproducible evidence reports.
8. Keep Jev, hosted models, network ingestion, broker adapters, and live execution out of B2.

## Product surface order

```text
local engine -> web deployment -> CLI extension -> app shell
```

The web, CLI, and app must consume the same versioned backend contracts. They must not duplicate market calculations, policy, risk, portfolio accounting, or order logic.

## Non-negotiable boundaries

- Source repositories under `D:\Code\Github\company-projects` remain separate and untouched.
- Existing `.gitignore`, `README.md`, `.tmp-*` probe directories, and unrelated user changes remain preserved.
- No authenticated exchange endpoints, balances, orders, withdrawals, or live broker code are added by U0–U7.
- Model outputs are typed inputs to experiments or explanations; deterministic policy and risk remain authoritative.
- Every long-running action has events, artifacts, provenance, lineage, and replay evidence.

## Decision points

| Decision | Needed before |
|---|---|
| B1 public source terms, region, and retention authorization | Any network historical ingestion |
| Feature/label and evaluation configuration freeze | U3 final benchmark |
| Jev access, cost, semantics, and contamination treatment | U3/B3 adapter |
| Paper wallet, fees, slippage, and latency assumptions | U4 paper portfolio |
| Deployment/auth/observability policy | U5 web operations |
| App framework and supported platforms | U6 app shell |
| Live trading authorization and compliance review | U8 only |

## Evidence convention

Each unified milestone updates `docs/UNDERSTANDING-LOG.md`, adds or updates an ADR when a boundary changes, and writes machine-readable evidence under `docs/evidence/`. Reports must state what was implemented, what was verified, what remains unknown, and the exact next gate.
