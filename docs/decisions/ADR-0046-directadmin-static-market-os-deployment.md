# ADR-0046: Deploy the disconnected Market OS preview to DirectAdmin

**Status:** Static-preview target selected on 2026-10-29; deployment is deferred
until local milestones are closed and hosting prerequisites are available.

## Decision

Deploy only the disconnected static preview from `apps/web/public/` to
`/domains/accel.io.vn/public_html/market-os`, served at
`https://accel.io.vn/market-os/`. The static artifact contains exactly
`index.html`, `.htaccess`, and `DEPLOYMENT.txt`. The directory location supplies
the `/market-os/` URL base; this artifact has no client router or external
assets that need a build-time prefix.

The deployment follows the existing Wuwa Map DirectAdmin File Manager API
workflow: build once, upload an artifact named with the commit SHA, extract to a
staging directory outside `public_html`, then move the current Market OS
directory to the single rollback slot and promote staging. Production
verification compares the served HTML hash with the artifact and checks the
existing `/`, `/waifu`, `/waifu/`, `/wuwa-map`, and `/wuwa-map/` routes. A failed promotion or
verification restores the pre-deploy directory and verifies it.

## Security and runtime boundary

The static preview contains no portfolio, dataset, API, credential, sign-in, or
mutation data, so this path does not require a login gate. The local Next.js
operator is a separate runtime that reads private data from loopback Python
services. It is not part of this static artifact and remains local until U5.5
defines and verifies application authentication, authorization, storage
isolation, and operations. Cloudflare Access at the edge alone is not treated
as origin protection for that future private application.

No web-root configuration for `/`, `/waifu`, or `/wuwa-map` is modified. The
workflow uses the same four secret names as Wuwa Map, but GitHub repository
secrets are scoped to a repository; Autonomous-Market-OS needs its own values
or environment-scoped copies. Secret values are never stored in this repo.

## Verification and rollback

- The quality job runs the static contract test, verifies the source/legacy
  copies, builds the exact artifact, and uploads it under the triggering SHA.
- The deploy job only runs after an explicit workflow dispatch on `main`; a
  push never deploys. It fails before calling DirectAdmin when any required
  secret is missing.
- The recorded workflow attempt stopped at missing-secret validation and did
  not change site files. A valid DirectAdmin TLS chain is also required; the
  deployment report records the observed certificate expiry.
- Staging, temporary archives, failed releases, and the preserved previous
  rollback slot live under `/domains/accel.io.vn/`, outside `public_html`.
- The production path is changed only by the DirectAdmin move operations for
  `market-os`. `/`, `/waifu`, `/waifu/`, `/wuwa-map`, and `/wuwa-map/` must
  return HTTP 200 before and after promotion.
- If the previous Market OS path returned 404 before its first deployment,
  failed promotion restores that absent state; there is no older version to
  retain as a rollback slot until the first release succeeds.
