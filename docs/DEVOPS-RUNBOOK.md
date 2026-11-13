# DevOps runbook

## Runtime choices

The repository has three deliberately separate runtime shapes:

1. Local development: Python loopback gateway plus Next.js loopback operator.
2. Local/private containers: root `docker-compose.yml`, with only
   `127.0.0.1:3000` mapped to the host.
3. Owner-approved private promotion: Linux VM, systemd, and Tailscale Serve
   under `deploy/u5-5/`.
4. Optional local observability: Prometheus, Loki/Promtail, and Grafana under
   the Compose `observability` profile.
5. Optional local MLOps tracking: MLflow under the Compose `mlops` profile;
   experiment manifests remain offline and `not-promoted`.

The Kubernetes manifest under `deploy/k8s/` is a private single-Pod
development shape. It has an internal `ClusterIP`, no public ingress, and an
ephemeral runtime volume. It is not a production promotion or a substitute for
the approved Tailscale path.

## CI/CD

- `.github/workflows/ci.yml` runs Python tests, Next typecheck/build, evidence
  validation, static artifact checks, and container builds.
- `.github/workflows/security.yml` runs secret, dependency, evidence, compile,
  and diff checks.
- `.github/workflows/devsecops.yml` runs CodeQL, Trivy filesystem/IaC/secret
  scanning, Terraform/Ansible validation, and source SBOM generation.
- `.github/workflows/deploy-market-os.yml` builds and optionally deploys only
  the disconnected static `/market-os` artifact. It does not deploy the
  dynamic Next operator or Python gateway.

U6.4-C release hardening runs in `.github/workflows/ci.yml` as a two-runner
matrix. `windows-latest` builds `windows-x64`; `ubuntu-latest` builds
`linux-x64`. Each runner installs the pinned Next.js and Electron dependencies,
explicitly downloads the target-native Electron binary with
`pnpm exec install-electron` (without launching Chromium),
builds the renderer, and packages the Python source sidecar under `python/`
with the host-native `python` or `python3` interpreter. This is a target-native
source package; it does not embed Python or install a native service.

The matrix job creates two distinct versions, signs both with an ephemeral
external Ed25519 key, and runs `smoke-artifact.cjs --expect-signed`. The smoke
must return 200 for `/readyz`, `/healthz`, `/overview`, and `/runtime`, close
both loopback ports after shutdown, and expose release identity, append-only
event evidence, and the local paper-only/read-only boundary. The uploaded CI
artifact contains each `artifact-manifest.json`, `release-signature.json`, the
two smoke reports, `release-drill.json`, and `ci-evidence.json`.

The release drill seeds the candidate with the older signed artifact, then
verifies the following sequence:

1. a simulated failed launch restores both `current` and `known-good` metadata;
2. promotion moves `current` to the candidate and keeps the older artifact as
   `known-good`;
3. the inspection report shows `rollback_available: true` while the two
   manifest hashes differ;
4. explicit rollback re-verifies the older artifact and restores it as
   `current`.

The manifest boundary check also requires loopback-only, synthetic, paper-only,
read-only, zero provider requests, no credentials, no mutation routes, and
`live_trading: false`. The Python sidecar root remains `python/`, so release
metadata and local storage do not escape the artifact directory.

The CI job validates the evidence bundle before upload with
`pnpm run release:validate`. The validator rechecks both signed artifact
directories, manifest hashes, four-route smoke reports, and the promotion /
rollback boundary without contacting a VM or provider.
It then renders `release-evidence-report.md` and
`release-evidence-report.json` for reviewer and tooling consumption.
The same job runs `pnpm run install:preflight` against the signed candidate
artifact on each matching runner. The preflight checks the target-native
Electron binary, Python source sidecar, artifact-local storage root, slot
metadata, signature state, and the unchanged private/read-only/paper-only
boundary. It only reads the unpacked artifact and emits
`install-preflight.json` plus `install-preflight.md`; it does not install a
service, embed Python, create a destination, or modify release slots.
The same CI job creates target-native `.tar.gz` archives for the known-good and
candidate artifacts, re-extracts them, and verifies their signatures before
upload. Mutable `python/.market_os` state is excluded from each archive.
After archiving, `release:index` writes `portable-archive-index.json` and
rechecks both archive hashes against their reports, the validated manifest
hashes, signatures, target/version identity, and the read-only paper-only
boundary before the evidence is uploaded.
The dependent U7-E catalog job downloads both target evidence bundles and writes
`cross-target-release-catalog.json`. It requires both target indexes to pass,
keeps known-good/candidate versions aligned across targets, requires unique
archive hashes, and checks one consistent private/read-only/paper-only boundary.
U7-F renders that validated catalog into `cross-target-release-catalog.md` and
`cross-target-release-catalog-report.json`. The reporter rechecks the U7-E
schema, target/version identity, four signed artifacts, unique archive hashes,
mutable sidecar exclusion, and the same private/read-only/paper-only boundary
before writing reviewer evidence.

