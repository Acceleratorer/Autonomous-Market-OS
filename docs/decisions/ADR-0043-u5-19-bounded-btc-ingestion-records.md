# ADR-0043: U5.19 Bounded BTC Ingestion Records

**Status:** Accepted locally  
**Date:** 2026-10-29

## Context

U5.15–U5.18 add local read-only BTC dataset, candle, manifest, and research
inspection to the Next.js operator. The manifest detail returns only collection
counts, so operators cannot review which source rows were accepted or rejected,
where canonical candle gaps occurred, or which bounded raw records support the
ingestion outcomes.

## Decision

- Add manifest-scoped GET routes for outcomes, gaps, and raw provenance. Keep
  each page capped at 100 rows and use exclusive cursors bound to the selected
  manifest.
- Reuse the configured, read-only HistoryStore. Reject caller roots, malformed
  and duplicate query fields, invalid cursors, and manifest/dataset mismatches.
- Verify the selected manifest against its catalog SHA-256 before exposing gap
  records. Validate gap entry shape, ordering, and collection count.
- Compare outcome status totals against the verified manifest and join each
  displayed outcome to its stored raw-record fingerprint.
- Verify provenance payload fingerprints in DuckDB while returning only a
  512-character preview. Fail closed when an individual stored payload exceeds
  the 256 KiB local inspection cap.
- Render all three views as server-side pages with escaped text and contained
  tables. Do not return filesystem paths, full raw payloads, or mutation
  controls.

## Consequences

Operators can inspect bounded B1 result, gap, and source-row details from the
local web surface. The existing provenance key deduplicates identical raw-page
hashes within a run. This view does not replace canonical replay. The local BTC
detail pages are complete; connected deployment still requires the U5.5
decisions about target, identity, isolation, and operations.
