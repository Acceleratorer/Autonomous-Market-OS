# Security policy

## Supported versions

Security fixes target the default branch. The project is currently a
synthetic, paper-only research and inspection system; it is not a live trading
service.

## Reporting a vulnerability

Please do not disclose credentials, private keys, portfolio data, or a working
exploit in a public issue. Use GitHub's private vulnerability reporting or a
private maintainer channel for this repository. Include:

- affected commit or version;
- affected file, route, or container;
- reproduction steps that use synthetic data only;
- impact and any proposed mitigation.

If the report includes secrets, redact them and rotate them immediately.

## Security boundaries

- Python owns accounting, risk, persistence, recovery, replay, audit, backup,
  and portfolio inspection.
- Next.js is a server-side, GET/HEAD-only read-only adapter.
- The public `/market-os` preview contains no portfolio data, credentials,
  scripts, provider calls, or mutation controls.
- U5.5 connected access is owner-only, portfolio-allowlisted, loopback-bound,
  and intended to run behind private Tailscale Serve.
- Containers and Kubernetes manifests in this repository are local/private
  packaging examples. They do not enable public ingress or live execution.

Never add secrets to source, HTML, browser bundles, logs, evidence artifacts,
Docker images, or Kubernetes manifests. Use host-injected secret stores for
the owner-controlled private runtime.

## Automated security controls

CI runs high-confidence secret scanning, dependency audits, CodeQL, Trivy
filesystem/IaC/secret scanning, Terraform/Ansible syntax checks, and source
SBOM generation. These checks reduce risk but do not replace review of the
owner VM, Tailscale policy, image provenance, or secret-manager configuration.
