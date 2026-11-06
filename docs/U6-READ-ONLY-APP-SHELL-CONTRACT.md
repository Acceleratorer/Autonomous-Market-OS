# U6 Read-Only App-Shell Contract

**Status:** U6.1 locally verified; U6.2 selects Electron; U6.3 local shell slice verified; U6.4-A unsigned artifact and local U6.4-B signing/slot contract verified.
**Date:** 2026-11-06

## Purpose

U6 extends the completed local CLI, HTTP, and Next.js read-only projections to
thin desktop and mobile shells. The shell is a presentation adapter. Python
`market_os` remains authoritative for accounting, persistence, recovery, BTC
inspection, research inspection, and all versioned response semantics.

The existing Next.js `AppShell` is the reference interaction model for the
first implementation. U6.1 verifies its gateway status, overview, and BTC
dataset catalog slice against the shared Python/API/CLI contracts. ADR-0053
selects Electron as the desktop container; the native implementation must keep
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

## U6.1 local verification

- `getGatewayStatus()` validates the Python `/readyz` envelope before the
  overview reports gateway availability.
- Overview and BTC dataset registry remain server-rendered GET-only pages using
  `market-api.ts`; the adapter preserves versioned envelopes, 1–100 bounds,
  exclusive cursors, ordering, empty-store responses, and invalid-input
  rejection.
- Focused Python parity checks and the TypeScript shell contract test pass.
- Overview and dataset captures pass at 320, 375, 768, 1024, and 1440 pixels;
  wide tables remain inside labelled horizontal-scroll regions.

## U6.2 native platform selection

- ADR-0053 selects Electron for Windows x64 and Linux x64 desktop targets.
- The existing Next.js shell remains the renderer; Python remains the gateway,
  storage, accounting, and inspection authority.
- U6.2 added no Electron dependency, native scaffold, updater, credentials,
  provider path, mutation route, or deployment. U6.3 now proves the local
  loopback child-process lifecycle and hardened Electron renderer boundary;
  packaging/update rollback remains the U6.4 gate.
- Machine-readable evidence is in
  `docs/evidence/u6-native-platform-selection.json`.

## U6.3 local Electron shell slice

- `apps/desktop/electron` starts the existing Python gateway and server-rendered
  Next.js operator as owned loopback child processes, waits for `/readyz` and
  `/healthz`, and stops descendants on exit.
- The renderer loads only `http://127.0.0.1:<next-port>/overview` with sandbox,
  context isolation, disabled Node integration, web security, denied window
  creation, and loopback-only navigation.
- A real headless Electron smoke on custom ports returned 200 for `/readyz`,
  `/healthz`, and `/overview`; both ports closed after graceful SIGINT cleanup.
- The U6.1 parity suite remains the contract reference. U6.3 adds no provider,
  credential, mutation, live-trading, public-listener, or Tailscale path.
- Machine-readable evidence is in `docs/evidence/u6-electron-shell.json`.
- Reproducible sidecar bundling, signing, and explicit update rollback remain
  the U6.4 gate; no packaged native release exists yet.

## Platform decision

Electron is selected for the first desktop shell by ADR-0053. No mobile
framework is selected. Keep the implementation in the existing server-rendered
Next.js shell and keep the native code isolated under `apps/desktop/electron`.

## U6.4-A unsigned artifact

ADR-0054 defines the first reproducible desktop artifact. It keeps the
Electron shell, Next.js production output, and Python source sidecar in one
target-labelled directory with a SHA-256 manifest and explicit slot metadata.
The sidecar runs with system Python 3.11+ and the dependencies declared by
`pyproject.toml`; Python remains the authority for all domain behavior.

Build and smoke the artifact from `apps/desktop/electron`:

```text
cd apps/web/next-operator
pnpm install --frozen-lockfile
pnpm run build

cd ../../desktop/electron
pnpm install --frozen-lockfile
pnpm run package:unsigned -- --target windows-x64 --output ../../../output/u6.4/market-os-windows-x64
pnpm run smoke:artifact -- --artifact ../../../output/u6.4/market-os-windows-x64
```

The smoke starts the artifact outside the source entrypoints, validates
`/readyz`, `/healthz`, `/overview`, and `/runtime`, checks the unsigned release
state, and confirms graceful loopback cleanup.

## U6.4-B signed release metadata and slots

The local release flow signs the immutable manifest bytes with an external
Ed25519 key. Only `release-signature.json` is stored in the artifact; it
contains the public key, key fingerprint, signature, and manifest SHA-256. The
private key must remain outside the artifact and repository.

`release-slots.cjs promote` verifies the manifest sidecar hash and signature,
writes a verified `current` slot, and preserves the previous current record as
`known-good`. A simulated launch failure restores both metadata files before
returning an error. `release-slots.cjs rollback` verifies the known-good
artifact and its hash before changing current, so tampering leaves the current
slot untouched.

`LocalRuntime` passes the verified signature and slot state to the existing
Next.js renderer. `/runtime` exposes version, Python sidecar, signature,
current slot, known-good slot, and rollback availability as observation only.
U5.5 owner-VM promotion and rollback remain pending, and all private,
read-only, paper-only, and execution-disabled boundaries remain visible.
