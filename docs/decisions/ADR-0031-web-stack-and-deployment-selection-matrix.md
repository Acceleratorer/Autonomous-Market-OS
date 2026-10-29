# ADR-0031: web stack and deployment selection matrix

**Date:** 2026-10-29  
**Status:** Accepted as a decision aid; no deployment selected

## Decision

Use the existing plain HTML/CSS/JS shell while the read-only surface is small.
Treat Astro as the first framework candidate for componentized read-only views,
React + Vite as the candidate for approved client-side interaction, and
Next.js as deferred until authenticated server rendering and an operated
runtime are approved together.

Record deployment choices separately from framework choices. The active target
remains loopback plus deterministic static artifact handoff.

## Rationale

Framework and deployment decisions solve different problems. Selecting a UI
framework does not establish identity, tenant isolation, secrets, sessions,
rate limits, audit retention, or rollback. Keeping the decisions separate lets
local web work progress without implying public access.

## Consequences

- The next coding slice can remain local and dependency-free.
- A framework is introduced only with a real workflow, lockfile, build, smoke,
  and bundle review.
- Public or shared deployment remains blocked until the U5.5 contract inputs
  are supplied and tested.
