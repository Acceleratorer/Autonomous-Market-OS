# Market OS Frontend Design System

**Status:** approved direction for U5 web surfaces and U6 desktop shell
**Product language:** professional finance console with blockchain provenance and a research-lab edge
**Primary mode:** Operate

## Design read

Market OS is an operator surface for inspecting deterministic market, portfolio,
risk, release, and evidence state. The interface should make four questions easy
to answer:

1. What is the system state now?
2. Where did this data come from?
3. Which controls or boundaries are active?
4. Which release is running and can it be rolled back?

The visual system is shared by the Next.js web operator and the Electron shell.
Electron adds a native window and runtime boundary; it does not get a second
renderer or a second component language.

## Dials

| Dial | Value | Intent |
|---|---:|---|
| Variance | 4/10 | Distinctive through hierarchy and evidence structure |
| Motion | 2/10 | State change, refresh feedback, and chart continuity only |
| Density | 8/10 | Compact operator views with readable data rows |

## Visual principles

- Dark primary theme with high contrast and restrained surfaces.
- Finance semantics first: green for healthy or positive, amber for pending or locked, red for failure or loss.
- Blockchain cues come from hashes, fingerprints, lineage, versions, and append-only event rows.
- Lab cues come from dataset revisions, manifests, experiment runs, and evidence chains.
- Panels communicate hierarchy. Lists and tables use spacing and dividers instead of a card for every row.
- No crypto-neon glow, decorative scanlines, AI-purple gradients, or ambient animation.
- Read-only and paper-only boundaries stay visible in the same place across routes.

## Core tokens

```css
:root {
  --mos-canvas: #070b10;
  --mos-sidebar: #090e14;
  --mos-panel: #0c1219;
  --mos-panel-raised: #111a23;
  --mos-line: #26333f;
  --mos-line-strong: #3a4c5c;
  --mos-ink: #f2f0e9;
  --mos-muted: #a1adb6;
  --mos-subtle: #7e8c97;
  --mos-data: #75d9f5;
  --mos-positive: #91d8a4;
  --mos-warning: #e6bd72;
  --mos-danger: #f08e8e;
  --mos-radius-panel: 8px;
  --mos-radius-control: 6px;
  --mos-shadow-panel: 0 18px 44px rgb(0 0 0 / 18%);
}
```

The Next.js operator already owns the canonical CSS token implementation in
`apps/web/next-operator/src/app/globals.css`. Static and compatibility surfaces
should keep these values in their local CSS because U5.2 intentionally packages
an exact three-file artifact.

## Typography

- UI and prose: IBM Plex Sans direction, with the current system sans stack as a zero-dependency fallback.
- Values, identifiers, timestamps, hashes, and status codes: IBM Plex Mono direction, with the current mono stack as fallback.
- Headings are compact and left aligned. Large display typography is reserved for the public preview, not dense operator pages.
- Labels use uppercase mono text sparingly. A section does not need a kicker if its title already explains the content.

## Surface map

### Web operator and Electron renderer

```text
sidebar
  workspace: overview, market desk, portfolios
  evidence: datasets, research

topbar
  workspace / current surface
  synthetic / paper / read-only / execution boundary
  gateway state

main
  market state strip
  chart plus risk and execution rail
  evidence chain
  bounded tables and drill-in links
```

### Public static preview

The preview communicates the product boundary without pretending to expose
portfolio state. It uses the same tokens and status language, while keeping a
lighter narrative structure:

```text
brand and boundary
preview status
system contract
private operator surfaces
```

## Component vocabulary

- `StatusRail`: gateway, data freshness, authority, venue, and execution mode.
- `MarketChart`: bounded candles with exact tabular values preserved below.
- `RiskLedger`: limits, outcomes, approvals, reservations, and execution locks.
- `EvidenceChain`: dataset revision → manifest → research run → portfolio.
- `FingerprintRow`: schema, hash, source, version, and timestamp.
- `RuntimePanel`: app version, Python sidecar, signature, current slot, known-good slot, and rollback availability.
- `EventStream`: append-only operational events with stable sequence values.
- `DataTable`: exact values, bounded rows, keyboard focus, and mobile overflow handling.

## State semantics

| State | Color | Meaning |
|---|---|---|
| Available / healthy | positive green | Service or evidence is usable |
| Synthetic / data | data cyan | Data context or fixture boundary |
| Pending / locked / execution off | warning amber | Deliberate boundary or incomplete gate |
| Unavailable / failed / loss | danger red | A real error or negative outcome |
| Read only / neutral | muted grey | Informational boundary |

Copy must distinguish `not promoted`, `execution disabled`, `data unavailable`,
and `gateway unavailable`. These are different operational states.

## Motion and interaction

- 160–240ms transitions for hover, focus, and active feedback.
- Candle or data refresh may use a short opacity/translate transition.
- New evidence rows may highlight once, then settle.
- No looping decorative motion.
- Respect `prefers-reduced-motion` for every transition or chart entrance.
- Interactive targets remain at least 44px on touch surfaces.
- Focus rings use the data cyan token and remain visible against the dark canvas.

## U5.5 and U6.4 product surfaces

The connected web gate remains behind owner-VM promotion and rollback. The UI
can expose the boundary without implying that access is enabled:

```text
Private operator
Connected access: pending owner-VM promotion
Execution: disabled
```

U6.4 adds a small release/runtime view using the same system:

```text
Version        0.6.4
Python sidecar Ready
Signature      Verified
Current slot   Candidate
Known-good     0.6.3
Rollback       Available
```

This view is observational. It does not add credentials, provider calls,
mutation routes, or live trading controls.

## Review checklist

- Is the current system state visible within the first viewport?
- Can every evidence claim link back to a bounded source record?
- Are read-only, paper-only, and execution boundaries explicit?
- Are green, amber, and red used consistently with their semantic meanings?
- Do tables remain usable at 320px, 375px, 768px, 1024px, and 1440px?
- Does the Electron shell reuse the same Next.js renderer and tokens?
- Does every loading, empty, unavailable, and invalid state explain the next safe action?
- Does the interface remain useful without a model, network, credentials, or live venue?

## Implementation order

1. Keep `apps/web/next-operator` as the canonical renderer.
2. Apply shared tokens and status semantics to Overview, Market Desk, Datasets, and Experiments.
3. Add the observational Runtime/Release surface for U6.4.
4. Keep `apps/web/public` and `apps/web/operator` visually aligned without changing their exact packaging contracts.
5. Verify the Electron wrapper against the same renderer after packaging work lands.

## Current renderer mapping

The canonical Next.js renderer now exposes the component vocabulary directly:

- `StatusRail` is the shared gateway, authority, data-mode, and execution strip on Overview.
- `MarketChart` is the existing bounded OHLCV renderer used by Market Desk; it keeps exact values below the visual.
- `RiskLedger` and `EvidenceChain` keep Market Desk risk and lineage rows compact and provenance-first.
- `FingerprintRow` and `DataTable` are shared by research and dataset inspection pages.
- `/runtime` is the observational U6.4 release surface using `RuntimePanel` and `EventStream`.

The runtime surface reports the current local shell truth (`U6.4-A` unsigned
artifact plus the locally verified U6.4-B signing/promotion/rollback contract).
When a signed artifact is present it reads the external signature and slot
metadata; it must not be read as owner-VM promotion evidence. Platform-specific
Python distribution and U5.5 connected access remain pending owner-controlled
gates, and the renderer keeps local, synthetic, paper-only, read-only, and
execution-disabled boundaries visible.
