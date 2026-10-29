# ADR-0044: U5.22 Bounded Portfolio Equity History

**Status:** Accepted locally  
**Date:** 2026-10-29

## Context

The local portfolio detail page shows current balances and risk records, but the
Python broker's persisted equity history is not exposed through the inspection
contract. The broker already trims this series to the configured risk window
and records equity as part of its existing paper accounting.

## Decision

- Add a v3 aggregate inspection response that extends v2 with the latest 100
  retained equity samples. Keep v1 and v2 response shapes unchanged.
- Read the persisted broker values and exact page extrema in Python. Preserve
  the existing stale-state checks and open the broker once per aggregate
  request.
- Permit equal event timestamps and return samples in their stored
  non-decreasing event-time order. Do not add a cursor because the local view
  needs only a bounded latest page and equal timestamps are not unique cursors.
- Render a static server-side SVG and the exact values in a bounded table. Do
  not calculate financial metrics in TypeScript, add a chart package, or
  animate this frequently inspected page.
- Keep U5.5 connected deployment, identity, isolation, and operations gates
  unchanged.

## Consequences

Operators can inspect a recent equity trend and its exact stored observations
from the existing local portfolio page. When more than 100 samples are
retained, older retained samples are explicitly omitted from this view. The
chart remains synthetic, paper-only, local, and read-only.
