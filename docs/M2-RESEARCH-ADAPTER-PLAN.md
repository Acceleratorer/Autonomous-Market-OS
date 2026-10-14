# M2 research adapter plan

**Starting point:** M2.1 deterministic Vibe-Trading market-data/backtest
adapter
**Orchestration owner:** Market OS
**Real network access in M2.1:** **No**

## 1. First adapter

Implement one fixture-backed **Vibe-Trading research/backtest adapter** against
the existing Market OS provider seam. The first vertical slice should normalize
offline OHLCV rows into `MarketBar`, feed the existing `BacktestProvider`
contract, and return evidence/artifacts through `MarketWorkflow`.

The read-only source seams are:

- `Vibe-Trading/agent/mcp_server.py::get_market_data` for the market-data
  request shape and source provenance fields;
- `Vibe-Trading/agent/backtest/runner.py::BacktestConfigSchema` and
  `fetch_data_map` for validated backtest inputs and loader metadata;
- `Vibe-Trading/agent/src/tools/backtest_tool.py::run_backtest` for the
  run-directory/config/artifact boundary;
- `Vibe-Trading/agent/mcp_server.py::backtest` for the research-facing tool
  envelope;
- `Vibe-Trading/agent/mcp_server.py::start_research_goal`,
  `add_goal_evidence`, and `get_research_reports` for the goal, evidence, and
  citation-oriented research records.

No child code is copied or modified. M2.1 may use equivalent local fixtures
that model these shapes.

## 2. Why this is the smallest useful improvement

It directly extends the current finance workflow from synthetic price tuples
to a normalized, provenance-carrying market-bar contract and a reproducible
backtest request. It exercises research, evidence, backtest, artifact lineage,
and paper-only orchestration in one vertical run. It also avoids introducing
LightRAG's multi-store/LLM configuration or RAG-Anything's parser and
multimodal runtime before their document contracts are stable.

## 3. Contract changes

`market_os.providers` now defines dependency-free contracts for:

- `MarketDataProvider`, `DocumentProvider`, `ResearchProvider`, and the existing
  `BacktestProvider`;
- `ProviderHealth`, `ProviderCapability`, `ProviderDeadline`, and
  `ProviderError`;
- `RateLimit`, `DataFreshness`, `LicenseMetadata`, `Provenance`, `CachePolicy`,
  and `DeterministicFixture`;
- normalized `MarketBar` and `DocumentRecord` values.

The adapter must map provider-specific objects to these types before they
enter Market OS. Root contracts remain dependency-free and paper-only.

## 4. Fixture strategy

- Store a small, versioned OHLCV fixture in the adapter test area.
- Include symbol, venue, currency, adjustment basis, source reference, and
  retrieval timestamp in every normalized bar.
- Use a fixed fixture identifier and checksum; do not read a network or user
  credential.
- Run one deterministic `MarketWorkflow` request twice with the same
  idempotency key and compare the complete stable result and artifact hashes.

## 5. Failure and timeout behavior

- The caller supplies a positive `ProviderDeadline`; the adapter must fail
  with a normalized `ProviderError` when it expires.
- Missing symbols, malformed rows, mixed currencies, invalid adjustment basis,
  and stale or absent provenance are hard failures.
- Rate-limit state is returned as metadata; the adapter does not silently retry
  beyond the declared policy.
- Market OS records the provider failure as a terminal run and keeps partial
  artifacts inspectable. Cancellation remains owned by `MarketWorkflow`.

## 6. Provenance and licensing

Every bar/document result carries `Provenance`. Documents also carry
`LicenseMetadata`; an adapter must reject unknown usage classification when a
result is intended for persisted research output. Retrieval timestamps and
source timestamps are distinct and preserved. Any provider-specific source,
volume unit, adjustment basis, or citation reference is retained in adapter
metadata rather than inferred by the workflow.

## 7. Focused tests

1. Contract validation for bars, documents, deadlines, freshness, licensing,
   cache policy, and fixture identity.
2. Fixture adapter happy path for one symbol and a bounded date range.
3. Missing-symbol, malformed-row, stale-data, and unsupported-license failures.
4. Deadline and cancellation behavior at the provider seam.
5. Stable idempotent replay through `MarketWorkflow`.
6. Artifact lineage from normalized bars to evidence and backtest output.
7. Paper-only rejection remains unchanged.

## 8. Acceptance criteria

- One offline Vibe-Trading-shaped adapter completes a deterministic research and
  backtest run through `MarketWorkflow`.
- All returned bars use the normalized `MarketBar` contract and retain source,
  adjustment, freshness, and retrieval metadata.
- Provider failures become inspectable terminal Market OS results.
- Repeated requests with the same idempotency key return byte-stable results.
- No network, credentials, broker, live execution, or child-repository changes
  are required.
- The adapter can be removed without changing the root workflow contract.

## 9. Explicit exclusions

M2.1 does not implement real Vibe-Trading loaders, LightRAG storage, RAG-
Anything parsers, news/document network access, OpenHarness-native recovery,
live execution, broker access, or a new persistence backend. It also does not
merge child source trees into this repository.

## 10. Later source adapters

### LightRAG

The narrow seam is `LightRAG.ainsert`/`aquery` in `lightrag/lightrag.py`, with
workspace isolation and source IDs used for citation references. It requires
configured LLM and embedding functions, `initialize_storages()`, and one of
several KV/vector/graph/doc-status storage backends. Its independent stores
and documented non-transactional residues make it a later document/retrieval
adapter after the root `DocumentRecord` and citation policy are proven.

### RAG-Anything

The narrow seam is `RAGAnything.process_document_complete` plus `aquery` or
`aquery_with_multimodal`, with optional batch processing through
`process_documents_batch[_async]`. It requires parser/runtime configuration,
working and output directories, LightRAG integration, and optional MinerU,
Docling, PaddleOCR, vision, audio, or video dependencies. It is a later
multimodal document adapter, not part of M2.1.

## 11. Dependency and licensing notes

Vibe-Trading, LightRAG, and RAG-Anything are MIT licensed at the inspected
commits. Vibe-Trading has a large Python 3.11+ dependency graph and many
optional data sources. LightRAG has a broad storage and model dependency graph;
RAG-Anything adds parser and multimodal dependencies. The fusion repository
will not add those dependencies until a concrete adapter passes its contract
and operational review.
