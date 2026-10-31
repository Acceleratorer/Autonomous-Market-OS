# Gateway

Run `python -m apps.gateway --host 127.0.0.1 --port 8787`. This starts the
existing loopback service; it does not enable public access or new routes.
The local service also exposes a loopback-only Prometheus-compatible `/metrics`
endpoint for the opt-in observability profile. U5.5 connected mode denies that
endpoint and keeps it outside the Tailscale operator route allowlist.
