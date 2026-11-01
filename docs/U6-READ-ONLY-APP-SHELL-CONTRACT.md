# U6 Read-Only App-Shell Contract

**Status:** Contract defined locally; concrete desktop/mobile platform deferred.
**Date:** 2026-11-02

## Purpose

U6 extends the completed local CLI, HTTP, and Next.js read-only projections to
thin desktop and mobile shells. The shell is a presentation adapter. Python
`market_os` remains authoritative for accounting, persistence, recovery, BTC
inspection, research inspection, and all versioned response semantics.

The existing Next.js `AppShell` is the reference interaction model for the
first implementation. A native shell may be selected later, but it must keep
the same route semantics and safety boundary.

## Contract boundary

| Surface | Authority | Shell responsibility |
|---|---|---|
| Portfolio registry/detail | `market_os.api` and `market_os.store` | Render validated GET responses and links |
| BTC datasets/candles/manifests/records | `HistoryStore` through the versioned API | Preserve bounded pages, hashes, and exclusive cursors |
| B2/B3 research catalogs/details | `BtcResearchInspectionStore` through the versioned API | Render summaries and bounded detail state |
| Gateway status | loopback health/readiness response | Show available/unavailable/unknown state |
| CLI | `market_os.cli` and `apps/cli` | Remain a scriptable projection of the same contracts |

The shell may hold navigation, cursor, viewport, and transient loading state.
It must not calculate accounting, risk, equity, fills, research metrics, or
fingerprints locally, and it must not create or mutate a store.

## Initial read-only surface

The first shell slice covers:

1. overview and gateway status;
2. portfolio registry and portfolio detail;
3. BTC dataset registry and bounded candle detail;
4. ingestion-manifest catalog, detail, outcomes, gaps, and provenance;
5. B2/B3 research-run catalogs and bounded details.

Every view is GET-only and uses the existing `market-os.*@v1` envelope. A
missing store renders an empty/unavailable state without initializing storage;
invalid limits, cursors, revisions, and IDs fail closed.

## Local safety boundary

- synthetic, paper-only, local-only, and read-only;
- loopback gateway only (`127.0.0.1` by default);
- no credential or provider path;
- no mutation, approval, order, live venue, or network acquisition route;
- no Kafka, Spark, Airflow, or distributed ownership dependency;
- disconnected DirectAdmin static preview remains a separate artifact and is
  never used as the connected shell transport.

## Responsive and accessibility gates

- verify at 320, 375, 768, 1024, and 1440 pixels;
- no page-level horizontal overflow; wide tables scroll only in labelled
  regions;
- primary links and actions have 44px touch targets and visible keyboard focus;
- the local/read-only/paper boundary and gateway state stay visible on mobile;
- preserve `main#main-content`, skip-link behavior, DOM order, and reduced
  motion behavior from the existing operator shell.

## Parity acceptance

The shell is ready for promotion to a selected desktop/mobile platform only
when the following are demonstrated against the same fixture and configured
local store:

- CLI, HTTP, Next.js, and shell payloads agree on envelope, ordering, bounds,
  cursors, hashes, and exact decimal strings;
- empty-store and invalid-input behavior agrees across all surfaces;
- no shell action writes files, opens a provider transport, or changes broker
  state;
- typecheck/build, focused parity tests, responsive browser checks, evidence
  validation, secret scan, and `git diff --check` pass.

## Platform decision

No desktop or mobile framework is selected by this contract. Choosing Tauri,
Electron, React Native, Flutter, or another platform requires a separate
decision record with packaging, update, filesystem, and local gateway policies.
Until that decision is made, keep the implementation in the existing
server-rendered Next.js shell and do not create a generic `apps/app` bucket.
