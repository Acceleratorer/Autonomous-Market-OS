# Container runtime

This directory packages the existing read-only local operator into two
containers:

- `python.Dockerfile`: Python loopback gateway and local file-backed state.
- `next.Dockerfile`: production Next.js operator.

The root `docker-compose.yml` runs both processes in one network namespace.
Python remains bound to `127.0.0.1:8787`; only the Next.js port is mapped to
the host loopback address `127.0.0.1:3000`.

This is a local/private development package. It is not the U5.5 production
promotion path and does not configure Tailscale, public ingress, credentials,
providers, live data, or mutation routes.
