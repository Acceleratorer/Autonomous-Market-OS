# ADR-0052: U6 read-only app-shell contract

**Date:** 2026-11-02
**Status:** Accepted for local contract definition; platform selected by ADR-0053; U6.3 local shell slice and U6.4-A unsigned artifact verified; U6.4-B remains open

## Context

U6 now has mature local read-only CLI projections for the shared BTC dataset,
ingestion-manifest, and B2/B3 research contracts. The repository also has a
server-rendered Next.js operator shell with responsive desktop/mobile behavior.
There is no owner VM or connected access. U6.2 selects Electron for the first
Windows/Linux desktop container; U6.4-A now verifies the unsigned artifact
contract and U6.4-B remains the signed release gate.

## Decision

Define one U6 app-shell contract over the existing versioned GET surfaces. Use
the Next.js `AppShell` as the reference shell, keep Python `market_os` as the
domain authority, and require payload/parity/safety checks before shipping a
native desktop or mobile package. Do not add a generic app bucket or a new
stateful client model.

The contract is recorded in
[U6-READ-ONLY-APP-SHELL-CONTRACT.md](../U6-READ-ONLY-APP-SHELL-CONTRACT.md).

## Consequences

- CLI, HTTP, Next.js, and a future shell share the same envelopes, cursors,
  hashes, and exact values.
- The shell remains local-only, synthetic, paper-only, and GET-only.
- A future platform choice must explicitly cover packaging, filesystem access,
  gateway lifecycle, updates, and safe failure behavior.
- DirectAdmin static preview and private connected runtime remain separate.

## Deferred

Tauri/React Native/Flutter alternatives, provider credentials, connected
identity, mutation routes, live execution, and distributed infrastructure.
Electron lifecycle is verified in U6.3; U6.4-A verifies reproducible source
sidecar packaging and U6.4-B owns signing and explicit update rollback.
