# ADR-0039: U5.15 Next.js Local BTC Dataset Registry

**Status:** Accepted locally  
**Date:** 2026-10-29

## Context

The local Next.js operator only exposed B4 portfolio pages, while U5's web
scope also includes BTC research data. B1 already persists canonical datasets
in a local HistoryStore, but the HTTP adapter exposed only item resources and
had no bounded dataset catalog for the web app.

## Decision

- Add a cursor-paged `GET /v1/btc/history/datasets` response with a maximum page
  size of 100 and stable exclusive revision ordering.
- Bind the endpoint to the gateway's configured HistoryStore; reject extra
  query parameters, including `store_root`.
- Return an empty page without creating store files when no catalog exists.
  Open an existing catalog in read-only mode and return metadata without
  filesystem paths or unbounded candle/manifests arrays.
- Add the server-rendered `/datasets` route to the existing Next.js operator.
  Keep response parsing, formatting, and pagination on the server.
- Label the page as metadata-only. Dataset file integrity still requires the
  existing replay operation.

## Consequences

The selected TypeScript, React, Node.js, Next.js, and Tailwind application now
has a local B1 dataset inventory alongside B4 portfolio inspection. No new
dependency, provider call, data acquisition, client-side domain logic, or
connected deployment is introduced. Full dataset detail remains gated on
bounded candle and manifest contracts.
