# Autonomous Market OS: Project Context

**Purpose:** This is the handoff file for continuing work in a new chat. Read it first, then follow the linked roadmap and milestone contract for the active task.

## Current position

- Repository: `D:\Code\Github\HKUDS\Autonomous-Market-OS`.
- Baseline commit: `4ceb712f0a43b768e84c21e65408da832cbe4100` (`HEAD == origin/main` before the current uncommitted work).
- B3 remains offline, fixture-backed, recorded-response-only where applicable, and not promoted.
- B3.8–B3.14 form a local synthetic observability stack: session artifacts, loopback read-only API/dashboard, catalog and comparison, CLI inspection, and the cross-surface acceptance harness.
- The current worktree contains uncommitted B3.10–B3.14 changes and unrelated pre-existing files. Preserve all unrelated entries.
- The current architectural milestone is the U4/B4 closeout gate. Its contract and recommended defaults were approved on 2026-10-26; implementation remains authorized only within the synthetic, paper-only boundary.
- The B4.1 slice now provides a persisted synthetic broker domain in `market_os/b41_broker.py`, focused tests, and read-only CLI/API inspection. B4.2 hardens ledger/checkpoint recovery integrity and limit-price enforcement; B4.3 hardens unique market-event identity; B4.4 hardens command idempotency scope; B4.5 makes malformed ledger records fail closed with a typed recovery error; B4.6 does the same for malformed persisted metadata; B4.7 does the same for malformed persisted order/fill snapshots; B4.8 validates snapshot scalar and cursor shapes; B4.9 records deterministic risk and approval rejection outcomes. None exposes mutation routes or provider paths.
- The 2026-10-27 B4 local-slice closeout review found B4.1–B4.9 hardening complete and reproduced a market-order fill-time risk gap. B4.10 now closes that local gap with terminal, audited, cursor-advancing rejection outcomes. The first local U5 read-only dashboard is documented in [U5-LOCAL-READONLY-DASHBOARD.md](U5-LOCAL-READONLY-DASHBOARD.md). Remaining completion gaps are partial fills/expiry, shared-portfolio concurrency, mutation API, and backup/retention/migration. See [B4-LOCAL-SLICE-CLOSEOUT-REPORT.md](B4-LOCAL-SLICE-CLOSEOUT-REPORT.md). Keep U4/B4 paper-only local; do not treat it as a closed shared-portfolio milestone.

## Completed local synthetic stack

| Milestone | Result | Evidence |
|---|---|---|
| B3.8 | Deterministic synthetic session artifacts | `market_os/b38_synthetic_session.py` |
| B3.9 | Read-only local synthetic API and HTML session dashboard | `market_os/b39_synthetic_api.py` |
| B3.10 | Loopback-only server with fixed-root, query-free, read-only routes | `market_os/b310_synthetic_server.py` |
| B3.11 | Deterministic session catalog and right-minus-left comparison | `market_os/b311_synthetic_catalog.py` |
| B3.12 | HTML catalog and comparison dashboard links | `market_os/b310_synthetic_server.py` |
| B3.13 | CLI catalog and comparison inspection | `market_os/cli.py` |
| B3.14 | Cross-surface acceptance harness for CLI, HTTP, HTML, tamper, replay, and write boundaries | `market_os/tests/test_b314_synthetic_acceptance.py` |

The B3.14 acceptance suite verifies that CLI JSON and HTTP JSON describe the same validated artifacts, HTML links resolve to the same sessions, inspection does not replay or mutate artifacts, tampering fails closed, query parameters and POST are rejected, path boundaries are enforced, and untrusted labels are escaped.

## Active milestone: U5 local read-only dashboard

Read [B4.1-PAPER-PORTFOLIO-VIRTUAL-BROKER-CONTRACT.md](B4.1-PAPER-PORTFOLIO-VIRTUAL-BROKER-CONTRACT.md) before any B4 implementation. It defines the approved synthetic BTCUSDT Spot, long-only portfolio and virtual broker boundary. The owner-approved choices are recorded in the [B4.1 owner-decision worksheet](B4.1-OWNER-DECISION-WORKSHEET.md).

Human decisions recorded before B4 code:

1. Portfolio identity scope and initial synthetic wallet, including whether initial BTC inventory is allowed.
2. Fee, spread, slippage, mark-price, precision, rounding, quantity-step, and minimum-notional rules.
3. Market/limit matching, full versus partial fills, queue priority, cancellation, and expiry semantics.
4. Numeric order, inventory, cash, loss, and drawdown limits.
5. Approval scope, approver identity, expiry, revocation, and recovery behavior.
6. Append-only ledger, checkpoint, atomicity, retention, backup, and migration policy.
7. Portfolio sharing and concurrency scope across strategies or datasets.
8. Exact read-only CLI/API inspection resources.

The owner approved the recommended defaults for all eight items on 2026-10-26. Inventory, loss, drawdown, and enforcement-window values remain required explicit configuration; missing values fail closed. B4 implementation remains synthetic-only and paper-only.

