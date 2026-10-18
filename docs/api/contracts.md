# `market-os.v1` Contracts

The contract module is the boundary between applications, orchestration, storage, and provider adapters. It uses standard-library dataclasses so adapters do not inherit each other's dependency graphs.

## Rules

- Every contract carries `api_version: "market-os.v1"` where it crosses a durable or remote boundary.
- IDs are stable ASCII identifiers no longer than 128 characters.
- Dates are calendar dates in `YYYY-MM-DD`; timestamps are ISO-8601 strings.
- A `Task` is paper-only in v1. Any other `execution_mode` is rejected at construction.
- An idempotency key is optional for local calls and required by retrying remote clients.
- A `Run` is terminal only with `completed`, `failed`, `cancelled`, or `rejected`; failed and rejected runs include an error.
- `RunEvent` carries actor, tool/model, input/output references, cost, error, and provenance fields even when a provider does not populate all of them yet.
- `Artifact` stores immutable content metadata, SHA-256, lineage, and access policy.
- Provider-specific payloads stay behind adapters; core contracts use
  `MarketObject`, `KnowledgeDocument`, `Evidence`, and the dependency-free
  provider seam types in `market_os.providers`.

## Example task

```json
{
  "task_id": "task-example-1",
  "objective": "Compare diversified low-risk candidates",
  "symbols": ["SPY", "QQQ"],
  "start": "2026-01-02",
  "end": "2026-01-06",
  "created_at": "2026-10-13T00:00:00+00:00",
  "execution_mode": "paper",
  "idempotency_key": "research-2026-01-02-1",
  "api_version": "market-os.v1"
}
```

Adapters should call `task_from_dict` and `order_plan_from_dict` at the transport boundary. Contract failures expose a stable `code`, human-readable `message`, and optional `field` through `error_response`.

## Deferred fields

Authentication, tenant isolation, and persistent approval storage remain
deferred. Normalized provider seam types are now defined; concrete network
providers remain deferred until an adapter passes the M2 contract and
operational gates. See [ADR-0010](../decisions/ADR-0010-final-orchestration-owner.md).

## Explicit provider selection

The CLI `research` command accepts `--provider fixture|vibe-trading|lightrag`
and an optional `--backtest-provider`. The service `POST /v1/tasks` accepts
matching `provider` and `backtest_provider` fields. Omitted fields preserve the
fixture default. Optional provider failures are returned as errors; adapters do
not silently substitute another backtest engine.

For M2.2, `--provider lightrag --backtest-provider vibe-trading` selects the
document retrieval adapter and preserves the existing backtest adapter. The
result includes normalized `documents` and `retrieval` records; their artifact
lineage is rooted in the Market OS store.

`retrieval` carries `query`, document IDs, cited passage IDs/excerpts, provider
identity/version, retrieval time, query/content fingerprints, and partial/error
metadata. Root research citations include the same adapter citation references
alongside any market-evidence citations in the combined workflow.

The cited synthesis is available in the versioned `cited-research` artifact;
inspection endpoints are read-only and validate hashes and artifact lineage.

## Explicit model-gated summaries

M2.4 adds the opt-in `market-os.model-summary.v1` contract. The deterministic
M2.3 synthesis remains the default and trusted result. A caller may select the
local deterministic test double with `summary_provider: "deterministic-test"`,
the synthetic recorded-response adapter with `summary_provider:
"openai-recorded"`, or the approval-gated OpenAI adapter with
`summary_provider: "openai"` (and the matching CLI flag). All selections must
use the explicit `lightrag` cited-retrieval provider. Unknown providers or
summary selection without cited retrieval are rejected. The live OpenAI path
fails closed before network access when its approval configuration is absent.

The persisted `model-summary` artifact records provider/model identity, prompt
and input fingerprints, classified statements, validation errors, gate status,
usage metadata, explicit provider failure metadata when fallback is used,
output/summary fingerprints, and lineage to `cited-research`.
Supported statement text must equal a persisted exact support quote, and all
citation, passage, document, content-hash, and run lineage references are
resolved before approval. Inferences and unsupported statements are explicit
and separately counted. Rejected output is not published as summary text; a
provider failure preserves the deterministic synthesis as a `fallback` gate.

The read-only inspection resources are `model-summary` and `inferences`:

```text
GET /v1/runs/<run-id>/research/model-summary
GET /v1/runs/<run-id>/research/inferences
```

They invoke no provider and write no trading state. Inspection rejects missing
or corrupt artifact content, mismatched fingerprints, missing cited-research
lineage, and cross-artifact synthesis mismatches. Model summaries cannot alter
the paper-only order plan or risk decision.

## Research-quality benchmark

M2.6 refines the dependency-free `market-os.quality-benchmark.v2` report. It is
explicitly offline and read-only with respect to trading state. `POST
/v1/benchmarks` accepts a local synthetic fixture path and returns independent
case metrics, thresholds, replay status, lineage, separate benchmark/gate/
candidate-quality outcomes, and a model-adapter promotion decision. The
read-only resources are:

