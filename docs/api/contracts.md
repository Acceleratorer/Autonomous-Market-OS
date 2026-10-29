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

B1 adds offline fixture ingestion and read-only dataset inspection. The reviewed
Binance transport is disabled by default and can only be selected by the exact
policy, runtime flag, and separate execution approval. The CLI surfaces are:

```text
market-os btc-paper ingest --fixture <path> --store-root <path>
market-os btc-paper historical-readiness --cutoff-ms <UTC-minute-ms>
market-os btc-paper acquire --start-ms <ms> --end-ms <exclusive-ms> \
  --page-size 1000 --max-pages 44 --max-requests 44 --max-rows 43200 \
  --max-runtime-seconds 900 --max-attempts 1 \
  --allow-historical-ingest --authorization-file <approved-policy.json> \
  --execution-approval "<exact B1 approval phrase>" \
  --store-root <path>
market-os btc-paper inspect <dataset-revision> --resource manifest|candles|outcomes|provenance|gaps|replay --store-root <path>
```

`historical-readiness` is offline and returns the versioned
`market-os.btc-history-readiness.v1` proposal. It defaults to a blocked
30-UTC-day BTCUSDT/1m range ending at the explicit cutoff, with 43,200 rows,
44 pages/requests, one attempt per page, a 900-second runtime cap, and a
256 KiB page bound. The candle opening at the cutoff is excluded.

`acquire` remains refused unless the explicit runtime flag, the exact
repository-root `approved-policy.json`, and a matching
`market-os.btc-history-authorization.v1` policy file are supplied. The policy
must verify source terms, regional eligibility, retention rights, a future
`expires_at`, and the requested range and caps. The default Binance transport
remains disabled; the reviewed opt-in path additionally requires a separate
exact execution approval phrase. The phrase is recorded in
`docs/U3-B1-HISTORICAL-READINESS-REPORT.md`.

The existing HTTP adapter accepts `POST /v1/btc/history/ingest` with a local
`store_root` and fixture object. Read-only resources are:

```text
GET /v1/btc/history/readiness?cutoff-ms=<UTC-minute-ms>
GET /v1/btc/history/datasets?limit=<1..100>&after_dataset_revision=<revision>
GET /v1/btc/history/datasets/<revision>/candles?limit=<1..100>&after_open_time_ms=<UTC-ms>
GET /v1/btc/history/datasets/<revision>/manifests?limit=<1..100>&after_manifest_id=<manifest-id>
GET /v1/btc/history/datasets/<revision>/manifests/<manifest-id>
```

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

The dataset catalog is bounded, revision-ordered, and uses the gateway's
configured local HistoryStore. It rejects `store_root`, opens an existing
catalog read-only, and returns an empty page without creating files when the
store is absent. An existing non-directory store path is an integrity error.
Catalog rows expose metadata only, and timestamps must fit the JavaScript UTC
date range used by the local renderer. Replay remains necessary to validate
stored Parquet content.

The local Next.js detail surface uses the bounded candle-page route. It is
bound to the configured HistoryStore, rejects caller-selected roots, returns at
most 100 rows in ascending `open_time_ms` order, and uses an exclusive cursor
that must identify a stored candle. Each page verifies the canonical Parquet
path and file hash before selecting rows; the hash is streamed so memory use
does not grow with file size. The response contains UTC timestamps and bounded
decimal strings, without filesystem paths or provenance payloads. Replay is
still required to verify canonical-content equivalence.

The local Next.js ingestion-manifest surface is bound to the same configured
HistoryStore. Manifest catalog pages return at most 100 validated catalog
summaries in manifest-ID order; the exclusive cursor must identify a manifest
for the requested dataset. Detail requests derive the manifest file path from
the validated ID, check that it remains inside local manifest storage, read no
more than 8 MiB, and verify its SHA-256 against the catalog before parsing.
Responses contain fixed scalar metadata, outcome counts, and counts of raw-page,
gap, and parent-revision collections. They do not return filesystem paths,
payload arrays, or provenance. Oversized, malformed, or mismatched manifests
fail closed. This display check does not replace canonical dataset replay.

The local Next.js ingestion-record pages use these manifest-scoped GET routes:

```text
GET /v1/btc/history/datasets/<revision>/manifests/<manifest-id>/outcomes?limit=<1..100>&after_outcome_index=<index>
GET /v1/btc/history/datasets/<revision>/manifests/<manifest-id>/gaps?limit=<1..100>&after_start_time_ms=<UTC-ms>
GET /v1/btc/history/datasets/<revision>/manifests/<manifest-id>/provenance?limit=<1..100>&after_raw_page_sha256=<sha256>&after_row_index=<index>
```

These routes use the configured read-only HistoryStore and require the
manifest to belong to the requested dataset. They accept only unique query
fields and reject caller-selected roots. Outcomes validate manifest status
counts and join rows to raw provenance fingerprints. Gaps are read from the
single 8 MiB-capped, hash-verified manifest and validate entry shape and order.
Provenance pages use the existing `(manifest, raw-page SHA-256, row index)`
catalog key, verify the full source-row fingerprint, and return at most 512
preview characters for payloads up to 256 KiB. The API returns no filesystem
paths or complete raw payloads. Canonical replay remains the dataset integrity
check.

## Local B2/B3 research inspection

The local Next.js operator uses these bounded read-only routes:

