# Application Surfaces Contract

**Status:** Implemented locally on 2026-10-28.

## Layout

- `market_os/` remains the canonical domain and compatibility package.
- `apps/web/public/` is the canonical static read-only dashboard source.
- `apps/cli/` is a thin application entrypoint over `market_os.cli`.
- `apps/gateway/` is a thin application entrypoint over the existing local
  `serve` command and loopback-only gateway.
- `apps/web/operator/` is the local connected shell; its canonical assets are
  `index.html`, `operator.js`, and `operator.css`.
- `apps/web/next-operator/` is the local Next.js operator UI; its server-rendered
  pages consume the existing loopback read-only contract. `/overview` presents
  bounded catalog previews; `/` remains the portfolio registry.
- `docs/hosting/market-os/` remains a compatibility copy for existing preview
  and hosting consumers.

## Naming and compatibility

Surface names are polished at the application boundary. Existing capability
module names such as `market_os.api`, `market_os.cli`, and the historical
compatibility aliases remain stable because tests, package entrypoints, and
local wrappers depend on them. A wholesale rename is deferred until a real
consumer can move through a versioned compatibility window.

## Web packaging

`scripts/build_web_artifact.py` verifies the canonical web source against the
legacy preview and packages a new static output directory. The artifact is
synthetic, paper-only, read-only, and contains no API connection, credentials,
portfolio state, or mutation controls. Public deployment, authentication, and
connected web operations remain separate U5 gates.

The framework selection gate is recorded in [ADR-0027](decisions/ADR-0027-web-stack-selection.md).
U5.8 records the user's selection of Next.js for a separate local-only,
read-only operator UI; it does not change the static preview or authorize
connected deployment.

U5.3 adds a deterministic static artifact manifest and local-only `X-Request-ID` diagnostics. These do not authenticate users or authorize shared access.

The gateway retains `app.js` and `styles.css` as read-only compatibility aliases
for existing local links while the product-facing asset names use the explicit
`operator.*` prefix.
