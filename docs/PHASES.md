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
| U2 — Quantitative data foundation | B0–B1 | BTCUSDT closed-candle contracts, historical dataset storage, manifests, lineage, gaps, deduplication, and deterministic replay | Complete offline |
| U3 — Quantitative evaluation | B2–B3; selected M5 controls | Deterministic features and labels, numerical baselines, calibration, walk-forward evaluation, and controlled Jev comparison | B2 complete offline; B3 next |
| U4 — Paper portfolio | M3 + B4 | Shared virtual broker, portfolio ledger, costs, fills, risk policy, approvals, and paper-only shadow mode | Planned |
| U5 — Web operations | M4 web + B5 | Web deployment of the existing API with BTC data, experiment, report, and paper-portfolio views | Planned |
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
- U2 is complete with B1's network transport still disabled.
- U3 starts with B2: deterministic feature/label materialization and chronological numerical baselines. B2 is complete offline; B3 is the next gate.

## Exit gates

- U0: contracts, ownership, recovery, and paper-only tests pass.
- U1: cited research and adapter workflows replay with evidence and CI checks.
- U2: canonical BTC data replays identically with explicit quality outcomes.
- U3: frozen chronological evaluation, leakage checks, calibration, and baseline reports exist.
- U4: virtual fills, accounting, costs, and risk replay identically with no live path.
- U5: deployment, auth boundary, observability, recovery, and paper-only behavior are verified.
- U6: CLI and app use the same API/contracts and own no domain or risk logic.
- U7: every added artifact workflow has lineage, permissions, and bounded resource use.
- U8: only a separately approved live-readiness review can change the execution boundary.
