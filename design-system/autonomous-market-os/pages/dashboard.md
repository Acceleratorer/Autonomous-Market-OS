# Local operator dashboard

These rules specialize the project design system for the local portfolio
registry and portfolio detail pages.

- Keep the dark, data-dense palette and green boundary/status accent from
  `MASTER.md`.
- Use the system sans-serif and monospace stacks. The generated Google Fonts
  suggestion is not loaded because this local surface has no external asset
  dependency.
- Render exact values returned by the Python broker. Do not derive equity,
  performance, exposure, or other financial metrics in the web layer.
- Portfolio equity history may be shown as a static line chart for only the
  latest bounded page. Keep exact broker values and timestamps in a contained
  table, and state when older risk-window samples are omitted.
- Show only records supplied by the validated B4 API. Do not add simulated
  chart points or placeholder market activity.
- Keep the pages server-rendered and GET-only. Use the Python API as the single
  source for accounting, risk, order state, and reservations.
- Avoid decorative motion and chart animation on this frequently inspected
  surface. Keep only short color and border feedback; respect reduced motion.
- At 320, 375, 768, 1024, and 1440 pixels, prevent page-level horizontal
  scrolling. Wide data tables may scroll inside their own labelled region.
- Keep keyboard focus visible on labelled table-scroll regions and make the
  skip-link target (`main#main-content`) programmatically focusable.
- At widths up to 560 pixels, keep primary navigation in a two-column grid so
  section links remain touch-sized without pushing page content far below the
  fold. At tablet widths, let links wrap in source order.
- On nested detail routes, keep the parent section highlighted in primary
  navigation with `aria-current="location"`; reserve `aria-current="page"` for
  the exact current route.
- Keep the synthetic, paper-only, local, and read-only boundary visible on the
  registry and detail pages.