The B4.2 slice is recorded in [B4.2-LEDGER-RECOVERY-INTEGRITY.md](B4.2-LEDGER-RECOVERY-INTEGRITY.md). It verifies persisted result-snapshot fingerprints, checkpoint metadata and canonical state, and adverse-slippage limit enforcement while preserving the B4.1 storage format and read-only surfaces.

The B4.3 slice is recorded in [B4.3-EVENT-IDENTITY-INVARIANTS.md](B4.3-EVENT-IDENTITY-INVARIANTS.md). It rejects duplicate synthetic market-event IDs before mutation and rejects duplicate IDs in recovered event cursors.

The B4.4 slice is recorded in [B4.4-IDEMPOTENCY-SCOPE-INVARIANTS.md](B4.4-IDEMPOTENCY-SCOPE-INVARIANTS.md). It scopes retry lookup and recovery uniqueness to command event kind while preserving same-type replay/conflict behavior.

The B4.5 slice is recorded in [B4.5-LEDGER-MALFORMED-TAIL.md](B4.5-LEDGER-MALFORMED-TAIL.md). It converts invalid UTF-8, invalid JSON, and non-object ledger records into a stable `BrokerRejected` recovery failure without repair or truncation.

The B4.6 slice is recorded in [B4.6-MALFORMED-PERSISTED-METADATA.md](B4.6-MALFORMED-PERSISTED-METADATA.md). It applies the same fail-closed typed handling to malformed genesis, policy, and checkpoint metadata.

The B4.7 slice is recorded in [B4.7-MALFORMED-SNAPSHOT-RECOVERY.md](B4.7-MALFORMED-SNAPSHOT-RECOVERY.md). It normalizes malformed persisted order and fill records during ledger snapshot restoration.

The B4.8 slice is recorded in [B4.8-SNAPSHOT-SCALAR-VALIDATION.md](B4.8-SNAPSHOT-SCALAR-VALIDATION.md). It validates persisted numeric fields, event time, equity history, revoked approvals, and event cursor shapes before restoration.

The B4.9 slice is recorded in [B4.9-RISK-AUDIT-OUTCOMES.md](B4.9-RISK-AUDIT-OUTCOMES.md). It records order risk and approval rejections with stable reason codes and idempotent replay.

## Product surface order

The product is built in this order:

```text
local deterministic engine
  -> local read-only API/dashboard
  -> web deployment
  -> CLI extension
  -> desktop/mobile app shell
  -> separate production/live-readiness review
```

All surfaces consume the same versioned backend contracts. UI, CLI, and app layers do not duplicate calculation, portfolio accounting, risk, policy, or execution logic. Production deployment and live trading are separate approval gates, not automatic consequences of local completion.

## Non-negotiable boundaries

- BTCUSDT Spot-only, long-only, no leverage, margin, shorting, futures, perpetuals, funding, or liquidation.
- Market OS owns validation, calibration, fusion, signal, sizing, risk, persistence, recovery, and paper execution.
- Jev and hosted models remain advisory or experimental typed inputs; they do not own policy or execution.
- No Binance, Jev/TypeSafe, OpenAI, credential, real-data acquisition, shadow-study, live-trading, or production request is implied by B3.8–B3.14.
- `approved-policy.json` must remain absent unless a future explicitly approved milestone requires it.
- `D:\Code\Github\HKUDS\company-projects` remains a separate workspace and is not modified.
- Preserve `.gitignore`, `README.md`, `API.md`, `.tmp-*`, and unrelated worktree changes.

## Verification snapshot

- B3.14 acceptance tests: 4 passed.
- B3.8–B3.14 focused/regression suite: 85 passed.
- B4.5 focused broker plus B3.2 venue tests: 36 passed.
- B4.10 focused broker plus B3.2 venue tests: 45 passed.
- Full offline suite with `TYPESAFE_API_KEY=''`: 445 passed, 5 pre-existing
  optional LightRAG/Vibe runtime failures, and 1 skipped.
- Compileall, secret scan, and `git diff --check`: passed.
- `approved-policy.json`: absent.
- `company-projects`: absent at the last read-only inspection.
- No provider, network, credential, real-data, trading, commit, or push operation occurred for the B3.14 work.

## How to resume

1. Read this file, [ROADMAP.md](ROADMAP.md), [PHASES.md](PHASES.md), and the active milestone contract.
2. Inspect `git status --short` and preserve pre-existing worktree entries.
3. Review the B3.14 acceptance diff before any commit or push.
4. Read [U5-LOCAL-READONLY-DASHBOARD.md](U5-LOCAL-READONLY-DASHBOARD.md). The local GET-only dashboard is implemented; the next gate is deployment/auth/observability review while preserving paper-only behavior.

The B4.1–B4.10 closeout review is complete. The local hardening slices pass, and the first U5 read-only dashboard is implemented locally. The broader U4/B4 and U5 deployment gates remain open because the contract-level gaps are real. Preserve the paper-only boundary.
