# ADR-0013: Approval-gated single synthetic live model smoke

- Status: accepted for offline preparation; live execution pending approval
- Date: 2026-10-16
- Scope: one synthetic OpenAI Responses API validation request

## Decision

Prepare one optional OpenAI Responses API smoke using the local synthetic
research fixture and `gpt-6.1-sol`. Keep the request outside ordinary CI and
require a separate explicit execution approval after offline validation.

## Guardrails

- Market OS remains the orchestration, grounding, fallback, risk, and paper-only
  owner. Model output cannot authorize an order.
- Exactly one logical request, zero retries, no concurrency, 20-second timeout,
  16,000-byte input bound, 512-token output bound, and $0.02 maximum spend.
- `store:false`, no tools, synthetic internal fixture only, no credentials in
  payloads or evidence, and no raw provider payload persistence.
- Existing citation, exact-quote, hash, lineage, output-size, secret-like, and
  classified-rendering gates remain authoritative. Failed grounding preserves
  deterministic M2.3 synthesis.
- Ordinary pushes, pull requests, and default workflows never make a provider
  request. The explicit `MARKET_OS_M2_8_LIVE_SMOKE_APPROVED=1` gate is required
  by the execution harness in addition to the adapter's approval settings.

## Alternatives rejected

- Running the smoke during offline preparation: rejected because the prompt
  requires a separate human approval before any network request.
- Running it in pull-request or push CI: rejected because credentials and
  nondeterministic provider behavior must not enter ordinary CI.
- Allowing a retry: rejected for this single-smoke evidence slice; a provider
  error must preserve deterministic fallback without a second request.
- Sending real market or account data: rejected; the fixture is synthetic and
  explicitly classified as internal test data.

## Consequences

The offline milestone can prove configuration, payload, redaction, and gate
behavior while leaving live latency, usage, cost, entitlement, and provider
quality unresolved. A later approved invocation may produce one bounded result;
its transport and grounding outcomes must be recorded separately.
