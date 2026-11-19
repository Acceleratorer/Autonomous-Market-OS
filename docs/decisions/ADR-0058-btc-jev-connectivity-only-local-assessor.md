# ADR-0058: Jev Connectivity-Only and Local BTC Packet Assessment

- **Status:** Accepted
- **Date:** 2026-11-19
- **Scope:** BTCUSDT Spot; hosted Jev boundary and B3.1 packet assessment

## Context

The owner approved one synthetic TypeSafe/Jev connectivity request on
2026-11-19. It passed the U3 response contract and assessed no BTC packet. The
local BTC implementation has a separate Qwen evidence assessor, while the
historical B1 citations remain ineligible because their recorded local receipt
occurred after the B2 observations and no defensible UTC clock error bound was
captured. Source publication time remains unknown and is not inferred from
receipt time.

## Decision

1. Keep hosted Jev at connectivity-only for the current BTC work. The
   successful synthetic probe is connectivity evidence, not a BTC assessment.
2. Keep BTC B3.1 packet content and assessment local, using the separately
   identified Qwen assessor for eligible packets. Do not send packet text,
   citations, or assessment context to hosted Jev.
3. Treat local Qwen and Jev as different systems. Qwen's current one-hot
   evidence labels are uncalibrated, are not market-return probabilities, and
   do not inherit Jev's identity or calibration.
4. Preserve Market OS ownership of market math, probability calibration,
   stability, fusion, risk, and paper decisions. Evidence labels cannot become
   market-return forecasts or execution authority.
5. Require a new owner decision before any hosted Jev packet assessment,
   context egress, or successor study that changes this boundary. Future Jev
   connectivity calls also require separate explicit approval.

## Consequences

- No eligible real BTC evidence packet currently exists under strict recorded
  availability. The local Qwen smoke runs on synthetic packets validate only
  local inference and audit plumbing. Under the 2026-11-19 clarification in
  ADR-0057, a future contemporaneous receipt with a defensible UTC error bound
  may establish availability while publication remains unknown; this ADR does
  not authorize capturing that data.
- The successful Jev connectivity record remains separate from all B3.1
  packet, Qwen training, tuning, or evaluation artifacts.
- Any future local assessment must retain the same packet fingerprint and
  observation lineage as its numerical control, then be reported as a Qwen
  result rather than a Jev result.
- This decision does not approve additional market-data acquisition, provider
  requests, promotion, shadow operation, or trading.

## References

- [ADR-0022: B3.1 offline evaluation freeze](ADR-0022-b3-1-decision-freeze.md)
- [ADR-0057: Strict recorded availability for BTC evidence](ADR-0057-btc-strict-recorded-availability.md)
- [BTC MiniRAG and Jev evidence path](../BTC-MINIRAG-JEV-EVIDENCE-PATH.md)
- [U3 connectivity report](../U3-API-CONNECTIVITY-REPORT.md)
- [Successful synthetic Jev connectivity evidence](../evidence/jev-connectivity-reauthorized-2026-11-19.json)
