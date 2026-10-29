# U5 Local Read-Only Operator Dashboard

**Status:** Local slice accepted on 2026-10-28.
**Scope:** Synthetic, paper-only, GET-only inspection of an existing B4 portfolio.

## Contract

`GET /v1/b4/portfolios/<portfolio_id>/dashboard` returns an HTML operator view built from the same `B41Broker` inspection and snapshot seams used by the JSON API and CLI.

The page shows portfolio identity, the synthetic/paper/read-only boundary, balances, mark price, processed-event count, persisted order states, and risk/fill-time rejection reason codes.

The page contains no command form, mutation control, provider path, credential input, or live venue behavior. `POST` remains unsupported and returns the existing not-found response for this route.

## Verification

`market_os/tests/test_portfolio_broker.py::test_u5_operator_dashboard_is_read_only_and_escaped` and [U5-LOCAL-ACCEPTANCE.md](U5-LOCAL-ACCEPTANCE.md) verify HTML content type, escaped order identifiers, absence of a form, health/readiness, JSON parity, query rejection, and POST rejection. The static preview also passes the Node contract test and a Playwright browser smoke with zero console errors.

## Remaining U5 gates

This local dashboard does not claim deployment readiness. Authentication/access control, service observability, backup/restore, retention, migration, and shared-portfolio semantics remain separate gates. The dashboard must stay read-only until a separately approved mutation contract exists.
