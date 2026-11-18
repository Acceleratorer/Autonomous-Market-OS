# ADR-0023: MiniRAG Scope for the BTC Evidence Path

- **Status:** Accepted
- **Date:** 2026-11-18
- **Scope:** BTCUSDT Spot evidence retrieval only

## Context

Market OS already has a LightRAG adapter for the general cited-research
workflow. The BTC experiment has a separate need: attach time-bounded cited
context to the frozen B2 numerical observation before an optional Jev evidence
assessment. The owner confirmed that MiniRAG should serve this BTC flow while
the broader LightRAG decision remains unchanged.

## Decision

Use MiniRAG's `mini` retrieval mode behind the existing retrieval contract for
the BTC evidence flow. Normalize returned source text into Market OS passage
IDs and citations, then join it to an eligible B2 observation through the
B3.1 evidence-packet profile.

For this offline integration slice:

- MiniRAG runs in a child process over caller-owned BTCUSDT-tagged documents.
- Deterministic local embedding and structural extraction functions keep the
  adapter independent from hosted providers. The optional MiniRAG runtime is
  not a Market OS base dependency.
- Market OS validates event-time bounds, availability, source hashes,
  retrieval lineage, and source dependency groups before a packet is usable.
- Jev remains a recorded-response-only advisory assessor until separate
  provider access is approved. B2 remains the numerical control; Market OS
  retains calibration, fusion, stability, risk, and paper execution authority.
- The existing LightRAG adapter and its general cited-research role remain in
  place. This ADR does not replace that project-wide choice.

## Consequences

The BTC path can retain source citations and observation identity while keeping
the quantitative target separate from semantic evidence assessments. MiniRAG's
deterministic local extraction is a structural retrieval aid, not a semantic
model or a retrieval-quality result. Any later Jev integration must use the
same packet fingerprints and matched B2 rows; no market-return probability is
read from Jev labels.

The archive's local receipt timestamp is retained as availability metadata. It
does not imply that each historical candle was available at its original
minute, so packet construction must preserve both market event time and local
availability time.

## References

- [BTC MiniRAG and Jev Evidence Path](../BTC-MINIRAG-JEV-EVIDENCE-PATH.md)
- [ADR-0015: BTC math-first and Jev boundary](ADR-0015-btc-math-first-jev-experiment.md)
- [ADR-0019: U3/B3 Jev experimental boundary](ADR-0019-u3-b3-jev-experimental-boundary.md)
- [ADR-0022: B3.1 offline evaluation freeze](ADR-0022-b3-1-decision-freeze.md)