U7-G ([contract](U7-G-QUALITY-BENCHMARK-REPORT.md)) renders the synthetic
`market-os.quality-benchmark.v2` fixture through `market-os benchmark report`.
The stable projection keeps fixture and report
fingerprints, replay and gate correctness, lineage, safety, threshold metrics,
and the explicit `Not ready` promotion decision. Machine-specific latency is
excluded from the stable projection, and deterministic test-double cost stays
unavailable. CI uploads the JSON and Markdown report with the benchmark
artifact; no provider, credential, network, mutation, or live path is used.

U7-H ([contract](U7-H-SYNTHETIC-SESSION-ACCOUNTING-REPORT.md)) validates the
checked-in B3.8 synthetic session through the immutable manifest, replay, and
accounting store, then renders
`market-os.u7-h-synthetic-session-accounting-report@v1`. It preserves the four
artifact fingerprints, replay/accounting linkage, bounded counts,
turnover/cost/PnL/final-state projections, deterministic replay, and an
explicit synthetic/paper/read-only/no-provider/no-network boundary with
promotion disabled. CI uploads the JSON, Markdown, and validated session
artifacts.

U7-I ([contract](U7-I-LOCAL-EVIDENCE-PACK.md)) builds a fail-closed local
evidence index over the committed U7-F, U7-G, and U7-H evidence products. It
rechecks exact schemas/statuses, required checks, source hashes, reviewer
lineage, and the shared private/synthetic/paper-only/read-only boundary. CI
uploads the stable JSON and Markdown pack.

U7-J ([contract](U7-J-SYNTHETIC-ECONOMIC-REPORT.md)) renders a deterministic
ClawWork-shaped cost and work-income projection from the checked-in synthetic
fixture with `market-os synthetic economic-report`. It validates the fixture
fingerprint, token/API cost channels, score threshold, balance reconciliation,
and the private/synthetic/paper-only/read-only boundary. CI uploads the JSON
and Markdown report; the ClawWork runtime, providers, credentials, network,
payments, mutations, and live execution remain disabled.

U7-K ([contract](U7-K-CLI-TOOL-REGISTRY-AUDIT.md)) renders a deterministic
typed registry audit with `market-os tools report`. Enabled tools are limited
to local inspect/report/read-artifact capabilities. Tools requiring external
services, network, credentials, mutation, or live execution remain deferred
and are recorded with `execution_enabled: false`. CI uploads the JSON and
Markdown audit without invoking any generated CLI.

U7-L ([contract](U7-L-PAPER2SLIDES-RESEARCH-BRIEF.md)) exports the validated
cited-research artifact as a hash-checked Markdown brief and evidence manifest.
The output is a Paper2Slides-compatible input artifact; the model/media
pipeline is not run and no provider, credential, network, mutation, or live
execution path is enabled.

U7-M ([contract](U7-M-RELEASE-EVIDENCE-DRIFT-AUDIT.md)) runs after U7-E/F in
the existing `u7-release-catalog` job. `release:drift` consumes both target
evidence directories and `cross-target-release-catalog.json`, then traces
`ci-evidence.json` through U7-A validation, U7-B report, U7-D archive index,
and the U7-E catalog. It fails closed on missing files, schema/status drift,
raw-to-derived manifest or signature mismatch, failed `/readyz`, `/healthz`,
`/overview`, or `/runtime` smoke, inconsistent promotion/rollback metadata,
or an unsafe/private-boundary change. Windows/Linux archive and manifest hash
differences are recorded as expected target variance while each target's
provenance chain must remain internally consistent. CI uploads
`release-evidence-drift.json` and `release-evidence-drift.md` beside the
cross-target catalog.

U7-N ([contract](U7-N-UNIFIED-EVIDENCE-REGISTER.md)) runs in `offline-tests`
over the committed U7-I local evidence pack and the hosted-verified U7-M
summary. `python -m market_os.u7_evidence_register` checks exact schemas and
statuses, source hashes, zero release drift, two shared target versions, and
the normalized private/read-only/paper-only/execution-disabled boundary. CI
uploads `unified-evidence-register.json` and `unified-evidence-register.md`
without contacting a VM, provider, credential store, or live execution path.

