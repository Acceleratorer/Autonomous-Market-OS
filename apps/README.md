# Application surfaces

These folders hold the product interfaces; portfolio accounting, risk and
persistence remain in `market_os`.

- `web/` contains the static read-only dashboard source and the local operator
  shell (`web/public/` and `web/operator/`).
- `cli/` provides an application entrypoint for the existing command interface.
- `gateway/` provides an entrypoint for the existing local HTTP service.

Desktop and mobile applications are future consumers of the shared contracts.
Use `apps/desktop/` or `apps/mobile/` only when a concrete shell workflow is
approved; keep the active surface split explicit instead of adding a generic
`apps/app/` bucket.
