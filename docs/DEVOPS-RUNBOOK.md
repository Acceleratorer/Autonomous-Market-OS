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
