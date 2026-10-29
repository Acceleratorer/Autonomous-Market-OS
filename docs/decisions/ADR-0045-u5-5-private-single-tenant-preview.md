# ADR-0045: U5.5 Private Single-Tenant Preview Scope

**Status:** Accepted scope; implementation gated  
**Date:** 2026-10-29

## Context

The local read-only operator is complete through U5.22. The owner selected a
private single-tenant preview as the next connected-web direction. The current
Next.js and Python services remain loopback-only, and the Python gateway owns
paper accounting, recovery, and file-backed persistence. The current gateway
does not authenticate connected subjects or authorize their portfolios.

## Decision

- Prepare U5.5 for private, single-tenant, read-only access.
- Use TypeScript, React, Node.js, Next.js, and Tailwind CSS for the private
  preview, reusing the existing Next.js operator and keeping portfolio
  accounting, recovery, authorization, and persistence Python-owned.
- Supersede the Next.js-connected framework deferral in ADR-0029 and ADR-0031
  only for this private single-tenant preview. This does not select a host,
  identity provider, or access service.
- Keep the current loopback API and paper-only behavior unchanged until the
  connected authorization boundary is versioned and reviewed.
- Require a selected deployment host and identity provider/login method,
  reviewed storage isolation and portfolio allowlist, and the U5.5
  authentication and operations matrix before connected implementation or
  exposure.
- Treat Tailscale Serve, Cloudflare Tunnel + Access, and self-hosted WireGuard
  as candidates, not approved access services. The concrete host and login
  method remain open.
- Leave the number of user subjects within the tenant open for the next design
  step; one owner subject is the proposed smallest preview.
- Require a verified, versioned identity path from ingress through Next.js to
  Python and a documented trust boundary for local processes and origin access.

## Consequences

The work can advance toward a private preview without implying that hosting,
authentication, or connected data access is ready. Public multi-tenant hosting
and mutation remain outside this decision. The proposed single-tenant storage
and authorization boundary is captured in
[`U5.5 connected web options`](../research/u5-5-connected-web-options-2026-10-29.md)
and requires review against the chosen target before implementation.
