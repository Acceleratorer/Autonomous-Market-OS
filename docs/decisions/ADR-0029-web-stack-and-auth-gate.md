# ADR-0029: web stack and authenticated access gate

**Date:** 2026-10-29  
**Status:** Accepted as a deferred promotion gate

## Decision

Keep the current plain HTML local shell and static preview. Treat Astro as the
next candidate for componentized read-only views, React + Vite as the candidate
for richer client-side interaction, and Next.js as deferred until authenticated
server rendering and a separately operated web runtime are approved.

Define authentication, tenant isolation, session behavior, and production
observability before enabling connected shared access. Do not add credentials,
provider integration, public listeners, or mutation routes in this gate.

## Rationale

The current product has stable Python-owned contracts and a small GET-only
operator surface. A framework would add build and dependency cost without a
required workflow. Authentication is a larger boundary than a UI library and
must be settled before the runtime is exposed.

## Consequences

- Web work can continue locally against deterministic fixtures.
- A future framework decision has explicit triggers and acceptance checks.
- The current shell remains useful without Node or a network provider.
- Public deployment and mutation stay blocked until U5.5 criteria are met.
