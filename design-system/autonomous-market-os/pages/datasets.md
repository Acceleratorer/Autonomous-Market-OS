# Local BTC dataset registry

This page extends `dashboard.md` for the `/datasets` route.

- Keep the dark, dense palette and system font stacks used by the operator.
- Present exact values from the local B1 catalog. Do not calculate returns,
  quality scores, or file-integrity state in the web layer.
- Label the registry as local and read-only. State that catalog metadata does
  not replay or verify Parquet files.
- Use server-rendered GET pagination. Keep the wide table inside its labelled,
  keyboard-scrollable region at narrow widths.
- Keep interactions to navigation and short color/border feedback. Do not add
  charts, simulated rows, external fonts, GSAP, or decorative motion.
