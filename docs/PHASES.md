# Autonomous Market OS: Unified Phases

This document replaces the separate forward M-phase and B-phase sequences with one delivery sequence. The historical labels remain in ADRs, reports, commits, and evidence so older work remains traceable.

## Naming

- `M0–M7` are the original platform roadmap labels.
- `B0–B7` are the BTC quantitative experiment labels.
- `U0–U8` are the unified forward milestones used for new work.

The original roadmap has eight M phases (`M0` through `M7`). It does not need additional M phases. Future work uses the unified U milestones below.

## Unified phase map

| Unified phase | Historical work | Outcome | Status |
|---|---|---|---|
| U0 — Foundation and ownership | M0–M1 | Product boundary, repository ownership, contracts, orchestration, persistence, recovery, and paper-only enforcement | Complete |
| U1 — Research platform | M2, including M2.1–M2.9 | Cited research, retrieval, backtesting adapters, model boundary, quality gates, and offline CI | Built; M2.9 live smoke remains blocked and isolated |
| U2 — Quantitative data foundation | B0–B1 | BTCUSDT closed-candle contracts, historical dataset storage, manifests, lineage, gaps, deduplication, deterministic replay, and source-readiness authorization | Complete offline; network authorization pending |
| U3 — Quantitative evaluation | B2–B3; selected M5 controls; API connectivity | Deterministic features and labels, numerical baselines, calibration, walk-forward evaluation, controlled Jev comparison, and bounded read-only provider connectivity | Implemented offline; B3 not promoted |
| U3 synthetic surfaces | B3.8–B3.14 | Synthetic session artifacts, local API/dashboard, catalog/comparison, CLI inspection, and acceptance harness | Complete locally; synthetic-only |
| U4 — Paper portfolio | M3 + B4 | Shared virtual broker, portfolio ledger, costs, fills, risk policy, approvals, and paper-only shadow mode | B4.17 formalizes indefinite local retention, validated non-destructive backup, and fail-closed archive/preflight integrity; deletion and schema transformation remain separate gates |
| U5 — Web operations | M4 web + B5 | Web deployment of the existing API with BTC data, experiment, report, and paper-portfolio views | U5.23 and the local exit gate are complete on the TypeScript/React/Node.js/Next.js/Tailwind operator. Continue only with a defined loopback-local slice; connected access remains gated. DirectAdmin static deployment is selected but has not run and still needs its documented host prerequisites |
| U6 — CLI and app surfaces | B6–B7 + M4 CLI/app | One versioned CLI and thin desktop/mobile shells using the shared API | Planned |
| U7 — Evaluation and artifact products | M5 + selected M7 | Cost/quality reports, education, slides, media, and tool integrations that consume stable artifacts | Planned, selective |
| U8 — Live readiness or permanent paper mode | M6 | A separate security, compliance, broker, reconciliation, and approval gate; paper mode may remain the permanent decision | Deferred; never automatic |

## Phase rules

1. Complete the local deterministic engine before web deployment.
2. Build one shared paper portfolio and risk engine; BTC is its first quantitative consumer.
3. Treat Jev and hosted models as optional experimental providers. They never own policy, risk, persistence, or execution.
4. Keep the existing cited research lane and BTC quantitative lane separate at the model boundary, then join them through versioned artifacts and evidence.
5. Add a surface only after its backend contracts and replay behavior are stable.
6. A negative or inconclusive quantitative result is an accepted outcome.
7. Live trading is outside the normal sequence and requires a new explicit decision record.

## Current position

- U0 is complete.
- U1 is built through offline M2.8 preparation; M2.9 remains blocked by the missing approved credential and is not a dependency for BTC work.
- U2 is complete offline with B1's network transport still disabled. The U3/B1 readiness gate defines a 30-day, 44-page proposal but does not authorize historical requests.
- U3 includes deterministic B2/B3 evaluation, the bounded U3/API connectivity slice, and the B3.8–B3.14 local synthetic surfaces. B2/B3/U3-API and the synthetic acceptance stack are implemented offline; B3 is not promoted because the shipped fixture has no leakage-safe labels. B4.1–B4.17 local hardening slices are implemented and reviewed; B4.15 adds shared membership, B4.16 confirms lifecycle semantics, and B4.17 formalizes retention/archive integrity. U4/B4 remains open for authenticated externally exposed mutation API, retention deletion, and migration transformation. Keep U4/B4 paper-only local until its exit gate is resolved.
- U5 has local HTML and Next.js read-only portfolio surfaces and bounded BTC dataset, candle, ingestion-manifest, B1 ingestion-record, and B2/B3 research pages. U5.9–U5.10 bound order, risk, member, and reservation pages; U5.11 adds bounded catalog, fills, approvals, and ledger resources and rejects the HTTP full-snapshot export. U5.12 removes the duplicate freshness read from risk and ledger pages; U5.13 streams freshness validation while preserving JSON record contents and full-file UTF-8 checks; U5.14 filters later-page names before sorting. U5.15 adds BTC history metadata pages without initializing an empty store or reading Parquet files. U5.16 adds exclusive-cursor candle pages with streamed Parquet hash checks. U5.17 adds paged manifest summaries and hash-checked, capped detail. U5.18 adds bounded, hash-checked B2/B3 metrics and report views. U5.19 adds bounded outcome, gap, and provenance pages. U5.20 adds a local overview that reads bounded previews from the existing validated catalogs and links to those pages. U5.21 adds a static candlestick visualization for only the current page while retaining the exact OHLCV table. U5.22 adds a v3 portfolio aggregate with the latest 100 broker-recorded equity samples, exact returned-page extrema, and a static line chart plus exact table. U5.23 completes responsive and keyboard navigation across five viewport widths. Full cold recovery stays intact. Directory enumeration and per-portfolio recovery remain linear, candle reads rehash the file per page, and manifests/results fail closed at their byte caps. Connected deployment remains gated on a concrete target, identity, tenant isolation, sessions, rate limits, audit, backup, rollback, observability, and operator access decisions.

## Exit gates

- U0: contracts, ownership, recovery, and paper-only tests pass.
- U1: cited research and adapter workflows replay with evidence and CI checks.
- U2: canonical BTC data replays identically with explicit quality outcomes.
- U3: frozen chronological evaluation, leakage checks, calibration, baseline reports, bounded provider connectivity, and the historical-data readiness decision exist.
- U4: virtual fills, accounting, costs, and risk replay identically with no live path.
- U5: deployment artifact, auth boundary, observability, recovery, and paper-only behavior are verified; static artifact readiness alone does not authorize public deployment.
- U6: CLI and app use the same API/contracts and own no domain or risk logic.
- U7: every added artifact workflow has lineage, permissions, and bounded resource use.
- U8: only a separately approved live-readiness review can change the execution boundary.

The local-first exit gate is recorded in `docs/LOCAL-EXIT-GATE-REPORT.md`: 546 tests passed, local Python/Next.js checks passed, and the pushed GitHub CI/security workflows passed. U5.5 connected access remains deferred until identity, authorization, isolation, and operations boundaries are defined. The disconnected DirectAdmin preview has a selected target but no deployment has run; host prerequisites remain.
