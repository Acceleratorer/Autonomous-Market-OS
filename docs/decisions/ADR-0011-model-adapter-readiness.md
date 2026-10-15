# ADR-0011: Model-adapter readiness gate

- Status: accepted
- Date: 2026-10-15
- Scope: M2 research-quality evaluation

## Decision

Market OS will not add a real model provider until the versioned M2.5 quality
benchmark passes its integrity thresholds and receives explicit human approval.
The deterministic M2.4 test double is evidence that the local contract and
validator can be exercised; it is not evidence of real-model usefulness.

The readiness status is **Not ready — specific failures remain**. M2.6 may
start real-model adapter planning only after a real-model benchmark run reports
quality, citation integrity, timeout/error, usage, cost, latency, security, and
lineage evidence against the same local corpus.

## Context

M2.3 established exact-quote cited research. M2.4 added an explicit model gate,
deterministic fallback, citation validation, and paper-only separation. A test
double can validate structural behavior but cannot answer whether a hosted or
local language model produces useful, well-grounded summaries. A separate
benchmark is therefore needed before introducing provider credentials or model
runtime dependencies.

## Gate requirements

The report must independently inspect citation precision/recall, quote exactness,
claim support, unsupported and inference handling, evidence coverage, cross-run
isolation, content hashes, replay, fallback, malformed/hostile output,
prompt-injection isolation, secret-like output, lineage, usage, cost, and
latency. Integrity thresholds are 1.0; local latency p95 is at most 100 ms for
the current deterministic benchmark. Real-provider cost and usage reporting are
mandatory for any future real adapter.

Required operational evidence includes timeout/error behavior, persisted
artifacts, read-only benchmark inspection, security review, and human approval.

## Alternatives rejected

- **Promote the deterministic test double:** rejected because it has no real
  linguistic variability, provider cost, or model latency.
- **Add a real provider now:** rejected because the benchmark and promotion gate
  must precede credentials, network access, and new provider dependencies.
- **Use one aggregate quality score:** rejected because it would hide citation,
  fallback, hash, or security failures behind an average.

## Consequences

The benchmark adds local fixture and artifact state but no trading state. It
keeps model adapter readiness observable and prevents structural test-double
success from being misreported as model quality. It also means the next
milestone may remain benchmark hardening if a future real-model run fails.
