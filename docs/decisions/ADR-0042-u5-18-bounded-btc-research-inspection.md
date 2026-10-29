# ADR-0042: U5.18 Bounded BTC Research Inspection

**Status:** Accepted locally  
**Date:** 2026-10-29

## Context

U5.15–U5.17 add bounded Next.js inspection for B1 datasets, candles, and
ingestion manifests. B2/B3 already persist offline runs, but their existing
resource routes expose caller-selected stores and do not provide a bounded
catalog/detail contract for the web operator.

## Decision

- Add fixed-configuration B2/B3 catalog and detail endpoints with exclusive
  run-ID pagination and strict query validation.
- Do not create missing stores on GET. Keep existing B2/B3 store reads in
  read-only mode and reject persistence through those instances.
- Read only the selected metrics/report artifact, cap manifests and results at
  256 KiB, and verify the exact result bytes against the stored size and
  SHA-256 before parsing.
- Return fixed summaries and normalized B2 metrics/B3 reports. Do not include
  artifact paths, features, labels, prediction arrays, fixture cases, or raw
  provider responses.
- Bind B3 report claims to run lineage, require matched inputs and offline
  request counts, and keep promotion fixed at `not-promoted`.
- Render server-side Next.js pages with GET links and contained responsive
  tables. Allow a configured loopback API port while keeping the host fixed to
  `127.0.0.1`.

## Consequences

The local operator can inspect persisted numerical baselines and
recorded-response comparisons without running experiments or returning large
artifacts to the browser. Result integrity checks establish the selected
artifact's stored hash; they do not replace full replay. B1 outcome, gap, and
provenance detail remain separate bounded work, and connected deployment
remains behind the U5.5 decision gate.
