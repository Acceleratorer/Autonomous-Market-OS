# M1: `market-os.v1` contracts

**Status:** implemented in the dependency-free fusion package; production adapter and storage choices remain open.

## Contract inventory

The domain contract module is [`market_os/contracts.py`](../market_os/contracts.py). It owns the stable boundary between the CLI, service API, workflow, persistence, and future child-repository adapters.

| Contract | Purpose |
|---|---|
| `AgentProfile` | Agent identity, provider/model, tools, permissions, and memory scope |
| `Task` | User objective, symbols, date range, execution mode, and idempotency key |
| `Run` | Durable lifecycle state for one task execution |
| `RunEvent` | Append-only lifecycle, tool, provenance, and error record |
| `Artifact` | Immutable JSON output with lineage, media type, access policy, and SHA-256 |
| `KnowledgeDocument` | Timestamped document reference and modality |
| `MarketObject` | Timestamped market observation and price basis |
| `Evidence` | Citable market or document evidence |
| `ResearchResult` | Summary, citations, evidence references, and assumptions |
| `BacktestResult` | Reproducible result, equity curve, and input fingerprint |
| `Portfolio` | Cash and positions for the paper portfolio boundary |
| `Order` | One paper order with quantity, reference price, and notional |
| `OrderPlan` | Paper-only collection of orders and total notional |
| `RiskDecision` | Approval/rejection with reasons and limits |
| `Approval` | Explicit approval lifecycle for a later gated execution flow |
| `CancellationRequest` | Durable cancellation intent |
| `ErrorResponse` | Stable client-facing error envelope |

## Validation rules

- Every serialized contract carries `api_version: "market-os.v1"`.
- IDs are bounded ASCII identifiers; required text cannot be blank.
- Dates use `YYYY-MM-DD`; timestamps must be ISO-8601 and UTC with an explicit offset.
- Initial symbols are uppercase US-style equity/ETF symbols.
- Numeric values are finite; cash, prices, quantities, and notionals cannot be negative, and paper order quantities/notionals must be positive.
- Lifecycle and decision fields use explicit allowed values.
- Failed or rejected runs require an error; rejected risk decisions require a reason.
- `Task.execution_mode` and `OrderPlan.mode` accept only `paper`; live execution is rejected with `live_disabled`.
- Artifact digests are lowercase SHA-256 values.

## JSON boundary

`to_json()` emits deterministic compact JSON with sorted keys and ASCII escaping. `from_json()` parses JSON, rejects unknown fields, applies only documented defaults, and validates the resulting dataclass. Tuple fields are normalized from JSON arrays.

Readers currently cover the workflow-facing contracts: `Task`, `Run`, `RunEvent`, `Artifact`, `Evidence`, `ResearchResult`, `BacktestResult`, `Order`, `OrderPlan`, and `RiskDecision`. Metadata-only contracts remain typed Python objects until an adapter needs a transport reader.

Reads without `api_version` default to the current version for backward compatibility. A supplied different version is rejected; there is no silent cross-version coercion.

## Error codes

The stable `ContractError.code` values include `invalid_id`, `required`, `invalid_date`, `invalid_timestamp`, `invalid_number`, `invalid_symbol`, `invalid_range`, `invalid_status`, `missing_error`, `missing_citations`, `missing_reason`, `missing_decision`, `invalid_digest`, `unknown_field`, `missing_field`, `invalid_json`, `unsupported_version`, and `live_disabled`.

The API maps these into the `ErrorResponse` envelope with `code`, `message`, `field`, `request_id`, `retryable`, and `api_version`.

## Fixtures and gate

Representative valid and invalid JSON fixtures live under [`market_os/tests/fixtures/contracts`](../market_os/tests/fixtures/contracts). The contract suite checks fixture decoding, deterministic serialization, round trips, backward-compatible reads, validation failures, version mismatches, and the paper-only guard.

The M1 gate is the focused contract suite plus the workflow integration suite. No real provider, broker, or live execution path is connected by this milestone.

## Deferred by design

- Authentication and tenant identity are transport concerns, not embedded in the first dataclasses.
- Provider-specific model, retrieval, market-data, and broker objects stay inside adapters.
- Production metadata/artifact storage, retention, encryption, and concurrency policy still require a decision.
- Approval and cancellation contracts exist, but asynchronous mid-provider cancellation is a later milestone.
