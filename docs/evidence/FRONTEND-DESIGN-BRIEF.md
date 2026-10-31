# Market OS institutional finance workspace

Date: 2026-10-31

## Design read

This is an `Operate` surface for an owner/quant inspecting synthetic BTCUSDT
paper state, research evidence, and broker-controlled accounting. The interface
should feel like a calm instrument panel: dense enough for daily inspection,
quiet enough to preserve trust, and explicit about what is unavailable or
disabled.

## Direction

`Graphite Instrument Panel`

- Foundation: deep graphite and ink surfaces, no decorative glass layer.
- Type: warm off-white display hierarchy, slate supporting copy, tabular
  numerals for measurements and fingerprints.
- Semantics: cyan for market context, emerald for verified/healthy, amber for
  uncertainty and execution-off state, red only for blocked or negative state.
- Shape: compact 6-10px controls and panels, restrained 8px border radius,
  thin separators, no oversized hero blocks.
- Navigation: persistent rail plus compartmentalized status bar.
- Signature: the four-state operator status strip:
  `SYNTHETIC`, `PAPER`, `READ ONLY`, `EXECUTION OFF`.

## Dials

- Variance: 4/10. Predictable structure is useful for an inspection tool.
- Motion: 3/10. Short transitions and orientation feedback only.
- Density: 9/10. Tables, charts, and exact values remain first-class.

The chart signature is a restrained OHLCV candlestick panel with a volume
strip, visible legend, exact readouts, and a short CSS draw-in. No 3D chart
distortion is used because price scale and candle geometry must remain
readable and auditable. Reduced motion renders the same chart statically.

The futuristic signature is spatial layering around the instrument and chart,
not a decorative 3D object. When no validated dataset is mounted, the desk
shows an explicit synthetic-fixture chart surface instead of inventing prices.
No WebGL or heavyweight 3D dependency is needed.

All routes share the same instrument-panel system: graphite surfaces, warm
white hierarchy, cyan data context, emerald health, amber uncertainty, red
blocked state, compact status compartments, tabular numbers, and narrow
separators. Synthetic catalog/session/comparison pages use the same product
identity without importing the Next.js shell or adding a client runtime.

## Layout decisions

- Overview: system status strip, bounded resource metrics, and resource panels.
- Market desk: chart context on the left, locked execution and research lineage
  on the right, watchlist/book context below.
- Dataset detail: chart plus exact OHLCV table and integrity metadata.
- Research detail: metrics, experiment identity, promotion state, and
  evidence lineage.
- Mobile: single-column reading order, preserved status bar, labelled table
  scroll regions, and no horizontal document overflow.

## Boundary decisions

- Server-rendered GET/HEAD inspection remains the only operator behavior.
- Python remains authoritative for accounting, risk, P/L, portfolio state,
  fingerprints, replay, and execution state.
- No provider calls, live quotes, credentials, POST routes, order mutation, or
  client-side authorization were introduced.
- Public `/market-os` remains a script-free static preview; dynamic operator
  promotion stays behind the owner Linux/systemd/Tailscale gate.
