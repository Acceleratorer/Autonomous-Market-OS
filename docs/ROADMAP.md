# Autonomous Market OS: Unified Roadmap

## Purpose

This is the forward roadmap for the fusion repository. It merges the original platform roadmap (`M0–M7`) and the BTC experiment roadmap (`B0–B7`) into one sequence (`U0–U8`). Historical milestone names remain valid in implementation reports and ADRs.

## Roadmap

| Milestone | Scope | Main result | Current state |
|---|---|---|---|
| U0 | M0–M1 | Foundation, contracts, Market OS orchestration ownership, persistence, recovery, and paper-only boundaries | Complete |
| U1 | M2 | Cited research, Vibe-Trading and LightRAG adapters, model-summary gate, quality benchmark, CI/CD | Built offline; M2.9 blocked on credential boundary |
| U2 | B0–B1 | BTCUSDT data contracts, fixture replay, canonical Parquet/DuckDB dataset, provenance, gaps, stored replay, and historical-data readiness gate | Complete offline; historical source authorization pending |
| U3 | B2–B3 + M5 controls + API connectivity | Features, labels, numerical baselines, calibration, walk-forward evaluation, controlled Jev comparison, and bounded provider connectivity | B2/B3/U3-API implemented offline; B3 not promoted |
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

U3/B2 is complete offline. It remained local, deterministic, and offline, reused the B1 dataset and existing Market OS artifact, lineage, persistence, CLI, and API conventions, and did not wait for M2.9. U3/B3 is implemented as an offline controlled Jev-shaped benchmark and is not promoted because the shipped fixture has no leakage-safe labels. U3/API adds fixture-first public Binance and optional Jev connectivity with explicit live probes; the U3/B1 readiness gate now defines the bounded historical proposal but does not authorize or execute ingestion. U4/B4 and U5/B5 remain unstarted.

The B1 readiness defect-closure milestone confirmed and fixed exclusive observed-end semantics, checkpoint identity/hash/lineage validation, and exact source-decimal retention in B1 canonical storage. The Binance historical transport remains intentionally hard-disabled behind a separate enablement review; no B1 acquisition was performed. Current regenerated synthetic identities are authoritative in the B1/B2/B3 evidence records.

## U3/B2 implementation result

1. Materialized deterministic point-in-time features and separate five-minute labels from hash-checked B1 canonical rows.
2. Defined inspectable warm-up, gap, stale, unavailable, invalid, and eligibility outcomes.
3. Added naïve 0.5, empirical-rate, and conditional-rate baselines before any LightGBM dependency.
4. Added chronological train/calibration/test split metadata with five-minute purge and embargo.
5. Persisted config, features, labels, predictions, metrics, calibration, split, lineage, and replay fingerprints.
6. Added read-only `btc-paper b2` CLI and `/v1/btc/b2` API routes.
7. The shipped B1 fixture has no leakage-safe labeled samples because its feature-eligible rows reach the documented gap; metrics are explicitly unavailable. Evidence is in `docs/evidence/u3-b2-btc-features-baselines.json`.
8. Keep broker adapters, portfolio mutation, and live execution out of U3/API; provider connectivity is bounded and read-only.
9. B3 is not promoted. U3/API evidence must be reviewed before any separate U4/B4 decision; U5/B5 remains untouched.

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
| B1 public source terms, region, retention, and explicit bounded-run approval | Any network historical ingestion |
| Feature/label and evaluation configuration freeze | U3 final benchmark |
| Jev access, cost, semantics, and contamination treatment | U3/B3 adapter |
| Paper wallet, fees, slippage, and latency assumptions | U4 paper portfolio |
| Deployment/auth/observability policy | U5 web operations |
| App framework and supported platforms | U6 app shell |
| Live trading authorization and compliance review | U8 only |

## Evidence convention

Each unified milestone updates `docs/UNDERSTANDING-LOG.md`, adds or updates an ADR when a boundary changes, and writes machine-readable evidence under `docs/evidence/`. Reports must state what was implemented, what was verified, what remains unknown, and the exact next gate.
