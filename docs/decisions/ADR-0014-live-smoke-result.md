# ADR-0014: Approved synthetic smoke blocked by missing credential

- Status: recorded safely; no request made
- Date: 2026-10-16
- Scope: M2.9 approved one-request synthetic OpenAI smoke

## Decision

Record the exact approval and stop before transport because `OPENAI_API_KEY` was
not available through the approved environment or secret boundary. Preserve the
M2.8 pending evidence and deterministic M2.3 fallback. Do not add a credential,
retry, change provider/model, or consume the one-shot reservation.

## Consequences

M2.9 has no transport, latency, usage, cost, response, or real-model grounding
result. A later run requires the credential to be supplied through the approved
secret boundary, then must consume the one-shot reservation and make at most one
request under the fixed M2.8 bounds.
