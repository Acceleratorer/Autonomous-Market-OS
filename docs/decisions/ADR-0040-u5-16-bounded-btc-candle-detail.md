# ADR-0040: U5.16 Bounded BTC Candle Detail

**Status:** Accepted locally  
**Date:** 2026-10-29

## Context

U5.15 added a bounded local BTC dataset registry but left candle detail for a
later slice. The existing B1 candle resource returns an unbounded array and
accepts a caller-selected `store_root`, so the local Next.js page needs its own
bounded contract before rendering candle rows.

## Decision

- Add a fixed-store read-only route for a revision's candles, paged by an
  exclusive stored `open_time_ms` cursor with a maximum of 100 rows.
- Verify the canonical relative Parquet location and stored file hash before
  selecting each page. Stream hash reads so memory use remains fixed.
- Return only dataset metadata and candle timestamps/numeric strings. Keep
  manifest, provenance, outcomes, gaps, and replay out of this response.
- Add a server-rendered Next.js detail route linked from `/datasets`, with
  ordinary GET navigation and a labelled horizontal-scroll region for mobile.
- Keep replay as the canonical-content check; a hash-valid page alone does not
  prove the whole dataset matches its canonical fingerprint.

## Consequences

The local operator can inspect stored BTC candles through a bounded page while
Python remains authoritative for dataset integrity. No client-side calculation,
mutation, acquisition, provider access, or connected deployment is enabled.
Hashing remains linear in file size for each page, and experiment/report views
remain separate follow-on contracts.
