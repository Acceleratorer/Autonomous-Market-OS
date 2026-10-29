# ADR-0032: Local Next.js operator web

**Date:** 2026-10-29  
**Status:** Accepted for U5.8 local scope

## Decision

Use TypeScript, React, Node.js, Next.js App Router, and Tailwind CSS in a new
`apps/web/next-operator/` package for local read-only portfolio inspection.
Keep the application server on loopback and consume the existing Python B4
read-only API. Keep the Python broker as the only owner of portfolio and risk
logic.

## Rationale

The existing local shell already exposes the B4 inspection resources, while
the user selected a component-based TypeScript web stack for the next web
implementation. A separate Next.js surface lets that local workflow progress
without changing the disconnected static preview or compatibility shell.

## Consequences

- The app server renders data from fixed loopback GET endpoints with no-store
  caching and runtime response validation.
- No client-side mutation controls, portfolio calculations, or credential
  handling are added.
- The package has its own pinned dependency manifest and lockfile, TypeScript
  check, production build, and browser smoke.
- Selection applies only to the local operator. U5.5 still blocks authenticated
  shared access until deployment, identity, isolation, session, and operational
  controls are selected and reviewed.
- The older plain HTML preview and operator shell remain available.

## Evidence

See [U5.8](../U5.8-NEXT-LOCAL-OPERATOR-WEB.md) and
[`u5-8-next-local-operator-web.json`](../evidence/u5-8-next-local-operator-web.json).
