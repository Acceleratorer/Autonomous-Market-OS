# Web stack options

**Review date:** 2026-10-29  
**Scope:** Future browser application over the existing local contracts.

## Current baseline

The repository has four distinct web surfaces:

| Surface | Location | Runtime | Purpose |
|---|---|---|---|
| Public preview | `apps/web/public` | static HTML/CSS | disconnected paper-only product preview |
| Local operator shell | `apps/web/operator` | gateway-served HTML/CSS/JS | GET-only local portfolio inspection |
| Local Next operator | `apps/web/next-operator` | Node.js / Next.js App Router | TypeScript and React read-only operator UI over loopback API |
| Domain/API | `market_os` and `apps/gateway` | Python | contracts, recovery, accounting, risk, and inspection |

The Next.js package is selected for the local portfolio operator workflow.
The owner also selected the TypeScript/React/Node.js/Next.js/Tailwind CSS stack
for the private single-tenant U5.5 preview. The static preview remains
disconnected, and the compatibility HTML shell remains available. The Next.js
client does not own domain logic.

## Options

| Option | Fits when | Cost | Decision status |
|---|---|---|---|
| Plain HTML/CSS/JS | Static preview and compatibility operator shell | lowest | active for those surfaces |
| Astro | Several mostly static/read-only routes need shared components and a small client island | low to medium | preferred next candidate |
| React + Vite | The browser needs richer client state while the Python gateway remains the API owner | medium | candidate after interaction scope is approved |
| Next.js | Local server-rendered operator UI with a loopback Node runtime | medium | selected for U5.8 local scope |
| Next.js connected | Authenticated server rendering and an operated web runtime are approved | high | selected for the private preview stack by ADR-0045; host and auth remain behind U5.5 gate |

## Selection rules

1. Keep plain HTML for the disconnected preview and compatibility shell.
2. Choose Astro when the next approved work is componentized read-only views,
   static artifact generation, or a small number of client islands.
3. Choose React + Vite when interaction is primarily client-side and the
   gateway remains the sole domain/API owner.
4. Use the selected Next.js App Router for the local read-only operator. Keep
   connected use behind the U5.5 identity, storage-isolation, runtime, and
   observability gate.

## Non-negotiable constraints

- No framework may own portfolio accounting, risk, persistence, replay, or
  order mutation.
- The browser consumes versioned API contracts and treats model output as
  advisory data.
- Public static preview and connected local operator shell remain separate
  artifacts.
- Adding a framework requires a package lock, build check, browser smoke, and a
  bundle/dependency review in the same milestone.