```text
GET /v1/benchmarks/<benchmark-id>/cases
GET /v1/benchmarks/<benchmark-id>/metrics
GET /v1/benchmarks/<benchmark-id>/failed-cases
GET /v1/benchmarks/<benchmark-id>/benchmark-failures
GET /v1/benchmarks/<benchmark-id>/candidate-quality-failures
GET /v1/benchmarks/<benchmark-id>/evaluation
GET /v1/benchmarks/<benchmark-id>/thresholds
GET /v1/benchmarks/<benchmark-id>/fingerprint
```

In v2, `failed-cases` means candidate-quality failures and
`benchmark-failures` means failures of the benchmark procedure or integrity
checks. Empty metric denominators and unavailable usage/cost/latency are
reported as not applicable or unknown rather than zero or perfect. Existing v1
artifacts remain readable through the versioned legacy fingerprint path.

The benchmark compares M2.3 deterministic exact-quote synthesis with the M2.4
deterministic test double. It does not claim real-model quality, does not add a
provider, and cannot approve a real adapter without the documented thresholds,
security checks, measured cost/usage/latency, and human approval. See the
[M2.6 quality review](../M2.6-QUALITY-REVIEW.md) and
[bounded model-adapter plan](../M2.6-MODEL-ADAPTER-PLAN.md).

## B1 BTC historical dataset inspection

B1 adds offline fixture ingestion and read-only dataset inspection. Public
Binance transport is disabled pending ADR-0016 source/legal review and explicit
approval. The CLI surfaces are:

```text
market-os btc-paper ingest --fixture <path> --store-root <path>
market-os btc-paper acquire --start-ms <ms> --end-ms <ms> --store-root <path>
market-os btc-paper inspect <dataset-revision> --resource manifest|candles|outcomes|provenance|gaps|replay --store-root <path>
```

The existing HTTP adapter accepts `POST /v1/btc/history/ingest` with a local
`store_root` and fixture object. Read-only resources are:

```text
GET /v1/btc/history/<dataset-revision>/manifest
GET /v1/btc/history/<dataset-revision>/candles
GET /v1/btc/history/<dataset-revision>/outcomes
GET /v1/btc/history/<dataset-revision>/provenance
GET /v1/btc/history/<dataset-revision>/gaps
GET /v1/btc/history/<dataset-revision>/replay
```

These paths invoke no model, broker, or network transport. Canonical Parquet
content is hash-checked before inspection; DuckDB stores raw-page, manifest,
outcome, and provenance lineage.

## U3/B2 BTC feature and baseline evaluation

B2 consumes an existing B1 `dataset_revision` only. It never acquires market
data and never calls Jev, OpenAI, a hosted model, a broker, or an exchange.
The read/write boundary is a local research artifact store; inspection is
read-only after the run is materialized.

The CLI surfaces are:

```text
market-os btc-paper b2 run --dataset-revision <revision> --history-store-root <b1-root> --store-root <b2-root>
market-os btc-paper b2 inspect <run-id> --resource manifest|config|features|labels|splits|predictions|metrics|calibration|lineage|artifacts --store-root <b2-root>
```

The API surfaces are:

```text
POST /v1/btc/b2/runs
GET /v1/btc/b2/<run-id>/<resource>?store_root=<b2-root>
```

The POST body names the local `history_store_root`, B1 `dataset_revision`,
optional `experiment_id`, optional UTC `as_of`, and optional B2 `store_root`.
The GET resource is one of `config`, `features`, `labels`, `splits`,
`predictions`, `metrics`, `calibration`, `lineage`, or `manifest`.

B2 feature version `btc.b2.features.v1` materializes only these deterministic
values from closed candles: `close`, `ln(C_t/C_{t-1})`,
`ln(C_t/C_{t-5})`, `(H_t-L_t)/C_t`, and `ln(1+V_t)`. Inputs are the current
candle plus the exact five prior contiguous candles, and each input reference
must be closed and available by `decision_eligible_at`.

Target version `btc.b2.close-return-5m.v1` stores the separate label
`ln(C_{t+5}/C_t)`, direction, target fingerprint, and future target reference.
The target is withheld for missing continuity or unavailable future data; no
target reference is included in feature inputs.

Feature statuses are `eligible`, `warm_up`, `gap`, `stale`, `unavailable`, and
`invalid`. B2 baselines are fixed to `naive_0_5`, `empirical_rate`, and
`conditional_rate`. Split metadata is chronological; rows with
`target_end_ms >= boundary` are purged and the next five minutes are
embargoed. Configuration, fingerprints, predictions, metrics, calibration,
split metadata, artifact hashes, and lineage are persisted and replay-checked.
LightGBM is deliberately deferred until a larger, leakage-safe offline
evaluation justifies the dependency.
