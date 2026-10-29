# Autonomous Market OS: Unified Roadmap

## Purpose

This is the forward roadmap for the fusion repository. It merges the original platform roadmap (`M0–M7`) and the BTC experiment roadmap (`B0–B7`) into one sequence (`U0–U8`). Historical milestone names remain valid in implementation reports and ADRs.

## Roadmap

| Milestone | Scope | Main result | Current state |
|---|---|---|---|
| U0 | M0–M1 | Foundation, contracts, Market OS orchestration ownership, persistence, recovery, and paper-only boundaries | Complete |
| U1 | M2 | Cited research, Vibe-Trading and LightRAG adapters, model-summary gate, quality benchmark, CI/CD | Built offline; M2.9 blocked on credential boundary |
| U2 | B0–B1 | BTCUSDT data contracts, fixture replay, canonical Parquet/DuckDB dataset, provenance, gaps, stored replay, and historical-data readiness gate | Complete offline; historical source authorization pending |
| U3 | B2–B3 + M5 controls + API connectivity | Features, labels, numerical baselines, calibration, walk-forward evaluation, controlled Jev comparison, and bounded provider connectivity | Implemented offline; B3 not promoted |
| U3 synthetic surfaces | B3.8–B3.14 | Deterministic session artifacts, local read-only API/dashboard, catalog/comparison, CLI inspection, and acceptance harness | Complete locally; synthetic-only |
| U4 | M3 + B4 | Shared paper portfolio, virtual broker, costs, fills, risk, approvals, and shadow mode | B4.17 formalizes indefinite local retention and validated non-destructive backup; deletion, authenticated mutation API, and schema transformation remain separate gates |
| U5 | M4 web + B5 | Web deployment and operator views over the shared API | U5.22 adds bounded local portfolio equity history with exact values preserved. The owner selected the TypeScript/React/Node.js/Next.js/Tailwind stack and a private single-tenant preview scope. Its host, identity, authorization, isolation, and operations decisions still gate connected access |
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

