# Jev Local Runtime Availability

**Checked:** 2026-11-25

**Scope:** Authentic TypeSafe Jev, local/VPC deployment, published local-use terms, vendor response, and a bounded local artifact scan. Read-only; no Jev API request, email, or BTC packet was sent.

## Finding

Authentic local Jev remains **unverified**. Current first-party public materials document Jev as a hosted TypeSafe API model. The official Enterprise page still lists the VPC/on-premises question but the answer is not present in its fetched content. No public Jev weights or vendor-authenticated local runtime manifest was found. This does not rule out a private TypeSafe offer or a separate agreement.

## First-party technical evidence

- TypeSafe's [model catalog](https://docs.typesafe.ai/models) identifies Jev 1.14 (`jev-1.14.0`) as its newest release and says the catalog models are served through `POST /v1/systemone`.
- The [System One API reference](https://docs.typesafe.ai/api/system-one) gives `https://api.typesafe.ai/v1/systemone` and requires bearer authentication. It documents a remote API request, not local inference.
- The [Enterprise page](https://typesafe.ai/enterprise) includes “Can we run Jev in our own VPC or on-premises?” but its fetched page exposes the question without an answer. The answer is unresolved by this check.
- The [official TypeSafe Hugging Face models page](https://huggingface.co/typesafeAI/models) currently says there are no public models. The [TypeSafe GitHub organization](https://github.com/orgs/typesafe-ai/repositories) lists 12 public repositories; the visible repositories include SDKs, examples, an n8n integration, a `vllm` fork, and the [System One Python adapter](https://github.com/typesafe-ai/system-one-adapter-python). The adapter is described as a TypeSafe client replacement backed by LLM APIs; neither that listing nor the public model page supplies a Jev checkpoint or local Jev serving package. These are bounded public-listing checks, not proof that private distribution is impossible.

## Public terms

The [Master Customer Agreement](https://typesafe.ai/legal/mca), last updated 2026-09-23, defines the Services in §1 as TypeSafe-hosted web and API services. Section 2.1 grants access to those Services and integration of the API; the posted agreement does not expressly grant a right to obtain or run Jev model weights locally. Section 2.3(b) restricts use of the Services or Output to distill a model, train an imitator, or develop or facilitate a similar or competing product. A separate written agreement may govern instead. This is a reading of the posted text, not legal advice and not a conclusion about a private offer.

## Vendor response check

Two read-only Gmail searches found no matching messages from `@typesafe.ai` in the last 30 days and none from `sales@typesafe.ai` since 2026-11-01. Both searches excluded Spam and Trash. This does not establish anything about other contact channels.

## Bounded local artifact check

On this Windows host, a depth-limited filename/directory scan found no `jev`, `typesafe`, `systemone`, or `local-jev` runtime/model artifact in the default Hugging Face cache, configured `HF_HOME` / `HF_HUB_CACHE` / `TRANSFORMERS_CACHE` locations, LM Studio cache locations, or the checkout's `.market_os` tree. The checkout's matching `.market_os` entries were Jev connectivity records/reservations, not weights or a serving runtime. A directory-name scan of the installed pinned CPython 3.11.18 `Lib/site-packages` found no Jev, TypeSafe, or System One package; command lookup found no `jev` or `local-jev` command; process-name lookup found no Jev/TypeSafe process. No credential values were read. The scan does not cover every custom directory, private registry, or vendor delivery channel.


## Separate System One-compatible project

The independent [`amithgc/local-jev` project](https://github.com/amithgc/local-jev) advertises a local server that speaks Jev's System One wire format while running open models, including Qwen and an entailment model. Its README says the response reports the model that actually answered (for example, `llm-qwen3.5-4b`) and labels the project research-grade, not a finished product. The project source is MIT-licensed ([license](https://raw.githubusercontent.com/amithgc/local-jev/main/LICENSE)); its model weights have separate model-specific terms. Its README says the first launch fetches model weights and that the server can then run locally. This is a possible **Jev-compatible substitute**, not TypeSafe Jev; no install or runtime evaluation was performed here.

## Project consequence

Keep [ADR-0058](../decisions/ADR-0058-btc-jev-connectivity-only-local-assessor.md): hosted Jev remains connectivity-only, and BTC packets stay local. Keep the current assessor labeled **Qwen, not Jev**. Do not call an independent wire-compatible implementation Jev or use hosted Jev outputs to train one. Reconsider authentic local Jev only after TypeSafe provides written local/VPC/on-premises terms and a vendor-authenticated manifest identifying the Jev version, runtime, weight hashes, supported local execution method, and offline/network requirements.
