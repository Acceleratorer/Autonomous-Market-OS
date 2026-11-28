# TypeSafe Jev local runtime recheck

**Checked:** 2026-11-28 Asia/Ho_Chi_Minh (UTC+07:00)

**Scope:** Public first-party TypeSafe documentation, legal terms, the public
TypeSafe GitHub organization, and the TypeSafeAI Hugging Face API/profile.
The public-source portion was read-only. A separately authorized, synthetic
hosted Jev connectivity probe was run after this source review; it did not
include a BTC packet or private project data. No installation or model download
was performed. The existing TypeSafe Sales thread was also checked read-only
in the owner's mailbox.

## Finding

Authentic local Jev remains **unverified**. The current first-party material
documents Jev as a hosted API model. It does not publish Jev weights, an offline
runtime, a local container, a signed runtime manifest, or local-use terms. The
Enterprise page still presents the VPC/on-premises question without an answer;
a private offer or account-specific agreement remains possible, but no such
offer is evidenced here.

## First-party technical evidence

- TypeSafe's [model catalog](https://docs.typesafe.ai/models) identifies Jev
  1.14 (`jev-1.14.0`) and Jev 1.13 (`jev-1.13.0`) and says models on the page
  are served through the same `POST /v1/systemone` endpoint. It states that
  “the same weights serve every account” and describes shaping behavior through
  request state, instructions, and criteria rather than customer weights.
- The [System One API reference](https://docs.typesafe.ai/api/system-one)
  documents `POST https://api.typesafe.ai/v1/systemone`, bearer authentication,
  and a request containing `model`, `state`, and `questions`. The
  [quick start](https://docs.typesafe.ai/introduction/quickstart) lists SDK, API, agent-skill,
  and browser Playground use and instructs users to obtain an API key. None of
  these first-party pages provides local inference or weight-download steps.
- The [Enterprise page](https://typesafe.ai/enterprise) says to contact Sales
  about higher limits, data requirements, or getting started. Its FAQ includes
  “Can we run Jev in our own VPC or on-premises?” but the reviewed page exposes
  no answer or deployment artifact.
- The official [TypeSafe GitHub organization](https://github.com/orgs/typesafe-ai/repositories)
  currently lists 12 public repositories: `typesafe-ai.github.io`, `vllm`,
  `LLaDA`, `daggerverse`, `pulumi-clickhouse`, `system-one-adapter-python`,
  `skills`, `typesafe-sdk-python`, `typesafe-sdk-js`,
  `n8n-nodes-typesafe-ai`, `WorkflowEvals`, and `typesafe-public-examples`.
  The public [System One adapter](https://github.com/typesafe-ai/system-one-adapter-python)
  explicitly backs its drop-in client with other LLM APIs; it is not Jev
  weights or a local Jev runtime. The organization listing and repository trees
  reviewed contain no Jev checkpoint, local runtime manifest, or offline
  container.
- A direct read-only check of the official Hugging Face endpoints
  `https://huggingface.co/api/models?author=TypeSafeAI&limit=100` and
  `https://huggingface.co/api/datasets?author=TypeSafeAI&limit=100` returned
  empty arrays on this workstation. This is a current public-listing result,
  not proof that private or gated artifacts do not exist.

## Legal and identity boundary

The [Master Customer Agreement](https://typesafe.ai/legal/mca), last updated
2026-09-23, defines ordinary Services as the TypeSafe-hosted web interface and
hosted API (§1). Section 2.3 restricts using Services or Output for model
distillation, training an imitator, or developing a similar/competing product,
and also restricts reverse engineering. The agreement recognizes separate
written agreements and says an Order controls conflicts, so only an account-
specific written offer can establish local deployment and local-use rights.
This is a contract reading for engineering risk, not legal advice.

## Similar names are not Jev

- `TypeSafeAI/Qyvos`, where visible in search or cached metadata, describes a
  separate Julia-1-based classifier trained on the independently published
  Open-Jev dataset. It does not identify its weights as TypeSafe Jev and does
  not establish local Jev rights.
- [Open-Jev](https://huggingface.co/datasets/TypeSafeAI/Open-Jev) describes an
  independently implemented dataset and explicitly says it is not official
  TypeSafe/Jev training data or model predictions.
- Community projects such as local-jev, Nimble, Kev, or other System One
  compatible servers are separate models. API compatibility, a Qwen backbone,
  a Jev-like name, or training on Open-Jev data cannot establish Jev identity.

## Decision and next gate

This recheck does not change [ADR-0058](../decisions/ADR-0058-btc-jev-connectivity-only-local-assessor.md):
hosted Jev remains connectivity-only, BTC packets remain local, and Qwen stays
separately named. The next gate is a response to the existing TypeSafe inquiry
that supplies both:

1. written local/VPC/on-premises terms permitting operation and evaluation; and
2. a vendor-authenticated manifest containing the Jev version, runtime or
   container identity, weight hashes, supported targets, and offline/egress
   behavior.

Until both are present, the project must not call a substitute Jev, send BTC
packets to hosted Jev, or use hosted Jev outputs to train or evaluate a local
substitute.

## Mailbox follow-up — 2026-11-28

The existing thread titled **“Inquiry: authentic local Jev runtime and
deployment terms”** contains three sent messages to `sales@typesafe.ai`: the
original 21 November inquiry and follow-ups on 25 and 27 November. The latest
message is still unanswered. No vendor-supplied terms, runtime manifest,
artifact hash, weight hash, or local-deployment confirmation was present in the
thread. This is mailbox evidence for the pending gate, not evidence that a
private offer is impossible.

## Fresh hosted connectivity probe — 2026-11-28

The bounded CLI ran one `jev-1.14.0` request against the documented hosted
endpoint with the committed synthetic descriptive question set, paper-only
mode, a `$0.05` estimate cap, and zero retries. The result was valid with 484
input tokens, 92 output tokens, and 402 ms observed adapter latency. The
normalized result and fingerprints are in
[`jev-hosted-synthetic-connectivity-2026-11-28.json`](../evidence/jev-hosted-synthetic-connectivity-2026-11-28.json).

The persisted run replayed with zero network and provider requests. The probe
confirms the hosted API path and the local replay contract only. It does not
change the local-runtime finding, establish Jev weights, qualify B3.1 packet
egress, or grant Jev any math, calibration, risk, or execution authority.

## Support inquiry sent — 2026-11-29

The owner-corrected follow-up inquiry was sent from `noobtan77@gmail.com` to
`support@typesafe.ai` with the subject **“Inquiry: authentic local Jev runtime
and deployment terms”**. Gmail visibly confirmed **“Đã gửi thư”**. The message
asks for an authentic local/VPC/on-premises package, written personal
non-commercial local-use terms, a vendor-authenticated Jev/runtime/container
and weight SHA-256 manifest, supported targets, and offline/telemetry/egress
behavior. It states that no BTC data, credentials, API keys, or private
artifacts are being sent.

No reply or vendor artifact is evidenced yet. This outreach does not change
the local-runtime finding: hosted Jev remains connectivity-only, BTC packets
remain local, and Qwen remains separately named until both written terms and a
vendor-authenticated manifest are received and verified.