U3/B2 is complete offline. It remained local, deterministic, and offline, reused the B1 dataset and existing Market OS artifact, lineage, persistence, CLI, and API conventions, and did not wait for M2.9. U3/B3 is implemented as an offline controlled Jev-shaped benchmark and is not promoted because the shipped fixture has no leakage-safe labels. U3/API adds fixture-first public Binance and optional Jev connectivity with explicit live probes; the U3/B1 readiness gate defines the bounded historical proposal but does not authorize or execute ingestion. B3.8–B3.14 complete the local synthetic session, inspection, catalog, comparison, and acceptance surfaces. B4.1–B4.17 are implemented as synthetic local hardening slices; application surfaces are organized under `apps/` while `market_os` remains the compatibility/domain package. U5.2 verifies a deterministic static artifact with an exact file set and no script/network/credential boundary. U5.5 preserves the static and local shell boundaries and defines the authenticated connected-web gate; the owner has now selected a private single-tenant preview scope and Next.js stack, while its host and identity provider/login method remain open. Retention deletion and migration transformation remain separate U4/B4 gates. Keep U4/B4 paper-only local and hold public U5 deployment until an explicit follow-up gate resolves those gaps.

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
9. B3 is not promoted. U3/API evidence was reviewed before U4/B4; U5 now has a local read-only dashboard and remains outside deployment/shared-access scope.

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
| Jev provider access, cost, retention, and privacy policy | Any future B3.1 provider integration or context egress; requires separate approval |
| Paper wallet, fees, slippage, and latency assumptions | U4 paper portfolio |
| [B4.1 owner-decision worksheet](B4.1-OWNER-DECISION-WORKSHEET.md): approved portfolio identity, matching, risk, approval, persistence, and inspection decisions | U4/B4 implementation |
| [B4.2 ledger and recovery integrity](B4.2-LEDGER-RECOVERY-INTEGRITY.md): persisted snapshot/checkpoint validation and limit-price enforcement | Any later B4 persistence or shared-portfolio surface |
| [B4.3 event identity invariants](B4.3-EVENT-IDENTITY-INVARIANTS.md): unique synthetic market-event IDs and no-op duplicate retries | Any later B4 replay or event-ingestion surface |
| [B4.4 idempotency scope invariants](B4.4-IDEMPOTENCY-SCOPE-INVARIANTS.md): command-type-scoped retry identity and recovery uniqueness | Any later B4 command or shared-portfolio surface |
| [B4.5 malformed-ledger recovery](B4.5-LEDGER-MALFORMED-TAIL.md): typed fail-closed handling for invalid UTF-8, JSON, and record shape | Any later B4 persistence or recovery surface |
| [B4.6 malformed persisted metadata](B4.6-MALFORMED-PERSISTED-METADATA.md): typed fail-closed handling for genesis, policy, and checkpoint metadata | Any later B4 persistence or recovery surface |
| [B4.7 malformed snapshot recovery](B4.7-MALFORMED-SNAPSHOT-RECOVERY.md): typed fail-closed handling for persisted order and fill records | Any later B4 persistence or recovery surface |
| [B4.8 snapshot scalar validation](B4.8-SNAPSHOT-SCALAR-VALIDATION.md): typed fail-closed handling for numeric, cursor, timestamp, and history shapes | Any later B4 persistence or recovery surface |
| [B4.9 risk and audit outcomes](B4.9-RISK-AUDIT-OUTCOMES.md): deterministic rejection reason codes and idempotent audit records | Any later B4 risk or command surface |
| [B4.11 backup and restore](B4.11-BACKUP-RESTORE.md): opt-in local archive validation and broker-checked restore | Any retention/archive or schema migration surface |
| [B4.12 migration preflight](B4.12-MIGRATION-PREFLIGHT.md): read-only schema compatibility classification and fail-closed recovery guard | Any versioned schema transformer |
| [B4.13 local concurrency contract](B4.13-CONCURRENCY-CONTRACT.md): isolated portfolios, one-writer locking, stale-writer rejection, and reload recovery | Any shared portfolio or distributed ownership surface |
| [B4.14 mutation audit contract](B4.14-MUTATION-AUDIT-CONTRACT.md): typed local command rejection, replay, and conflict audit | Any externally exposed mutation API |
| [B4.15 shared portfolio contract](B4.15-SHARED-PORTFOLIO-CONTRACT.md): immutable membership, reservations, local serialization, retries, and recovery | Any expansion of shared portfolio or external access |
| [B4.16 lifecycle contract](B4.16-LIFECYCLE-CONTRACT.md): full fills, accepted-order FIFO, reservation release, and disabled expiry | Any partial-fill or order-expiry expansion |
| [B4.17 retention/archive contract](B4.17-RETENTION-ARCHIVE-CONTRACT.md): indefinite ledger retention, validated copy, and fail-closed incomplete stores | Any pruning, deletion, remote archive, or schema transformation |
| [U5.1 local service boundary](U5.1-LOCAL-SERVICE-BOUNDARY.md): loopback bind/Host checks, pre-listener recovery, and query-free audit paths | Shared U5 deployment/auth/observability |
| [U5.2 static deployment readiness](U5.2-STATIC-DEPLOYMENT-READINESS.md): exact file set, parity, deterministic packaging, and no-script/no-network/no-credential checks | Separate deployment target and access policy |
| [U5.3 deployment/access/observability](U5.3-DEPLOYMENT-ACCESS-OBSERVABILITY-CONTRACT.md): artifact manifests and local request correlation | Separate authenticated connected-web contract |
| [U5.4 local operator shell](U5.4-LOCAL-OPERATOR-SHELL.md): GET-only browser consumer of B4 summary inspection | Separate authenticated connected-web contract |
| [U5.5 web stack and authenticated connected-web gate](U5.5-AUTHENTICATED-CONNECTED-WEB-CONTRACT.md): private single-tenant scope, identity propagation, storage isolation, sessions, and observability criteria | Concrete deployment target, identity/login method, and verified principal path |
| [U5.6 local portfolio inspection](U5.6-LOCAL-PORTFOLIO-INSPECTION.md): browser parity for shared membership, reservations, orders, and risk audit | Concrete deployment target and identity boundary |
| [U5.7 web stack and deployment matrix](U5.7-WEB-STACK-DEPLOYMENT-MATRIX.md): framework and deployment selection rules | Choose deployment target, identity, and interaction scope |
| [U5.16 bounded BTC candle detail](U5.16-NEXT-BOUNDED-BTC-CANDLE-DETAIL.md): fixed-store read-only candle pages with an exclusive UTC cursor and streamed Parquet hash validation | Separate bounded contracts for manifests and experiment/report views |
| [U5.17 bounded BTC ingestion manifests](U5.17-NEXT-BOUNDED-BTC-INGESTION-MANIFESTS.md): fixed-store manifest catalog pages and hash-checked, 8 MiB-capped detail | Outcome/gap/provenance pages added in U5.19 |
| [U5.18 bounded BTC research inspection](U5.18-NEXT-BOUNDED-BTC-RESEARCH-INSPECTION.md): fixed-store B2/B3 run catalogs and hash-checked, 256 KiB-capped metrics/report details | Outcome/gap/provenance pages added in U5.19 |
| [U5.19 bounded BTC ingestion records](U5.19-NEXT-BOUNDED-BTC-INGESTION-RECORDS.md): fixed-store outcome, gap, and raw-provenance pages with bounded cursors and payload previews | Local BTC detail is complete; connected deployment still needs U5.5 decisions |
| [U5.20 local operator overview](U5.20-LOCAL-OPERATOR-OVERVIEW.md): bounded first-page previews across portfolios, BTC datasets, and B2/B3 research | Local surfaces are connected from one overview; choose the next product surface or resolve the U5.5 deployment gate |
| [U5.21 bounded BTC candle visualization](U5.21-BOUNDED-BTC-CANDLE-VISUALIZATION.md): static SVG for the current hash-checked page, with exact OHLCV values preserved below | Choose the next local product surface or resolve the U5.5 deployment gate |
| [U5.22 bounded portfolio equity history](U5.22-BOUNDED-PORTFOLIO-EQUITY-HISTORY.md): latest 100 retained broker equity samples, with exact values and a static local chart | Choose the next local product surface or resolve the U5.5 deployment gate |
| Deployment/auth/observability policy | U5 web operations |
| App framework and supported platforms | U6 app shell |
| Live trading authorization and compliance review | U8 only |

## Evidence convention

Each unified milestone updates `docs/UNDERSTANDING-LOG.md`, adds or updates an ADR when a boundary changes, and writes machine-readable evidence under `docs/evidence/`. Reports must state what was implemented, what was verified, what remains unknown, and the exact next gate.
