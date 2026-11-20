# TypeSafe Jev local runtime and identity

**Checked:** 2026-11-20
**Scope:** Current public TypeSafe documentation, enterprise material, legal terms, and official GitHub repositories. No Jev API call was made.

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

TypeSafe's [Master Customer Agreement](https://typesafe.ai/legal/mca) defines the product Services as its **TypeSafe-hosted** console and API. Its license grants access to and use of those Services and permission to integrate the API into customer applications; it does not expressly grant rights to obtain, run, or redistribute Jev weights. The agreement also prohibits making the Services available as a standalone service, model distillation or training an imitator from Services/output, reverse engineering or deriving service source/underlying data, and creating derivative works; it reserves TypeSafe's rights in its technology. **Inference:** The public agreement is not a local-model license. Any private deployment, weight access, or redistribution would need explicit written terms from TypeSafe; this note is not a legal determination about a separate agreement.

**Project constraint:** Do not use hosted Jev responses as labels for distilling or training a local Jev imitator under the public agreement. A local assessor must be developed and evaluated independently unless TypeSafe provides separate written permission covering that use.

## What needs direct confirmation

The [enterprise page](https://typesafe.ai/enterprise) invites discussion of data requirements and lists “Can we run Jev in our own VPC or on-premises?”, but its public page does not provide an answer or deployment details. The official [Help Center](https://help.typesafe.ai/articles/8737694518-who-should-i-reach-out-to-with-support-requests) routes enterprise plans, procurement, and contracts to `sales@typesafe.ai`. No inquiry has been sent. Ask TypeSafe in writing whether it offers a customer-VPC, on-premises, or air-gapped Jev deployment; what exact Jev version, weights, runtime, and integrity identifiers it supplies; and what the agreement permits for local inference, copying/backups, modification, and redistribution. Confirm that the deployment is the same Jev version and retains its identity, rather than a compatible or Jev-style substitute.

## Project boundary

[ADR-0058](../decisions/ADR-0058-btc-jev-connectivity-only-local-assessor.md) keeps BTC packet content, citations, and assessment context local and prohibits sending them to hosted Jev. It also requires separate explicit approval for future Jev connectivity calls. This research does not change that boundary or authorize packet egress.
