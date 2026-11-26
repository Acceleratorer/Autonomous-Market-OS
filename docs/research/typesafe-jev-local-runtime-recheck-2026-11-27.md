# TypeSafe Jev local runtime recheck

**Checked:** 2026-11-27 Asia/Ho_Chi_Minh (UTC+07:00; 2026-11-26 UTC)

**Scope:** Official public TypeSafe/Jev documentation, terms, and artifact listings, plus the already-sent TypeSafe inquiry thread. Read-only; no Jev API request, outbound vendor contact, installation, or BTC packet was made.

## Finding

Authentic Jev local, VPC, or on-premises availability remains **unverified** from public primary sources. Public documentation describes hosted API access. The Enterprise page asks whether Jev can run in a customer VPC or on-premises, but its current page content exposes no answer. A private offer or separate agreement remains possible.

## Confirmed from official sources

- The [model catalog](https://docs.typesafe.ai/models) lists Jev 1.14 (`jev-1.14.0`) and 1.13 (`jev-1.13.0`), says listed models are served through `POST /v1/systemone`, and explains that the same weights serve every account. The [API reference](https://docs.typesafe.ai/api/system-one) gives `https://api.typesafe.ai/v1/systemone` and requires bearer authentication. The [Quick Start](https://docs.typesafe.ai/introduction/quickstart) describes SDK, API, agent-skill, and browser Playground use and directs users to get an API key.
- The [Enterprise page](https://typesafe.ai/enterprise) currently displays “Can we run Jev in our own VPC or on-premises?” but the answer is not present in the page content reviewed. The [2026-11-20 note](typesafe-jev-local-runtime-2026-11-20.md) records an earlier direct browser expansion as “hosted API only”; that answer was not reproduced in this check or the [2026-11-26 check](typesafe-jev-local-deployment-primary-source-check-2026-11-26.md), so treat it as a dated observation rather than a currently reverified FAQ answer.
- The [Master Customer Agreement](https://typesafe.ai/legal/mca) defines the Services as TypeSafe-hosted web and API services (§1) and licenses access to those services and API integration (§§2.1–2.2). Its §2.3(b) restricts use of the Services or Output to distill or imitate the model or develop a similar or competing product. The posted agreement provides no verifiable Jev weights or affirmative local-runtime grant; a separate written agreement may govern. This is a reading of posted terms, not legal advice.

## Bounded negative search results

The official [TypeSafe GitHub organization](https://github.com/orgs/typesafe-ai/repositories) lists 12 public repositories, including SDKs, examples, a System One adapter backed by other LLM APIs, and a generic [vLLM serving engine](https://github.com/typesafe-ai/vllm); the listings reviewed did not expose Jev weights or a local Jev runtime. The reviewed public docs, repository/package listings, and SDK/adapter releases exposed no Jev runtime manifest, checkpoint, container, download URL, or verifiable artifact hash. No public artifact URL or hash can therefore be recorded. This bounded search does not rule out private repositories, a vendor-only channel, or a private enterprise offer.

The existing TypeSafe Sales inquiry thread was rechecked on 2026-11-27. It contains the sent inquiry and follow-up only; no vendor reply or deployment manifest is present. No new email was sent.

## Independent local-compatible projects are not Jev

- [local-jev](https://github.com/amithgc/local-jev) describes itself as an offline System One-compatible server that uses open models, including Qwen and an entailment model. Its README says it is offline after the first model download and labels the project a research project, not a finished product. Its reported benchmark figures are author-published and have not been reproduced in this project. This is a third-party model and server, not TypeSafe Jev or a vendor-authenticated Jev runtime.
- [Bespoke Nimble](https://github.com/bespokelabsai/nimble) describes a locally runnable, open-weight typed-decision model inspired by Jev's System One approach. Its README explicitly says Nimble was not distilled from Jev. It is a separate model, not Jev weights or an official Jev-compatible endpoint.

These projects show that local typed-decision or wire-compatible alternatives exist; they do not change the finding about authentic Jev. No alternative was installed, run, or evaluated here. Do not send BTC packets to hosted Jev or use hosted Jev outputs to train or tune a local substitute under the posted agreement; see the dated contract review in [the earlier Jev research note](typesafe-jev-local-runtime-2026-11-20.md). If actual Jev remains a hard requirement, keep the local assessor identified as Qwen and await written TypeSafe terms and a verifiable runtime/weight manifest.

## Inference and project consistency

The public technical materials support hosted integration, but do not establish whether TypeSafe privately offers local deployment. The legal materials likewise do not settle entitlement to a private runtime without the applicable product-specific agreement. Do not infer Jev identity from an API-compatible local server, an SDK endpoint override, or generic serving infrastructure.

This finding is consistent with [ADR-0058](../decisions/ADR-0058-btc-jev-connectivity-only-local-assessor.md): the ADR keeps BTC packets local and hosted Jev connectivity-only. This recheck does not change that project boundary.

## Evidence gaps

- The Enterprise FAQ answer is not exposed in current public page content.
- No private deployment offer, product-specific agreement, or vendor-authenticated artifact manifest was reviewed.
- Without a runtime/weight manifest and downloadable artifacts, Jev version, local execution method, network requirements, and hashes cannot be verified.
