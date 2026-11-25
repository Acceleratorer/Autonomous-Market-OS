# TypeSafe Jev Local Deployment: Primary-Source Check

**Checked:** 2026-11-26

**Scope:** Current TypeSafe documentation, official public repositories, and posted public agreement. Read-only; no authenticated Jev request, installation, or BTC packet was made.

## Finding

Authentic local Jev remains **unverified**. The current public documentation describes Jev through TypeSafe's hosted System One API. The published agreement grants access to TypeSafe-hosted web/API Services but does not document a Jev checkpoint, local runtime, offline-use grant, or artifact distribution channel. The Enterprise page asks whether Jev can run in a customer's VPC or on-premises, but the accessible page content contains no answer. A private offer or separate agreement remains possible; the reviewed public sources cannot resolve that.

## Technical evidence

- The [documentation index](https://docs.typesafe.ai/llms.txt) describes the product as use of the System One API and points users to the [Quick Start](https://docs.typesafe.ai/introduction/quickstart), which offers SDK, API, agent-skill, or browser Playground paths and directs users to obtain an API key from the TypeSafe console.
- The [model catalog](https://docs.typesafe.ai/models) lists Jev 1.14 (`jev-1.14.0`) and 1.13 (`jev-1.13.0`) and states that models on the page are served through `POST /v1/systemone`. The [System One API reference](https://docs.typesafe.ai/api/system-one) gives `https://api.typesafe.ai/v1/systemone` and requires bearer authentication. Neither page documents downloadable Jev weights or local inference.
- The [Enterprise FAQ](https://typesafe.ai/enterprise) includes “Can we run Jev in our own VPC or on-premises?” but no answer is exposed in the page content reviewed.
- The official [TypeSafe GitHub organization](https://github.com/orgs/typesafe-ai/repositories) lists 12 public repositories in this check. Its [System One Adapter for Python](https://github.com/typesafe-ai/system-one-adapter-python) describes itself as a TypeSafe client replacement backed by other LLM APIs. The organization's [vLLM fork](https://github.com/typesafe-ai/vllm) is identified as a generic inference/serving engine, and its [LLaDA repository](https://github.com/typesafe-ai/LLaDA) is an implementation of a separately named diffusion-language-model paper. These public code artifacts do not identify Jev weights or a Jev serving manifest. This bounded public-listing review does not rule out private repositories or vendor-only distribution.
- The Hugging Face profile labeled [TypeSafe AI](https://huggingface.co/typesafeAI) links to `typesafe.ai` and the official GitHub organization and currently shows zero public models. This is supporting profile evidence, not a complete or vendor-authenticated inventory of private artifact channels.

## Public terms

The [Master Customer Agreement](https://typesafe.ai/legal/mca), last updated 2026-09-23, defines the Services in §1 as TypeSafe-hosted web and API services. Section 2.1 licenses access to those Services and API integration; §2.3(b) restricts using the Services or Output to distill the model, train an imitator, or develop a similar or competing product; §11 says no rights are granted unless expressly set out. The posted agreement therefore does not itself supply a local Jev artifact license or offline-use permission. This is an interpretation of the posted text, not legal advice; a separate written agreement may govern.

## Host and vendor-response check

On 2026-11-26, read-only Gmail searches for messages from `sales@typesafe.ai`
and `typesafe.ai` after 2026-11-25 returned no incoming reply. The matching
thread contains the already-sent inquiry and follow-up only.

A bounded Windows-host inventory found no Jev, TypeSafe, System One, or
`local-jev` directory in the default Hugging Face/LM Studio caches, configured
model-cache paths, or this checkout's `.market_os` tree. Command lookup found
no matching executable, the active system Python had no matching installed
package, and process-name lookup found no matching runtime. The `wsl.exe`
command reports that WSL is not installed; no Docker CLI was found. The
environment variable name `TYPESAFE_API_KEY` is present, but its value was not
read. It is not a local model artifact or license. No API request or package
installation was performed.

This host check is bounded to the named paths, active Python, commands, and
process names. It does not cover every custom directory, private registry, or
vendor delivery channel.

## Project consequence

Keep hosted Jev at the already-approved connectivity boundary and keep BTC packets local. The current local Qwen assessor remains **Qwen, not Jev**. Reconsider authentic local Jev only after TypeSafe provides written local/VPC/on-premises terms and a verifiable vendor-authenticated manifest identifying the Jev version, runtime, weight hashes, local execution method, and required network behavior. Do not infer Jev identity from a System One-compatible API, generic serving infrastructure, a TypeSafe API key, or a third-party model card.
