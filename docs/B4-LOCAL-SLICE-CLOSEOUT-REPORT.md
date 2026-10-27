# B4 Local Slice Closeout Report

**Review date:** 2026-10-27
**Scope:** U4/B4.1–B4.10 synthetic, paper-only local broker
**Decision:** The B4.1–B4.10 hardening slices are complete as a local read-only inspection and single-writer paper simulation. U4/B4 is **not closed as a complete portfolio milestone** and must remain paper-only local.

## 1. Executive decision

`B4.9` is complete for its stated slice. `B4.10` closes the reproduced market-order fill-time risk gap for the local full-fill model.

The broader B4 contract still has real gaps. The current implementation is suitable for deterministic synthetic replay, local inspection, and one-writer paper experiments. It is not yet a complete shared portfolio or operator mutation surface.

Do not promote this work to a shared or externally mutable B4 deployment. Keep U4/B4 in paper-only local mode. The first local U5 read-only dashboard is now available, but it does not imply that B4 mutation, backup, migration, or shared-portfolio semantics are complete.

## 2. B4.1–B4.9 matrix

| Slice | Implemented and verified | Evidence | Disposition |
|---|---|---|---|
| B4.1 | Synthetic BTCUSDT Spot, long-only portfolio genesis, Decimal accounting, full FIFO market/limit fills, owner approval binding, idempotent submit/cancel, append-only JSONL, checkpoints, deterministic recovery, CLI/API read-only inspection | `market_os/b41_broker.py`, `market_os/tests/test_b41_broker.py` | Complete for the approved local boundary |
| B4.2 | Result-snapshot fingerprints, checkpoint identity/sequence/canonical equality, adverse-slippage limit enforcement | `docs/B4.2-LEDGER-RECOVERY-INTEGRITY.md` | Complete |
| B4.3 | Duplicate market-event IDs rejected before mutation; recovery rejects duplicate cursor IDs | `docs/B4.3-EVENT-IDENTITY-INVARIANTS.md` | Complete |
| B4.4 | Idempotency scoped by command event kind; same-type replay/conflict preserved; duplicate recovered identities rejected | `docs/B4.4-IDEMPOTENCY-SCOPE-INVARIANTS.md` | Complete |
| B4.5 | Invalid UTF-8, invalid JSON, and non-object ledger records fail closed with a typed broker error | `docs/B4.5-LEDGER-MALFORMED-TAIL.md` | Complete |
| B4.6 | Malformed genesis, policy, and checkpoint metadata fail closed with stable broker errors | `docs/B4.6-MALFORMED-PERSISTED-METADATA.md` | Complete |
| B4.7 | Malformed persisted order/fill records fail closed during snapshot restoration | `docs/B4.7-MALFORMED-SNAPSHOT-RECOVERY.md` | Complete |
| B4.8 | Numeric snapshot fields, event time, equity history, revoked approvals, and cursor shapes are validated before restore | `docs/B4.8-SNAPSHOT-SCALAR-VALIDATION.md` | Complete |
| B4.9 | Stable rejection reason codes, `order.rejected` audit events, idempotent rejected-submit replay, read-only risk inspection | `docs/B4.9-RISK-AUDIT-OUTCOMES.md` | Complete for submit-order outcomes |
| B4.10 | Fill-time market-order risk failures become terminal, audited, cursor-advancing outcomes with deterministic recovery | `docs/B4.10-FILL-TIME-RISK-OUTCOMES.md` | Complete for the reproduced gap |

## 3. Test matrix and verification

| Check | Result |
|---|---|
| B4 broker plus B3.2 virtual venue focused tests | **45 passed** |
| B4 broker plus B3 synthetic surfaces acceptance group | **67 passed** |
| Full offline suite with `TYPESAFE_API_KEY=''` | **445 passed, 5 pre-existing optional LightRAG/Vibe failures, 1 skipped** |
| Compile check | Passed: `python -m compileall -q market_os scripts` |
| Diff whitespace check | Passed: `git diff --check` |
| Secret scan | Passed: `python scripts/ci_checks.py secret-scan` |
| Evidence validation | Passed: `python scripts/ci_checks.py validate-evidence` (`22` evidence files) |
| Stale-writer check | Passed: a second broker instance is rejected until it reloads after another writer commits |
| Oversized market-order probe | **Fixed and regression-tested**; see Section 4 |

The five full-suite failures are the pre-existing optional LightRAG/Vibe runtime failures documented in the project context. They are outside B4 and do not invalidate the focused B4 result.

## 4. Real gaps found

### 4.1 Fill-time risk handling for market orders

Limit orders can be checked against their submitted price at submission. A market order has no price until a synthetic market event arrives. B4.10 now handles an eventual fill notional outside the approved range by transitioning the order to terminal `risk_rejected`, recording a stable reason code in the committed `market.processed` result, and advancing the event cursor.

The remaining policy choice is whether this fill-time rejection rule is sufficient for the local full-fill model or whether a future version should reserve worst-case market-order notional at submission.

### 4.2 Partial fills and expiry

The approved local policy deliberately uses full fills and disables expiry. The state machine has no implemented residual quantity or event-time expiry behavior. This is an intentional boundary for the current paper slice, not an accidental regression. It remains a blocker for a generalized broker contract or any claim of exchange-like lifecycle coverage.

### 4.3 Portfolio sharing and concurrency

The implementation supports isolated portfolios and one writer at a time using a local file lock plus stale-ledger-head rejection. That is enough for the current local single-writer boundary. It does not define shared portfolio membership, cross-strategy reservations, fair ordering, conflict resolution beyond stale-writer rejection, or distributed ownership/recovery.

### 4.4 Mutation API

`submit_order`, `cancel_order`, and `revoke_approval` exist as Python methods for local tests and paper workflows. CLI and HTTP surfaces are read-only; there is no mutation route. That preserves the approved safety boundary, but it means B4 is not an operator command surface. A future mutation API needs its own versioned contract, authentication/access boundary, idempotency handling, audit behavior, and explicit approval.

### 4.5 Backup, retention, and migration

The ledger and checkpoint format are durable within one local store, but no backup/restore tool, retention/archive mechanism, or schema migration tool is implemented. The owner decision calls for indefinite ledger retention, opt-in local backup, and explicit versioned migrations; those operational controls remain unproven.

### 4.6 Audit coverage outside submit-order rejection

`B4.9` covers deterministic rejected submit outcomes. Invalid cancel and approval-revocation paths still raise generic `BrokerRejected` errors instead of consistently recording typed rejection outcomes. This is a smaller audit gap inside the future mutation surface.

### 4.7 U5 local surface boundary

The first U5 surface is documented in [U5-LOCAL-READONLY-DASHBOARD.md](U5-LOCAL-READONLY-DASHBOARD.md). It is a local GET-only HTML view over the existing B4 inspection seam. It does not close the U5 deployment gate or authorize shared access.

## 5. Final status and next gate

**Status:** `B4.1–B4.10 hardening complete; U4/B4 milestone not closed.`

Keep the implementation in **paper-only local** mode. The next B4 closure gate should explicitly resolve:

1. whether full-fill/expiry-disabled remains the permanent local policy or receives versioned lifecycle support;
2. the intended scope for shared portfolios and concurrency;
3. backup/restore, retention, and migration evidence; and
4. the separate mutation API contract and complete rejection audit coverage.

No provider, credential, live-data, exchange, deployment, commit, or push operation was performed for this review.
