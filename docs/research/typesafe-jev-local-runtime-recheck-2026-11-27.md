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

The TypeSafe Sales inquiry thread was rechecked on 2026-11-27. It contains three sent messages (the original inquiry and two follow-ups) and no vendor reply or deployment manifest. The latest follow-up contained no BTC data or API key.

## Local workstation artifact check — 2026-11-27

A bounded, read-only inventory covered the repository's `.market_os` data, common Hugging Face and ModelScope caches, the Codex model directory, and `Documents/Codex` to depth five. The only Jev-named directories were the three `jev-connectivity-live*` stores; each contained a reservation, manifest, and result JSON. The recognized model-weight extensions in those search roots found one model file, the pinned Qwen3-4B GGUF, and no weight file under a Jev/TypeSafe-named directory. No vendor-authenticated Jev runtime or deployment manifest was found. The environment contains a `TYPESAFE_API_KEY` variable name; its value was not read, and its presence is not evidence of a local runtime. `wsl.exe --list --quiet` exited 1 and returned zero distributions, so this workstation has no WSL target for a live Linux isolation check. This bounded local search does not rule out artifacts in unscanned locations or a private TypeSafe delivery channel.

## Independent local-compatible projects are not Jev

- [local-jev](https://github.com/amithgc/local-jev) describes itself as an offline System One-compatible server that uses open models, including Qwen and an entailment model. Its README says it is offline after the first model download and labels the project a research project, not a finished product. Its reported benchmark figures are author-published and have not been reproduced in this project. This is a third-party model and server, not TypeSafe Jev or a vendor-authenticated Jev runtime.
- [Bespoke Nimble](https://github.com/bespokelabsai/nimble) describes a locally runnable, open-weight typed-decision model inspired by Jev's System One approach. Its README explicitly says Nimble was not distilled from Jev. It is a separate model, not Jev weights or an official Jev-compatible endpoint.
- [Kev](https://github.com/jaredpalmer/kev) calls itself a Jev-like decision-model family built on Qwen and implements TypeSafe's public `/v1/systemone` request shape. Its author-owned [Kev-0.8B card](https://huggingface.co/jaredpalmer/kev-0.8b) says it can run on a 4 GB GPU and reports owner-published transfer-v4 locked-test accuracy/Brier of `0.697/0.397`; no BTC-specific evidence-support, contradiction, or abstention evaluation is reported there. The [Kev-4B card](https://huggingface.co/jaredpalmer/kev-4b) calls for about 16 GB free CUDA memory, exceeding this host's 8,151 MiB total GPU memory.
- Kev's [`pyproject.toml`](https://github.com/jaredpalmer/kev/blob/main/pyproject.toml) requires Python `>=3.12,<3.14` and a PyTorch/Transformers/PEFT stack, while the current assessor runtime is pinned to CPython 3.11.18. Kev-0.8B is only a hardware candidate, not a proven fit: no Windows run, CUDA/host memory measurement, or fit under Market OS's 6 GiB Job Object cap was performed. The [Kev 1.0 asset manifest](https://github.com/jaredpalmer/kev/blob/main/docs/releases/kev-1.0-assets.json) publishes pinned artifact revisions and hashes, but none was downloaded or locally verified.
- Kev therefore remains a separate research candidate that would need an owner-approved runtime and BTC-specific calibration/evaluation. Its Qwen backbone and public API compatibility do not make it Jev; this check makes no model-selection change.

These projects show that local typed-decision or wire-compatible alternatives exist; they do not change the finding about authentic Jev. No alternative was installed, run, or evaluated here. Do not send BTC packets to hosted Jev or use hosted Jev outputs to train or tune a local substitute under the posted agreement; see the dated contract review in [the earlier Jev research note](typesafe-jev-local-runtime-2026-11-20.md). If actual Jev remains a hard requirement, keep the local assessor identified as Qwen and await written TypeSafe terms and a verifiable runtime/weight manifest.

## Inference and project consistency

The public technical materials support hosted integration, but do not establish whether TypeSafe privately offers local deployment. The legal materials likewise do not settle entitlement to a private runtime without the applicable product-specific agreement. Do not infer Jev identity from an API-compatible local server, an SDK endpoint override, or generic serving infrastructure.

This finding is consistent with [ADR-0058](../decisions/ADR-0058-btc-jev-connectivity-only-local-assessor.md): the ADR keeps BTC packets local and hosted Jev connectivity-only. This recheck does not change that project boundary.

## Evidence gaps

- The Enterprise FAQ answer is not exposed in current public page content.
- No private deployment offer, product-specific agreement, or vendor-authenticated artifact manifest was reviewed.
- Without a runtime/weight manifest and downloadable artifacts, Jev version, local execution method, network requirements, and hashes cannot be verified.

## Follow-up official integration check — 2026-11-27

The TypeSafe-owned [`n8n-nodes-typesafe-ai`](https://github.com/typesafe-ai/n8n-nodes-typesafe-ai) repository's latest public commit (`f0ee24d`, 2026-11-26 UTC) was rechecked on 2026-11-27. Its README says operators create an API key in the TypeSafe console and that each input item sends one request containing its state, selected model, and questions. This node can orchestrate hosted Jev workflows, but it does not provide local Jev weights or a local runtime and does not satisfy the zero-provider/network runtime requirement. The current [model catalog](https://docs.typesafe.ai/models) still routes Jev 1.14 through `POST /v1/systemone`; the [API reference](https://docs.typesafe.ai/api/system-one) documents bearer authentication. This confirms the public hosted path only; it does not rule out a private TypeSafe offer or separate written agreement ([commit](https://github.com/typesafe-ai/n8n-nodes-typesafe-ai/commit/f0ee24d22de335b99a3127d1d15463e92d84e2f8)).

## Separate synthetic hosted connectivity probe — 2026-11-27

After the read-only local-availability checks above, one user-authorized
synthetic request was sent to TypeSafe's hosted
[`POST /v1/systemone`](https://docs.typesafe.ai/api/system-one) endpoint using
the generic statement “A triangle has three sides.” The response identified
the resolved model as `jev-1.14.0`, returned a Noul value of `0.99`, and
reported 283 input and 21 output tokens. The sanitized request/response record
is [here](../evidence/jev-hosted-synthetic-connectivity-2026-11-27.json).

This proves the configured credential can reach hosted Jev for one synthetic
request. It does not prove local weights, a local runtime, or local-use terms;
it is not BTC evidence and does not establish calibration or trading quality.
No API key, BTC packet, or project content was sent, and the response was not
used to train, tune, or evaluate the separate local Qwen model.
