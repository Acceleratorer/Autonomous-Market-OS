# Frontend verification report

Date: 2026-10-31

Scope: existing Market OS local operator surfaces, including the Next.js
operator, the read-only Market desk, the legacy synthetic catalog/session/
comparison HTML surfaces, and the disconnected static `/market-os` preview.

## Result

Local frontend verification is green for the approved synthetic, paper-only,
read-only boundary. The static public preview is deployed at `/market-os`.
The dynamic Next.js operator remains loopback-local; private VM/Tailscale
promotion is an owner-controlled external gate and was not run here.

## Institutional redesign follow-up

The visual system now uses a `Graphite Instrument Panel` direction: graphite
surfaces, warm off-white type, slate secondary text, cyan market context,
emerald healthy state, amber uncertainty, and red only for blocked/negative
states. The shell uses a persistent rail, compartmentalized status bar, dense
numeric readouts, thinner separators, flatter panels, and deliberate chart
hierarchy instead of generic SaaS card grids.

The overview now exposes `SYNTHETIC`, `PAPER`, `READ ONLY`, and `EXECUTION OFF`
as explicit status states. The Market desk keeps its bounded chart, watchlist,
portfolio/risk context, research lineage, and locked execution state. The
synthetic catalog and comparison surfaces received the same responsive
instrument-panel treatment and no longer overflow on mobile.

The Market desk chart is now an exact bounded OHLCV candlestick view with a
volume strip, legend, units, time range, and exact readout values. Candle
materialization uses a short CSS-only draw-in and disables movement under
`prefers-reduced-motion`; no inline style variables or client-side data
mutation were introduced.

The desk uses restrained chart materialization and spatial layering around the
instrument header. When no validated dataset exists, fixture mode is explicit:
`SYNTHETIC FIXTURE`, `PAPER`, `READ ONLY`, `EXECUTION OFF`, and no invented
price values. Fixture smoke verified the OHLCV chart and animation without CSP
errors; reduced-motion smoke verified the animation resolves to `none`.

The shared page-header context line, status compartments, panel borders,
numeric table treatment, and evidence language now apply to overview,
portfolio, datasets, research, Market desk, and synthetic HTML surfaces. The
catalog, session, and comparison HTML views now carry the same Market OS
identity/status treatment and responsive table behavior.

Browser evidence:

- `output/playwright/institutional-redesign-overview-1440.png`
- `output/playwright/institutional-redesign-desk-fixture-1440.png`
- `output/playwright/institutional-redesign-desk-fixture-375.png`

Public preview evidence:

- `https://accel.io.vn/market-os/?v=institutional-finance` returned `200`.
- The public entry point shows the shared synthetic/paper/read-only/
  execution-off status vocabulary and the private Market desk map.
- `DEPLOYMENT.txt` remains `403`; no public portfolio or candle data was
  uploaded.

## Files touched or verified for this milestone

- `apps/web/next-operator/src/app/desk/page.tsx`
- `apps/web/next-operator/src/components/market-desk.tsx`
- `apps/web/next-operator/src/components/app-shell.tsx`
- `apps/web/next-operator/src/components/ui.tsx`
- `apps/web/next-operator/src/app/globals.css`
- `apps/web/next-operator/src/lib/market-api.ts`
- `market_os/synthetic_server.py`
- `apps/web/public/index.html`
- `docs/hosting/market-os/index.html`
- `deploy/u5-5/README.md`
- `docs/U5.8-NEXT-LOCAL-OPERATOR-WEB.md`
- `docs/FRONTEND-FINANCE-REFERENCE.md`

Unrelated existing worktree changes were preserved.

## Functional surfaces

- Next.js routes `/`, `/overview`, `/desk`, `/datasets`, `/experiments`, and
  `/healthz` returned `200` in production smoke.
- `/desk` uses bounded local BTC candle data, catalog-backed watchlist rows,
  portfolio/risk context, research lineage, and an explicit `OFF` execution
  state.
- Invalid query and invalid portfolio paths render bounded read-only error
  states without exposing raw backend errors.
- Synthetic catalog, session dashboard, and comparison dashboard returned
  `200`; the catalog and comparison surfaces were corrected to avoid mobile
  horizontal overflow.

## Checks

| Check | Result |
| --- | --- |
| `npm run typecheck` | Pass |
| `npm run build` | Pass |
| Configured lint script | Not present in `package.json`; no lint claim made |
| Frontend unit/component test script | Not present in `package.json` |
| Focused synthetic server/catalog tests | 12 passed |
| Impeccable detector | 0 findings |
| `git diff --check` | Pass |
| Source/build secret-pattern scan | No hits |
| Next production browser smoke | Pass |
| Synthetic catalog/session/comparison browser smoke | Pass |
| Static artifact contract check | Pass |

## Browser and accessibility evidence

- Next production smoke covered 375, 768, 1024, and 1440 pixel widths.
- Static preview smoke covered 375, 768, and 1440 pixel widths.
- Synthetic catalog, session, and comparison smoke covered desktop and mobile.
- No document horizontal overflow was observed.
- Keyboard focus outline was visible.
- `prefers-reduced-motion: reduce` removed entrance transform/filter motion.
- Main landmark, primary navigation, chart accessible names, and execution
  state text were present.

## Console and network boundary

- Production Next smoke had no fresh console errors and no failed local
  resource responses.
- Browser requests were GET-only.
- Static preview had no external resource requests.
- No credential, token, provider configuration, real market-data acquisition,
  trade submission, order mutation, portfolio mutation, or execution mutation
  occurred.

## Remaining owner decision

Promote the dynamic Next.js operator only from the owner-controlled Linux VM
through the existing systemd/Tailscale Serve package after the owner provides
the SSH/auth context or runs `deploy/u5-5/promote.sh` on that VM. The public
DirectAdmin path remains the disconnected static preview by design.
