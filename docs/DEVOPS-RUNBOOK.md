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
