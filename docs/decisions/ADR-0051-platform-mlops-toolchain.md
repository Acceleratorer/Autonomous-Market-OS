# ADR-0051: Private platform, observability, DevSecOps, and MLOps toolchain

**Date:** 2026-11-01
**Status:** Accepted for local/private scaffolding; production promotion pending
**Scope:** Infrastructure packaging around the existing single-tenant, synthetic, paper-only, read-only Market OS

## Decision

- Use Terraform for provider-neutral infrastructure contract and future cloud/VPS
  resource modules.
- Use Ansible for Linux host configuration, service account, private directories,
  systemd units, and reviewed host hardening.
- Keep the approved production access path as private Linux VM + systemd +
  Tailscale Serve. Terraform and Ansible must not create a public listener.
- Use Prometheus for bounded metrics, Grafana for private dashboards, and
  Loki/Promtail for structured JSONL service/audit logs.
- Keep observability services in an opt-in local Compose profile. Metrics labels
  contain only route families, method, status class, and bounded audit event
  names; raw IDs, query strings, subjects, tokens, and filesystem paths are not
  exported as labels.
- Use MLflow only as optional private/offline experiment tracking. Existing B1,
  B2, and B3 fingerprints, replay lineage, metrics, calibration, and
  `not-promoted` decision remain authoritative.
- Add DevSecOps gates for CodeQL, Trivy, dependency and secret checks, IaC
  validation, and source SBOM generation.

## Deferred data-plane choices

Kafka, Spark/PySpark, and Airflow/Prefect are not installed in the default
runtime. They require a new contract for streaming retention/replay, distributed
batch ownership, or scheduled DAG operations. Adding them now would increase
attack surface and recovery complexity without a measured workload requirement.

## Consequences

- Local developers can inspect metrics/logs/experiment runs without exposing
  them publicly.
- The owner must select a real infrastructure provider before Terraform can
  provision resources; no cloud account or region is invented here.
- Real Ansible inventories, vaults, SSH keys, Tailscale credentials, backup
  recipients, and MLflow production storage remain outside Git.
- MLOps evidence can describe reproducible offline experiments but cannot imply
  predictive edge, live trading authority, or production promotion.
