# ADR-0012: Optional model adapter and offline CI foundation

- Status: accepted for M2.7
- Date: 2026-10-16
- Scope: recorded model summaries, approval-gated provider boundary, fusion CI

## Decision

Keep deterministic cited synthesis as the default. Add a stdlib-only optional
OpenAI Responses adapter behind `SummaryModelProvider`, with `gpt-6.1-sol` as
the explicit configured model. Add synthetic recorded Responses fixtures and
fusion-repository GitHub Actions workflows. The live adapter fails closed
unless complete approval, safety, budget, and retention configuration exists.

## Constraints

- No live call, credential, SDK, broker, external market/document provider, or
  live execution is part of M2.7.
- The adapter is not imported by the default offline workflow.
- The existing citation/grounding gate and deterministic fallback remain
  authoritative.
- `ModelUsage` uses `None` for unavailable provider usage; observed counts are
  non-negative integers.
- Requests set `store: false`, send bounded normalized synthesis data, and use
  at most one logical request plus one safe transient retry (at most two
  transport attempts).
- Spend is reserved cumulatively at the bounded worst-case request estimate
  before transport; reuse cannot silently exceed the configured ceiling.
- When both provider token counts are present, estimated cost uses the
  documented standard model rates; missing counts remain unknown.
- CI checks the offline suite, compilation, evidence, diff hygiene, and
  high-confidence secret patterns without requiring credentials.

## Alternatives rejected

- Adding the OpenAI SDK: unnecessary for this bounded adapter; stdlib HTTPS
  keeps optional provider dependencies out of the core.
- Making OpenAI the default: rejected because credentials, retention, account
  entitlement, and spend approval are not established.
- Running a live smoke in CI: rejected because CI must remain credential-free
  and deterministic.
- Adding broad security scanners: rejected because unreliable/noisy checks
  would reduce signal.

## Consequences

Recorded responses provide contract and gate coverage but do not establish real
model quality. Any live smoke needs separate approval and must use one synthetic
case within the configured request and spend bounds. Market OS remains the
orchestration and safety owner.
