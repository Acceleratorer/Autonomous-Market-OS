# TypeSafe Jev local runtime and terms recheck

**Checked:** 2026-11-25
**Scope:** First-party TypeSafe documentation, posted contract, official public code/model listings, and a bounded local artifact check. No Jev API request, email, BTC data, or credential value was transmitted.

## Finding

The public TypeSafe sources reviewed describe Jev through the hosted System One API. They do not publish an authentic Jev checkpoint, local inference package, or manifest that would establish a local Jev deployment. The Enterprise page currently lists its VPC/on-premises FAQ question, but this page fetch did not expose the answer. A direct browser check recorded in the [2026-11-23 recheck](typesafe-jev-local-runtime-recheck-2026-11-23.md) had expanded it and reported hosted API only; this recheck could not replay that answer from the text fetch. Therefore, local Jev remains **unverified**; the public evidence does not prove that a private vendor offer is impossible.

## First-party technical evidence

- The [model catalog](https://docs.typesafe.ai/models) lists Jev 1.14 (`jev-1.14.0`) and 1.13 (`jev-1.13.0`) and says models on the page use `POST /v1/systemone`. It identifies 1.14 as the newest version, available from 2026-10-14.
- The [System One API reference](https://docs.typesafe.ai/api/system-one) specifies `https://api.typesafe.ai`, bearer authentication, and the request's `state` and typed `questions` fields. The [Quick Start](https://docs.typesafe.ai/introduction/quickstart) describes SDK, API, agent-skill, and browser-Playground use and directs the user to obtain an API key from the TypeSafe console. These are hosted integration instructions, not local inference instructions.
- The [Enterprise page](https://typesafe.ai/enterprise) contains the question “Can we run Jev in our own VPC or on-premises?”; the answer was not exposed in the page content fetched on this date. The earlier direct browser observation remains separately attributed to its date above.
- The official [TypeSafe GitHub organization](https://github.com/orgs/typesafe-ai/repositories) showed 12 public repositories in this check, including SDKs, examples, an n8n integration, a `vllm` fork, and a System One adapter. The listing showed no Jev checkpoint or local-serving manifest. The [official TypeSafe Hugging Face models page](https://huggingface.co/typesafeAI/models) says that no models are public yet.
- TypeSafe's [System One Adapter for Python](https://github.com/typesafe-ai/system-one-adapter-python) describes itself as a drop-in client replacement backed by LLM APIs instead of TypeSafe. It can reuse a typed client shape, but its README does not claim to ship Jev or run Jev weights. A local endpoint behind this adapter would retain the identity and behavior of the configured local model, not Jev.

This is a bounded review of the currently visible public listings. It cannot rule out private repositories, a separate distribution channel, or a private enterprise agreement.

## Public contract evidence

The [Master Customer Agreement](https://typesafe.ai/legal/mca), last updated 2026-09-23, defines the Services in §1 as TypeSafe-hosted web and API services. Sections 2.1–2.2 license use of those Services and API integration. The posted text does not expressly grant access to or a right to run Jev weights locally. Section 2.3(b) restricts using the Services or their Output to distill the model, train an imitator, or develop or facilitate a similar or competing product or service. The agreement also says a separate written agreement may govern where one is in effect.

This is an interpretation of the posted text, not legal advice and not a conclusion about a separate agreement. The public agreement does not supply a local-use license or local artifact manifest. In particular, hosted Jev outputs should not be used to train or tune a local Jev-like substitute under the public terms without written terms that expressly allow it.

## Third-party compatibility lead

The search also surfaced [amithgc/local-jev](https://github.com/amithgc/local-jev), an independent project whose README claims local/offline serving with the same `/v1/systemone` wire format. Its README identifies locally run open models, including a Qwen instruction model and an entailment model, and describes the project as research software rather than a finished product. The repository's software license is MIT; that does not establish the licenses or terms for each model-weight artifact. It is not TypeSafe Jev, does not provide TypeSafe weights, and has no stated TypeSafe affiliation or endorsement. No code or model was installed or run in this check. This is a possible Jev-compatible protocol implementation only; it does not satisfy the authentic Jev runtime requirement and must not be labeled Jev.

## Bounded local artifact check

The bounded local check found no Jev/TypeSafe model directory in the targeted Hugging Face, LM Studio, and project local-evidence runtime directories. The pinned Python runtime contained no Jev, TypeSafe, or System One package, and no Jev/TypeSafe process was running. These checks cover only the named locations and processes; they do not search every custom path or vendor channel.

## Project consequence

Keep [ADR-0058](../decisions/ADR-0058-btc-jev-connectivity-only-local-assessor.md): BTC packets remain local and hosted Jev remains connectivity-only. Keep the local Qwen assessor labeled as Qwen; neither a compatible API shape nor a TypeSafe key makes it Jev.

Reconsider an authentic local Jev integration only after obtaining both (1) written TypeSafe confirmation and local/VPC/on-premises use terms and (2) a verifiable artifact manifest identifying the Jev version, runtime, model/weight hashes, and supported local execution method. Until then, the requested 100% local Jev runtime is not evidenced or legally cleared by the sources reviewed.
