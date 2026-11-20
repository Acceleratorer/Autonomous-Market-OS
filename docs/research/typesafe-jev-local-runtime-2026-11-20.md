# TypeSafe Jev local runtime and identity

**Checked:** 2026-11-20
**Scope:** Current public TypeSafe documentation, enterprise material, legal terms, and official GitHub repositories; read-only local-runtime discovery. No new Jev API call was made during this local-runtime check.

## Conclusion

No publicly documented and licensed path was found to run TypeSafe's actual Jev model locally or offline while retaining Jev identity. Rechecking the current public catalog on 2026-11-20, it lists `jev-1.14.0` and `jev-1.13.0` and says both use `POST /v1/systemone`; Jev 1.14 is identified as the newest release. The [API reference](https://docs.typesafe.ai/api/system-one) specifies `https://api.typesafe.ai` and required bearer authentication, and the [quick start](https://docs.typesafe.ai/introduction/quickstart) directs users to obtain an API key from TypeSafe. The model page says the same weights serve every account and describes domain customization through request state and question instructions/criteria.

**Inference:** The public offering is technically hosted-only: I found no TypeSafe Jev weights, binary, container, offline-serving instructions, or local deployment entitlement in the public materials reviewed. The official [GitHub organization](https://github.com/typesafe-ai) lists SDKs, examples, an adapter, and a vLLM fork, but no Jev checkpoint or serving package. This absence does not establish that TypeSafe has no private offer. An SDK or compatible HTTP endpoint running locally would not, by itself, prove that the inference model is TypeSafe's Jev.

### Official adapter is not Jev

TypeSafe's [System One Adapter for Python](https://github.com/typesafe-ai/system-one-adapter-python)
is first-party and MIT-licensed. Its README describes a drop-in replacement
for the TypeSafe SDK evaluation API that is backed by LLM APIs *instead of
TypeSafe*. It accepts a custom OpenAI-compatible endpoint, so using it with a
local endpoint is a plausible way to reuse the typed client shape. The adapter
does not contain Jev weights or run the Jev model; any local response would be
from the configured substitute model, with that model's own quality and
calibration. This repo's current Qwen assessor remains a distinct implementation
and is not changed by this finding.

## Contract and legal boundary

TypeSafe's [Master Customer Agreement](https://typesafe.ai/legal/mca) defines the product Services as its **TypeSafe-hosted** console and API. Its license grants access to and use of those Services and permission to integrate the API into customer applications; it does not expressly grant rights to obtain, run, or redistribute Jev weights. Section 2.3(b) also prohibits using the Services or Output to perform distillation, train an imitator, or develop or facilitate development of a similar or competing product or service. The agreement separately restricts standalone-service use, reverse engineering or deriving service source/underlying data, and derivative works; it reserves TypeSafe's rights in its technology. The public clause states no non-commercial-research exception. **Inference:** The public agreement is not a local-model license. Any private deployment or weight access would need explicit written terms from TypeSafe; this note is not a legal determination about a separate agreement.

**Project constraint:** Do not use hosted Jev Services or Output to develop, tune, or train a local Jev-like assessor under the public agreement unless TypeSafe provides written terms permitting it. Keep the existing synthetic connectivity record separate from local-assessor development. This is a contract-risk gate, not a legal conclusion about independent development or a separate agreement.

## Vendor confirmation requested

The [enterprise page](https://typesafe.ai/enterprise) invites discussion of data requirements and lists “Can we run Jev in our own VPC or on-premises?”, but its public page does not provide an answer or deployment details. The official [Help Center](https://help.typesafe.ai/articles/8737694518-who-should-i-reach-out-to-with-support-requests) routes enterprise plans, procurement, and contracts to `sales@typesafe.ai`. On 2026-11-20, I sent TypeSafe Sales an inquiry asking whether an officially supported customer-VPC, on-premises, or air-gapped deployment exists; for the exact Jev version and verifiable runtime/weight artifact hashes; and for written local-inference and research-use terms. It asks TypeSafe to confirm model identity and offline/telemetry requirements. A reply is pending. No API key, market data, packet, or citations were included.

After reviewing section 2.3(b) of the public Master Customer Agreement, I sent a short clarification in the same email thread asking TypeSafe to confirm in writing that the proposed official Jev deployment and integration into this local research application are permitted under the applicable agreement, and whether a separate order or license is required. The clarification does not request or include any BTC research data.

### Follow-up availability check — 2026-11-20

The official [model catalog](https://docs.typesafe.ai/models), [System One API reference](https://docs.typesafe.ai/api/system-one), and [Quick Start](https://docs.typesafe.ai/introduction/quickstart) still describe Jev 1.14/1.13 through the authenticated `https://api.typesafe.ai/v1/systemone` endpoint. On a direct browser check, I expanded the [enterprise FAQ](https://typesafe.ai/enterprise) item asking about VPC/on-premises. TypeSafe's answer is: “No. Jev is currently available only through our hosted API.” This explicitly rules out a currently offered customer-VPC/on-prem deployment in the public product description. TypeSafe Sales was also asked whether a separately licensed or private exception exists; the email thread has no reply as of this check. I found no TypeSafe Jev weight files, authenticated local runtime manifest, or local-serving instructions in the public materials checked. This is a bounded public-source search, not proof that no private exception exists.

I also queried the public Hugging Face Hub model API under the official `typesafe-ai` author and received no public model repositories; lookup of `typesafe-ai/jev` returned not found. This checks only public Hub listings and cannot rule out private distribution or another vendor-controlled channel.

On a second Hub check, I verified the TypeSafe AI organization at [`huggingface.co/typesafeAI`](https://huggingface.co/typesafeAI); its profile links back to `typesafe.ai` and the `typesafe-ai` GitHub organization. The linked [public models page](https://huggingface.co/typesafeAI/models) reports **0 public models**. A search index surfaced a `TypeSafeAI/Qyvos` entry, but the connected Hub repository lookup returned “not found,” and the organization’s current models page lists no public repository. I do not treat that stale/inconsistent search result as a published TypeSafe Jev runtime or as evidence that Jev weights are available. The Hub check is still limited to public listings and cannot rule out a private offer.

The broader public model search surfaced [`autotrust/JEV-27B`](https://huggingface.co/autotrust/JEV-27B), an independent open-weights student model. Its own model card says it was trained using 25,376 TypeSafe Jev 1.13 output distributions and is not affiliated with TypeSafe, shares no weights or code, and is not a TypeSafe product. It can run locally, but it is **not authentic local Jev**. Because the public agreement's section 2.3(b) restricts using Jev Services or Output to develop or facilitate a similar or competing model, that model raises a contract-risk question; this project will not adopt or evaluate it as a Jev substitute without written clarification. I did not download or run its weights. This statement records the published provenance and project boundary, not a legal conclusion about the independent publisher or downstream use.

An unrelated public project, [`amithgc/local-jev`](https://github.com/amithgc/local-jev/tree/64a0b31ff343dca32142496cf9edca5a0174a18d), advertises a local server compatible with the System One wire format. Its README says it uses open models such as Qwen and DeBERTa, is a research project, and is not affiliated with or supported by TypeSafe. It is therefore a **compatible substitute, not TypeSafe Jev**. The project reports MIT code and per-model licenses; those statements do not provide a license to TypeSafe Jev weights or evidence of model identity. I did not install or run it.

A read-only check of this Windows workstation confirmed `TYPESAFE_API_KEY` is defined in the current shell; its value was not read or printed. This confirms only that the variable is set and does not establish local Jev availability. No `local-jev` executable, `jev`/`typesafe` Python module, Jev/TypeSafe-named model entry in configured or common Hugging Face cache roots, or local listener on ports 8765, 8000, or 8001 was found. A targeted Gmail search before the inquiry found no pre-existing TypeSafe/Jev messages about VPC, on-premises, or local deployment. These checks do not cover every possible custom path, process port, mailbox, or private vendor channel.

No TypeSafe API request was made for this follow-up. The 2026-11-20 inquiry remains unanswered. The existing 2026-11-19 synthetic hosted connectivity probe remains the only recorded live Jev request in this project; it established hosted connectivity only, not local availability or BTC-packet assessment. The current state is therefore: **authentic local Jev remains unverified and was not found on this workstation; only hosted access is evidenced.**

### Repository integration boundary

The current B3.1 local path in [`btc_local_assessor.py`](../../market_os/btc_local_assessor.py) consumes an OpenAI-style chat-completion runtime and reports the pinned `local_qwen_evidence_assessor` / Qwen identity. Its semantic labels are serialized as one-hot distributions and explicitly marked uncalibrated. The separate [`btc_connectivity.py`](../../market_os/btc_connectivity.py) TypeSafe adapter posts to the hosted System One endpoint; the checked request builder emits only the fixed synthetic connectivity request, not a BTC evidence packet. [`btc_local_assessor_store.py`](../../market_os/btc_local_assessor_store.py) accepts only the Qwen provider/model identity and rejects a Jev identity.

Therefore, a loopback server that accepts the System One wire format, or changing the local model label, would not make this path authentic Jev. A future authentic local integration needs a distinct typed `state`/`questions` runtime seam, verified TypeSafe model identity and artifact provenance, and a deterministic mapping into B3.1 while preserving Jev's semantic probabilities separately from Market OS return probabilities. No such runtime or attestation is currently available in the project.

## Project boundary

[ADR-0058](../decisions/ADR-0058-btc-jev-connectivity-only-local-assessor.md) keeps BTC packet content, citations, and assessment context local and prohibits sending them to hosted Jev. It also requires separate explicit approval for future Jev connectivity calls. This research does not change that boundary or authorize packet egress.
