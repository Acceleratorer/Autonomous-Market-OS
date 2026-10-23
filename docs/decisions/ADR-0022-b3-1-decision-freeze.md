# ADR-0022: B3.1 Offline Evaluation Protocol Decision Freeze

- **Status:** Accepted
- **Date:** 2026-10-23
- **Scope:** BTCUSDT Spot; B3.1 protocol decisions only

## Context

B3 is an offline, recorded-response-only benchmark. Its fixture does not
contain leakage-safe labels, so its predictive and calibration metrics remain
unavailable and B3 is not promoted. The B3.1 decision worksheet proposed
protocol choices but did not itself approve them. The human owner has now
approved the decisions below. This ADR records that freeze; it does not start
implementation or a study.

## Decisions

1. **Jev role and questions.** Jev remains an advisory typed evidence
   evaluator. Initial B3.1 questions cover evidence support, agreement versus
   contradiction, and abstention. Consistency, freshness, provenance, and
   evidence-quality gates remain deterministic Market OS responsibilities.
   Regime questions and additional context are deferred.
2. **Primary target.** Preserve B2's five-minute log-return definition,
   `ln(C[t+5]/C[t])`. The primary classification is positive versus
   non-positive return. Executable net return after post-decision pricing,
   delay, fees, and slippage is a separate economic-evaluation target. Jev
   assessment probabilities are never relabeled as market-return
   probabilities.
3. **Calibration and fusion.** Binary logistic (Platt) calibration is the
   primary calibration method; regularized logistic regression is the primary
   fusion method. One-bin calibration remains a weak baseline. Isotonic
   calibration is unavailable unless a later preregistered sample threshold
   explicitly permits it. Missing or abstaining Jev results remain explicit
   and are not silently replaced with a neutral probability.
4. **Provider and privacy.** B3.1 implementation and evaluation remain
   recorded-fixture-only. No new Jev/TypeSafe request, credential, provider
   adapter activation, or context egress is authorized. Provider budget,
   version, retention, redaction, and latency policy require separate
   approval.
5. **Market scope.** B3.1 is BTCUSDT Spot-only. It assumes no short inventory,
   margin, leverage, futures, perpetuals, funding, or x50/x100. Any derivative
   work requires a new contract, ledger, risk gate, and human decision.
6. **Prospective shadow study.** A 90-day shadow period is a future proposal
   only. It requires a sufficient approved dataset, preregistered power/sample
   and regime-coverage rules, frozen costs and latency assumptions, and
   separate approval. It is not an active or approved study.

## Rationale and consequences

Fixture-only preserves B3's reproducible, offline boundary while provider
version/capability, request budget, retention, redaction, latency, and permitted
egress policies remain unresolved. It also avoids turning a protocol decision
into permission to contact Jev or send packet context to a provider.

The directional target measures the sign of B2's existing five-minute
log-return. Executable net return additionally depends on post-decision prices,
delay, fees, and slippage. Keeping separate target identities prevents a
directional probability or Jev's semantic assessment distribution from being
misrepresented as an executable-return probability.

Spot-only preserves B3.1's existing inventory and risk boundary. Derivatives
introduce contract, funding, margin, liquidation, and ledger behavior that
requires its own model and explicit human approval.

The B3 E1/E2 definitions, fixture, results, offline status, and non-promotion
remain unchanged. These decisions authorize no provider request, Binance
historical acquisition, prospective shadow study, B3.1 implementation, paper
execution, or trading.

## Deferred decisions

- Exact packet, assessment, question, configuration, and provider-specific
  primitive versions and mappings.
- Dataset sufficiency, power/sample thresholds, regime coverage, and any later
  preregistered threshold for isotonic calibration.
- Fusion features, missingness encoding, thresholds, uncertainty policy, and
  other study-specific preregistration details.
- Provider/model version and capability verification; request budget, cost,
  latency, permitted source classes, redaction, retention, and deletion policy.
- Whether to propose a prospective shadow study, and its duration, acceptance
  criteria, cost/latency assumptions, and human review.
- Whether derivatives remain permanently excluded or receive a separate future
  contract and simulator.

## References

- [Jev processing protocol](../../JEV_PROCESSING.md)
- [B3 benchmark report](../U3-B3-JEV-INCREMENTAL-BENCHMARK-REPORT.md)
- [ADR-0015: BTC math-first and Jev boundary](ADR-0015-btc-math-first-jev-experiment.md)
- [ADR-0019: U3/B3 offline Jev boundary](ADR-0019-u3-b3-jev-experimental-boundary.md)
