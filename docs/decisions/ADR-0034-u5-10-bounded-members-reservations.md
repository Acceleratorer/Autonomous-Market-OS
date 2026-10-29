# ADR-0034: Bounded Member and Reservation Inspection

**Status:** Accepted locally  
**Date:** 2026-10-29

## Context

U5.9 bounded order and risk rows but kept complete genesis membership and all
open reservation rows in the aggregate response. Response size therefore still
grew with those domain sets.

## Decision

Add `GET /v2/b4/portfolios/{portfolio_id}/inspection` with the contract
`market-os.b4-portfolio-inspection@v2`. Page members in ascending strategy ID
order and open reservations in broker order, newest first. Use independent,
exclusive cursors and 1–100 page limits for members, reservations, orders, and
risk. Keep portfolio reservation totals and each page's total count scoped to
the complete current set.

Keep the v1 aggregate and legacy detail resources unchanged for local
compatibility. Move the Next.js operator and compatibility HTML shell to v2.
Python continues to own portfolio identity, accounting, risk, membership,
reservations, and persistence.

## Consequences

- The browser detail response has bounded membership and reservation row
  arrays while retaining complete totals and independent navigation.
- V1, legacy resource, and catalog responses remain local-only; this ADR does
  not make those paths safe for connected access.
- Ledger recovery and risk-page selection remain linear. U5.5 and B4 retention
  and migration gates remain separate.

## Rejected alternatives

- Slicing the existing full arrays in the web layer would leave the HTTP
  response and server memory dependent on full cardinality.
- Changing v1 in place would break clients that rely on complete membership
  and reservation arrays.
- Moving page selection or reservation totals into TypeScript would duplicate
  broker-owned domain behavior.
