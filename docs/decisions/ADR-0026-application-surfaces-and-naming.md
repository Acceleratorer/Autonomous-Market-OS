# ADR-0026: application surfaces and naming

**Date:** 2026-10-28  
**Status:** Accepted for local implementation

## Decision

Introduce `apps/web`, `apps/cli`, and `apps/gateway` as thin product surfaces.
Keep `market_os` as the domain and compatibility package, including the
existing `api.py` and `cli.py` entrypoints. Use `apps/web/public` as the
canonical static dashboard source and retain the existing hosting path as a
checked compatibility copy.

## Rationale

This gives the repository a professional surface layout without breaking
imports, subprocess commands, package metadata, monkeypatch seams, or the
current local deployment wrapper. The web artifact can move toward static
deployment while remaining disconnected from portfolio state and live access.

## Consequences

New web, CLI, and gateway work has a clear home. Existing names remain stable
until a versioned migration is justified. No public server, authentication
boundary, provider, credential, or live-trading route is enabled.