U7-O ([contract](U7-O-EVIDENCE-CATALOG.md)) runs after the hosted U7-N, U7-J,
U7-K, and U7-L renders. `python -m market_os.u7_evidence_catalog` checks the
complete local evidence surface for exact schemas/statuses, normalized source
hashes, report fingerprints, lineage, one private/synthetic/paper-only/read-
only/no-network boundary, and disabled promotion or execution. CI uploads
`evidence-catalog.json` and `evidence-catalog.md` as
`market-os-u7-o-evidence-catalog`.

U8-A ([contract](U8-A-LIVE-READINESS-DECISION-PACK.md)) runs after U7-O in
`offline-tests`. It renders `market-os.u8-a-live-readiness-decision@v1` from
the local exit, U5.5, U6.4-C, and hosted U7-O evidence, then uploads
`market-os-u8-a-live-readiness-decision`. The pack is deliberately `gated`:
local identity, storage, session, audit, release rollback, and paper-only
checks pass, while owner VM access/health, Tailscale, connected promotion and
rollback, production observability, credentials/provider approval, and live
authorization remain blocked. No CI step changes the private, read-only,
paper-only, execution-disabled boundary.

U8-B ([contract](U8-B-LOCAL-OPERATIONAL-READINESS.md)) runs after U8-A in
`offline-tests`. It joins the U5.3 observability, B4.20 retention, platform,
U6.4-C release, and U8-A evidence into a deterministic local operational pack.
Request correlation/redaction, loopback access, bounded metrics labels,
private observability, read-only retention, backup/restore, and signed
rollback pass locally. Production retention/alerting, operator on-call,
owner-VM failure handling, connected reconciliation, and live authorization
remain blocked. CI uploads both outputs as
`market-os-u8-b-local-operational-readiness`.

U8-C ([contract](U8-C-PERMANENT-PAPER-ONLY.md)) runs after U8-A and U8-B in
`offline-tests`. It records the owner's permanent paper-only decision,
rechecks both packs' gated status and blocked external gates, and preserves
the canonical private/synthetic/paper-only/read-only boundary. It does not
enable a connected runtime, credentials, providers, mutation routes, or live
execution. CI uploads the JSON/Markdown output as
`market-os-u8-c-permanent-paper-only`.

Deployments use GitHub Secrets only. Never place DirectAdmin credentials,
Tailscale secrets, assertion secrets, or backup recipients in the repository.

## IaC and host configuration

Terraform records and validates the provider-neutral U5.5 contract under
`deploy/iac/terraform/`. Ansible configures the owner Linux host under
`deploy/iac/ansible/`. The real provider, SSH inventory, Tailscale identity,
and secret values remain owner-controlled inputs and are never committed.

Kafka, Spark/PySpark, and Airflow/Prefect are intentionally deferred. They
require a new workload contract for streaming, distributed batch, or scheduled
DAG ownership; the current bounded local B1/B2/B3 flows do not justify their
operational and security cost.

## Rollback

For the private runtime, use `deploy/u5-5/promote.sh` and
`deploy/u5-5/rollback.sh`. Promotion creates an encrypted portfolio backup,
retains one known-good release, restarts both services, and restores the
known-good release when health checks fail.

For the static preview, deploy only the generated artifact after
`python scripts/build_web_artifact.py --check` and the CI artifact checks pass.

For a local U6.4-C drill on a matching host, run:

```text
cd apps/desktop/electron
pnpm exec install-electron
pnpm run release:ci -- --target windows-x64 --output ../../../output/u6.4-ci/windows-x64
```

Use `--target linux-x64` on Linux. Keep the generated output local; CI is the
evidence store for target artifacts and public signature metadata. The Linux CI
step wraps the drill with `xvfb-run -a` because Electron's signed smoke needs a
headless display server; no public listener or execution boundary changes.

## U6.4-D installer preflight

After U6.4-C signs and validates the candidate artifact, run:

~~~text
cd apps/desktop/electron
pnpm run install:preflight -- \
  --artifact ../../../output/u6.4-ci/windows-x64/artifact-candidate \
  --target windows-x64 \
  --require-signed \
  --json ../../../output/u6.4-ci/windows-x64/install-preflight.json \
  --markdown ../../../output/u6.4-ci/windows-x64/install-preflight.md
~~~

The preflight checks the target-native binary, Python source sidecar,
artifact-local storage, slot metadata, signature state, and the unchanged
private/read-only/paper-only boundary. It only reads the unpacked artifact.
It does not install a service, embed Python, create a destination, or modify
release slots.
