# ADR-0041: U5.17 Bounded BTC Manifest Inspection

**Status:** Accepted locally  
**Date:** 2026-10-29

## Context

U5.15 and U5.16 add fixed-store BTC dataset and candle inspection. B1 manifests
contain useful per-run metadata, but the legacy manifest resource accepts a
caller-selected root and may include unbounded page, gap, and parent arrays.
The local Next.js operator needs an independent contract with bounded requests
and outputs.

## Decision

- Add a paged catalog summary endpoint and a dataset-bound manifest detail
  endpoint, both using the configured local HistoryStore and read-only DuckDB.
- Resolve the detail path from the validated manifest ID and keep it inside the
  local manifest directory. Read at most 8 MiB and verify the exact file bytes
  against the catalog SHA-256 before parsing.
- Return a fixed scalar field set, outcome counts, and collection counts. Do not
  include filesystem paths, raw arrays, or provenance payloads.
- Render a Next.js run list and detail page with normal GET navigation; disable
  speculative prefetch for data routes that perform reads or hashing.
- Keep the existing CLI/domain inspection resources authoritative for full
  arrays and lineage. Canonical dataset replay remains the validation boundary.

## Consequences

The local operator can review manifest identity, coverage, runtime, integrity
fingerprints, outcome totals, and collection sizes without exposing unbounded
payloads or arbitrary filesystem access. Manifests over the fixed 8 MiB
inspection cap fail closed in the web surface. The feature remains local and
read-only; it does not authorize ingestion or connected deployment.
