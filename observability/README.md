# Private observability

The opt-in `observability` Compose profile provides:

- Prometheus scraping the loopback-only Python `/metrics` endpoint;
- Loki receiving bounded JSONL service/audit logs through Promtail;
- Grafana with local Prometheus and Loki datasources.

Start it locally with a password supplied outside the repository:

```bash
GRAFANA_ADMIN_PASSWORD='change-this-locally' \
  docker compose --profile observability up --build
```

The base Compose profile does not require this variable. The observability
Grafana container fails closed at startup when it is absent; no default admin
password is stored in the repository.

The services are mapped only to host loopback: Grafana `3001`, Loki `3100`,
Prometheus `9090`, and MLflow `5000` when its profile is enabled. No
dashboard, log, or metrics endpoint is public or available through the
Tailscale operator path by default. Raw query strings,
portfolio IDs, subjects, tokens, and filesystem paths are not metric labels.

For production, replace local volumes with encrypted storage, configure alert
ownership and retention, and keep Grafana/Loki/Prometheus behind the same
private access boundary as the operator.
