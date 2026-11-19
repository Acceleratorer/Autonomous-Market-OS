# ADR-0057: Strict Recorded Availability for BTC Evidence

- **Status:** Accepted
- **Date:** 2026-11-19
- **Scope:** BTCUSDT Spot; MiniRAG and B3.1 evidence timing

## Context

The approved B1 Binance Vision archive covers historical BTCUSDT Spot 1m
candles received locally on 2026-11-18. Original per-candle publication times
were not captured. The B2 observations precede that receipt, so the archive
cannot establish which source evidence was available at each historical
observation. The packet builder correctly rejects the retrieved citations.

A local inventory on 2026-11-19 found no BTC-tagged sources in the five saved
general document bundles; the only current BTC evidence corpus derives from
B1. The existing U3 Jev connectivity probe is separate: its one synthetic
descriptive request failed validation and was not retried, so it is not a
B3.1 packet assessment.

## Decision

1. Use **strict recorded availability** for BTC evidence. Keep unknown source
   publication times unknown; do not substitute candle event time or local
   archive receipt time for an unrecorded publication timestamp.
2. Do not use an event-time proxy for this B1 revision. The retrospective
   B1/B2 artifacts remain diagnostics and cannot support a historical
   point-in-time MiniRAG/Jev comparison.
3. A future B3.1 packet must satisfy the existing event-time, publication,
   availability, retrieval, provenance, and observation-lineage checks in the
   packet builder. Prefer already-local source records with contemporaneous
   timestamps; otherwise prepare a prospective capture proposal for separate
   owner approval. Source publication may remain unknown when local availability
   is independently recorded under the clarification below.
4. This decision authorizes no additional market-data request, Jev API call,
   credential use, provider egress, promotion, or trading path. Those actions
   require separate explicit approval.

## Consequences

- The current B1 citations remain ineligible for historical B3.1 packets, even
  though MiniRAG can retrieve them reproducibly.
- The previous U3 connectivity probe does not satisfy B3.1: it was not linked
  to a BTC evidence packet or B2 observation.
- B2 remains the numerical control. Jev remains a recorded-response-only
  advisory assessor for evidence support, agreement/contradiction, and
  abstention. Market OS retains calibration, fusion, stability, risk, and
  paper-execution authority.
- Once a source corpus meets the strict timing gate, any comparison must join
  only on the same B2 observation ID and feature fingerprint, use recorded
  B3.1 assessments, and preserve the frozen chronological splits.

## Subsequent owner clarification — 2026-11-19

The owner confirms that a contemporaneously recorded local receipt time with a
defensible, non-negative UTC clock error bound establishes *local availability*
even while `source_published_at` remains unknown. Keep these timestamps
separate: do not copy the local receipt into the publication field or infer
publication from event time. For eligibility, use the conservative latest
possible receipt (`received_at_utc + clock_error_bound_ms`) and require it to be
no later than B2 decision eligibility, with the evidence event range ending no
later than the observation close. Preserve the raw receipt, clock bound, and
unknown-publication status in packet lineage.

The retrospective B1 archive remains ineligible: its recorded local receipt is
after the historical B2 decisions and its capture did not retain a defensible
UTC clock error bound. This clarification does not authorize another market
data request; a prospective capture still needs separate date-bound approval.

## References

- [BTC MiniRAG and Jev Evidence Path](../BTC-MINIRAG-JEV-EVIDENCE-PATH.md)
- [B1 Binance Vision execution evidence](../evidence/b1-binance-vision-execution-2026-11-18.json)
- [Post-guard MiniRAG retrieval evidence](../evidence/btc-minirag-post-guard-retrieval-2026-11-19.json)
- [U3 API connectivity report](../U3-API-CONNECTIVITY-REPORT.md)
- [U3 API connectivity evidence](../evidence/u3-api-connectivity.json)
- [ADR-0056: MiniRAG scope for the BTC evidence path](ADR-0056-minirag-btc-evidence-scope.md)
- [ADR-0058: Jev connectivity-only and local BTC packet assessment](ADR-0058-btc-jev-connectivity-only-local-assessor.md)