```text
GET /v1/btc/research/b2/runs?limit=<1..100>&after_run_id=<run-id>
GET /v1/btc/research/b2/runs/<run-id>
GET /v1/btc/research/b3/runs?limit=<1..100>&after_run_id=<run-id>
GET /v1/btc/research/b3/runs/<run-id>
```

The default page size is 25. Catalogs return at most 100 summaries in ascending
run-ID order; the exclusive cursor must identify a run for the selected
engine. Unknown or duplicate query parameters and caller-supplied roots are
rejected.

The gateway reads from `MARKET_OS_BTC_B2_STORE_ROOT` and
`MARKET_OS_BTC_B3_STORE_ROOT`, or from the corresponding `btc-b2` / `btc-b3`
directory under the workflow root. A missing store returns an empty catalog and
is not initialized by GET. Run manifests are capped at 256 KiB and the selected
metrics/report artifact is capped at 256 KiB. The artifact's exact size and
SHA-256 must match its run manifest before parsing.

Responses include fixed run metadata and normalized B2 metrics or a normalized
B3 report. They omit artifact paths, full feature/label/prediction arrays,
fixture cases, and provider responses. B2 score sample counts must match the
run. B3 validates dataset, feature, fixture, and experiment lineage, requires
matched inputs and zero network/provider requests, and preserves
`not-promoted`. These checks cover the displayed artifact; full run replay
remains the integrity check for the complete artifact set.

The Next.js API port is configurable through the server-only
`MARKET_OS_API_PORT` setting, defaulting to 8787. The target host remains
`127.0.0.1`.

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

## U3/B3 controlled Jev incremental-value benchmark

B3 consumes the same frozen B2 dataset, feature fingerprint, five-minute
target, chronological split, purge, embargo, and calibration path. It adds no
context input, LightGBM, broker, portfolio, execution, provider SDK, network,
credential, or real Jev request. The Jev-shaped adapter reads deterministic
recorded JSON responses only.

The CLI surfaces are:

```text
market-os btc-paper b3 run --dataset-revision <revision> --history-store-root <b1-root> --fixture <recorded-responses.json> --store-root <b3-root>
market-os btc-paper b3 inspect <run-id> --resource manifest|config|fixture_cases|responses|abstentions|splits|predictions|metrics|calibration|control_baselines|matched_controls|report|lineage|artifacts|fingerprints|replay --store-root <b3-root>
```

The API surfaces are:

```text
POST /v1/btc/b3/runs
GET /v1/btc/b3/<run-id>/<resource>?store_root=<b3-root>
```

The versioned contract records the B2 dataset/feature revision, exact
question and answer schema, provider/model/resolved-version/adapter identity, request
and response fingerprints, eligibility/availability timestamps, usage/cost/
latency status, failures, abstentions, cache metadata, split/calibration
fingerprints, and artifact lineage. Offline latency, usage, and cost are
`unknown-not-observed-offline`.

E1 is the numerical B2 conditional-rate arm. E2 uses the same numerical input
plus a typed recorded Jev assessment. Matched deltas are computed only on the
identical held-out test-row intersection where both arms have usable
predictions. Jev output is an experimental typed assessment, never `BUY`,
`SELL`, an order, a risk override, execution authority, or a calibrated
five-minute BTC return probability. The B3 result is explicitly not promoted;
see [ADR-0019](../decisions/ADR-0019-u3-b3-jev-experimental-boundary.md), the
[implementation report](../U3-B3-JEV-INCREMENTAL-BENCHMARK-REPORT.md), and
`docs/evidence/u3-b3-jev-incremental.json`.

## U3/API bounded connectivity

The connectivity slice is fixture-first and paper-only. Offline mode performs
zero network requests and uses synthetic Binance ticker/kline and TypeSafe
wire-format fixtures. The public CLI surfaces are:

```text
market-os btc-paper connectivity offline
market-os btc-paper connectivity binance --operation ticker|kline --allow-live-probe
market-os btc-paper connectivity jev --allow-live-probe --model-version <version> --max-spend-usd 0.05 --paper-only
market-os btc-paper connectivity inspect <probe-id> --resource manifest|result|fingerprints|replay
```

Binance is restricted to `https://data-api.binance.vision` and the public GET
paths `/api/v3/ticker/price` and `/api/v3/klines`; only BTCUSDT and 1m klines
are supported. No authenticated, account, order, withdrawal, margin, futures,
WebSocket, or execution endpoint exists in this slice.

Jev uses the documented `POST https://api.typesafe.ai/v1/systemone` wire
contract through stdlib HTTPS transport. A live Jev probe requires
`TYPESAFE_API_KEY`, an explicit `--allow-live-probe`, a versioned model, paper
only mode, the exact `$0.05` ceiling, one request, and zero retries. Responses
preserve provider/model/version, question version, request/response
fingerprints, timestamps, latency, usage, cost status, failure, abstention,
and validation status. Choice probabilities, confidence, Noul, and Score are
descriptive model outputs, not calibrated five-minute BTC-return probabilities.

Read-only inspection is exposed at:

```text
GET /v1/btc/connectivity/<probe-id>/<resource>?store_root=<connectivity-root>
```

See [ADR-0020](../decisions/ADR-0020-u3-api-connectivity-boundary.md), the
[implementation report](../U3-API-CONNECTIVITY-REPORT.md), and
`docs/evidence/u3-api-connectivity.json`.
