# TypeSafe Jev local runtime recheck

**Checked:** 2026-11-23
**Scope:** Current public TypeSafe documentation, legal terms, and the official GitHub organization. This was a read-only public-source check. No Jev API request, email to TypeSafe, BTC data, or local model artifact was used.

## Finding

Public evidence still supports **hosted-only Jev**. The current [Enterprise FAQ](https://typesafe.ai/enterprise) explicitly answers that Jev is currently available only through TypeSafe's hosted API for the VPC/on-premises question. A direct browser check expanded that FAQ item and confirmed the answer.

The [model catalog](https://docs.typesafe.ai/models) lists `jev-1.14.0` and `jev-1.13.0`, and says both are served through `POST /v1/systemone`; it identifies 1.14 as the newest release. The [System One API reference](https://docs.typesafe.ai/api/system-one) documents `https://api.typesafe.ai/v1/systemone` with required bearer authentication. The [Quick Start](https://docs.typesafe.ai/introduction/quickstart) instructs users to obtain an API key from TypeSafe. These materials document hosted API use, not local or offline inference.

The official [TypeSafe GitHub organization](https://github.com/orgs/typesafe-ai/repositories) exposes public SDK, integration, example, and adapter repositories. The public repository listing reviewed contained no verifiable Jev checkpoint, runtime manifest, or local-serving package. This is a bounded public search; it cannot rule out a private vendor offer or an artifact distributed through another channel.

## Similar-name public project

The public search also surfaced [`jev-ai/jev-model`](https://github.com/jev-ai/jev-model) and its linked [`thejevai.com`](https://thejevai.com) site. The site says the product is independently operated and is not affiliated with, operated by, or endorsed by TypeSafe; the repository README likewise says it is not the official product site for the underlying Jev model. The repository has one commit and contains generated static-site files (HTML, README, and Next.js assets); the inspected tree contains no model checkpoint, inference runtime, or license. It is not evidence of authentic local TypeSafe Jev. This does not rule out a separate private vendor deployment.

## Licensing evidence

The [Master Customer Agreement](https://typesafe.ai/legal/mca) defines the Services as TypeSafe-hosted web and API services (§1) and grants access to those Services plus permission to integrate the API (§2.1). It does not expressly grant a right to obtain, run, or redistribute Jev weights. Section 2.3(b) restricts using the Services or their Output to distill or imitate the service, or to develop or facilitate a similar or competing product or service.

**Interpretation limit:** This describes the public agreement reviewed, not legal advice and not any separate written agreement. A private deployment and local-use license remain unverified until TypeSafe supplies written terms and verifiable runtime/model artifacts.

## Project consequence

Do not describe a compatible local model or endpoint as Jev. Keep the existing BTC packet boundary in [ADR-0058](../decisions/ADR-0058-btc-jev-connectivity-only-local-assessor.md): BTC evidence remains local, and this check does not authorize packet egress or any new Jev request. The current conclusion is unchanged: **authentic local Jev is not evidenced by the public materials reviewed; only hosted access is documented.**

For the earlier, broader discovery record and implementation boundary, see [the 2026-11-20 local-runtime note](typesafe-jev-local-runtime-2026-11-20.md).
