# ADR-0035: Bound the Portfolio Catalog and Legacy HTTP Resources

**Status:** Accepted locally  
**Date:** 2026-10-29

## Context

U5.10 bounded the current detail pages, but the portfolio catalog and legacy
B4 HTTP resources could still return every member, reservation, order, fill,
risk record, approval, ledger event, or the entire snapshot. A large local
store could therefore create a response proportional to its full cardinality.

## Decision

- Keep the catalog routes and legacy resource paths, but add exclusive cursors
  and hard page limits from 1 through 100, defaulting to 25.
- Return catalog counts instead of full member arrays.
- Use resource-specific cursors for member, reservation, order, fill, risk,
  approval, and ledger pages. Keep full selected ledger records in the bounded
  window so local audit inspection remains useful.
- Return compact summaries without the complete event cursor.
- Reject the aggregate HTTP `snapshot` export. It duplicates the collections
  now available through page resources; broker-internal snapshots remain
  available to local code.
- Keep both local browser registries server-rendered and GET-only, using the
  same bounded catalog contract.
- Skip unrecoverable catalog candidates, report their count on the returned
  page, and show that count in both local registries. Cursor IDs must resolve
  to a recoverable catalog entry.
- Return HTTP 409 when a store changes between recovery and catalog summary
  inspection; callers may retry without treating concurrent state as corrupt.

This changes what legacy local HTTP collection calls return by default: callers
must follow the returned page cursor to inspect older rows. The route remains
loopback-only; connected use is still blocked by U5.5.

## Consequences

Response row counts are bounded independently of local history size. The
catalog still enumerates directory names, portfolio opening still runs
validated recovery, and ledger-page inspection still scans the ledger. A
durable index or cache is deferred until it can be checked against the
append-only ledger head without weakening recovery integrity.
