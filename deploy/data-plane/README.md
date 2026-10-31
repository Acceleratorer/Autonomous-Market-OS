# Optional data-plane extensions

Kafka, Spark/PySpark, and Airflow/Prefect are intentionally not part of the
default runtime. The current product is single-tenant, synthetic, paper-only,
read-only, and file-backed; adding a broker, distributed compute engine, or
workflow scheduler now would add operational and security surface without a
measured requirement.

Use these extension points only when a new contract defines the workload:

- Kafka: durable multi-consumer event streaming with explicit retention,
  replay, schema, and ownership semantics.
- Spark/PySpark: batch feature computation that no longer fits the bounded
  local B1/B2 jobs.
- Airflow or Prefect: multi-step scheduled DAGs with retries, ownership,
  backfills, and secret/credential policy.

Any future data-plane deployment must preserve Python accounting authority,
dataset fingerprints, offline/paper defaults, no live provider access, and
private ingress. Do not add these components merely to call the system
“production-grade.”
