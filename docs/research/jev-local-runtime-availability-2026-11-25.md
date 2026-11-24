# Jev Local Runtime Availability

**Checked:** 2026-11-25

**Scope:** Authentic TypeSafe Jev, local/VPC deployment, and offline use

## Findings

- TypeSafe's public API reference documents authenticated requests to its hosted API (`GET /v1/models` and `POST /v1/systemone`). It does not provide a local runtime package or a weight/runtime manifest: [TypeSafe API reference](https://api.typesafe.ai/redoc).
- TypeSafe's enterprise page lists a question about running Jev in a customer VPC or on-premises, but the answer is not present in the page text available for review: [TypeSafe Enterprise](https://typesafe.ai/enterprise). This leaves private deployment availability unresolved; it does not prove that TypeSafe cannot offer one privately.
- The project runtime and model directories inspected on this date contained no Jev- or TypeSafe-named runtime artifacts. The installed local assessor remains the separately identified Qwen runtime described in [ADR-0058](../decisions/ADR-0058-btc-jev-connectivity-only-local-assessor.md).
- TypeSafe Sales had not replied to the project's local-deployment inquiries sent on 2026-11-20 and 2026-11-21, as of this check.

No Jev API request or BTC packet transmission was made during this review.

## Gate

Treat authentic local Jev availability and local-use terms as **unverified** until TypeSafe provides written confirmation and verifiable artifacts covering the exact Jev release, runtime and weight hashes, supported hardware, offline operation, telemetry/network requirements, updates, and permitted non-commercial research use. Do not label Qwen or another compatible implementation as Jev.
