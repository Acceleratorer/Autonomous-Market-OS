# Autonomous Market OS structure

This file describes the repository as it exists today. It separates the
current implementation from the future application layout in
[`docs/TARGET-STRUCTURE.md`](docs/TARGET-STRUCTURE.md).

## Product boundary

Market OS is a local, deterministic, synthetic and paper-only system. The
repository owns domain contracts, calculations, persistence, recovery, risk,
paper execution, and the transport surfaces that inspect those results.

The repositories under `D:\Code\Github\company-projects` remain independent.
Adapters call them through narrow, typed seams. They do not become part of
this source tree.

## Current repository map

```text
Autonomous-Market-OS/
├── market_os/                 Python product package
│   ├── cli.py                 public CLI entrypoint (`market-os`)
│   ├── api.py                 local HTTP/API and B4 read-only dashboard routes
│   ├── workflow.py            task orchestration and run lifecycle
│   ├── contracts.py           shared evidence and artifact contracts
│   ├── providers.py           provider capability and error contracts
│   ├── provider_selection.py  explicit provider composition
│   ├── store.py               local artifact and event persistence
│   ├── research.py            deterministic research synthesis
│   ├── model_summary.py       typed model-summary validation and gating
│   ├── quality_benchmark.py   research-quality benchmark calculations
│   ├── strategy.py            synthetic strategy configuration and decisions
│   ├── strategy_replay.py     deterministic strategy replay
│   ├── accounting.py          synthetic portfolio accounting reports
│   ├── synthetic_session.py   synthetic session artifact creation
│   ├── synthetic_session_api.py read-only session inspection
│   ├── synthetic_session_report.py stable synthetic accounting reviewer report
│   ├── synthetic_server.py    loopback synthetic HTTP server
│   ├── synthetic_catalog.py   session catalog and comparison
│   ├── synthetic_replay.py    generic synthetic replay helpers
│   ├── evaluation_protocol.py offline feature/evaluation protocol
│   ├── synthetic_evaluation.py synthetic evaluation runner
│   ├── synthetic_reporting.py synthetic stability reports
│   ├── synthetic_artifacts.py content-addressed synthetic bundles
│   ├── synthetic_audit.py     synthetic artifact validation
│   ├── btc_history.py         BTC historical storage and canonical rows
│   ├── btc_connectivity.py    bounded BTC/Jev connectivity probes
│   ├── btc_features.py        BTC features, labels, splits, and baselines
│   ├── btc_jev_evaluation.py  recorded Jev-shaped BTC evaluation
│   ├── btc_question_evaluation.py B3.1 question normalization/evaluation
│   ├── btc_paper.py           BTC paper experiment contracts and reports
│   ├── paper_venue.py         synthetic venue and fill mechanics
│   ├── portfolio_broker.py    B4 paper portfolio, shared membership, reservations, risk, ledger, and recovery
│   ├── portfolio_backup.py    validated local ZIP backup, restore, and retention preflight
│   ├── portfolio_migration.py read-only migration preflight compatibility seam
│   ├── schema_migration.py B4.18 copy-on-write schema transformer and validation
│   ├── adapters/              LightRAG, Vibe-Trading, and OpenAI seams
│   ├── orchestration/         protocol, recovery, parity, and probes
│   └── deployment/             bounded local service wrapper
├── apps/                      thin product surfaces
│   ├── web/public/            canonical static read-only dashboard source
│   ├── web/operator/          local loopback-only GET-only operator shell
│   │   ├── index.html         operator document
│   │   ├── operator.js        operator behavior
│   │   └── operator.css       operator presentation
│   ├── cli/                   CLI application entrypoint
│   ├── gateway/               local HTTP service entrypoint
│   └── desktop/electron/      local Electron shell and release evidence tooling
├── tests/                     TypeScript static dashboard contract tests
├── scripts/                   CI checks and bounded smoke harnesses
├── docs/                      roadmap, contracts, ADRs, reports, evidence, operations
├── docs/hosting/market-os/    static read-only preview and hosting instructions
├── .github/workflows/         offline CI and validation automation
├── pyproject.toml             package, CLI entrypoint, and pytest configuration
└── README.md                  repository orientation
```

The exact current worktree classification is recorded in
`docs/WORKTREE-BASELINE-MANIFEST.json`; the stack and connected-runtime review
is recorded in `docs/STACK-AND-RUNTIME-REVIEW.md`. Those files are planning and
inventory artifacts, not authorization to stage, expose, or deploy anything.
Machine-readable U5.5 planning evidence lives in
`docs/evidence/u5-5-stack-runtime-review.json`.
The repository-grounded stack and codebase report lives in
`docs/CODEBASE-AND-STACK-UNDERSTANDING-REPORT.md`, with machine-readable
evidence in `docs/evidence/codebase-stack-understanding.json`.

## Responsibility map

| Area | Current modules | Responsibility |
|---|---|---|
| Web/API | `api.py`, `synthetic_session_api.py`, `synthetic_server.py`, `deployment/` | HTTP transport, read-only inspection, health/readiness, and local HTML views |
| CLI | `cli.py` | Command parsing and dispatch; domain calculations remain in package modules |
| Orchestration | `workflow.py`, `orchestration/`, `provider_selection.py` | Tasks, runs, cancellation, recovery, provider composition |
| Contracts | `contracts.py`, `providers.py`, `model_summary.py` | Typed boundaries, provenance, capabilities, errors, and model gates |
| Persistence | `store.py`, `portfolio_broker.py` | Append-only events, artifacts, checkpoints, recovery, and fingerprints |
| Portfolio/risk | `portfolio_broker.py`, `portfolio_backup.py`, `portfolio_migration.py`, `schema_migration.py` | Paper wallet, shared strategy membership, portfolio-wide reservations, orders, approvals, limits, audit outcomes, backup, read-only retention/archive preflight, migration preflight, and local copy-on-write migration |
| Execution | `paper_venue.py`, `portfolio_broker.py` | Synthetic market events and paper fills; no live venue |
| Math/statistics | `btc_features.py`, `evaluation_protocol.py`, `btc_jev_evaluation.py`, `btc_question_evaluation.py`, `quality_benchmark.py`, `quality_report.py`, `synthetic_session_report.py` | Features, labels, baselines, calibration, metrics, replay, evaluation, and stable reviewer projections |
| Strategy/accounting | `strategy.py`, `strategy_replay.py`, `accounting.py`, `synthetic_replay.py` | Signals, deterministic replay, PnL/accounting and synthetic simulation |
| Data | `btc_history.py`, `btc_connectivity.py` | Canonical BTC rows, manifests, readiness, and bounded connectivity probes |
| Providers | `adapters/` | Optional external runtimes behind fixture-first typed adapters |
| Tests | `market_os/tests/`, `tests/` | Python behavior and TypeScript dashboard contract coverage |
| Operations | `scripts/`, `apps/desktop/electron/scripts/`, `.github/workflows/`, `docs/evidence/` | CI checks, artifact smoke/release reports, quality reports, validation and machine-readable evidence |

Application surfaces are grouped under `apps/web`, `apps/cli`, and
`apps/gateway`. Their names are the product-facing boundary; `market_os.api`
and `market_os.cli` remain stable compatibility entrypoints for tests,
packaging, and local wrappers.

The static web artifact has a separate U5.2 readiness gate documented in
[`docs/U5.2-STATIC-DEPLOYMENT-READINESS.md`](docs/U5.2-STATIC-DEPLOYMENT-READINESS.md).
`scripts/build_web_artifact.py` packages exactly `index.html`, `.htaccess`, and
`DEPLOYMENT.txt` after parity and paper-only boundary checks. This is artifact
readiness only; it does not select a framework or authorize public deployment.
The U5.3 contract also emits a versioned artifact manifest and correlates local
gateway responses with query-free audit records using `X-Request-ID`.
The U5.4 local operator shell lives under `apps/web/operator`; it consumes the
versioned B4 inspection routes and does not own domain or mutation logic.
Its product-facing assets use the `operator.*` prefix. The previous `app.js` and
`styles.css` URLs remain read-only compatibility aliases at the local gateway.

The web, CLI, and gateway folders are the active product surface split. Add
`apps/desktop` or `apps/mobile` only when a concrete shell workflow exists;
there is no generic `apps/app` bucket.

## Data flow

```text
fixture or bounded input
  -> typed provider/data contract
  -> workflow or evaluation protocol
  -> deterministic calculation / risk / paper execution
  -> append-only events and content-addressed artifacts
  -> local CLI, HTTP, HTML, or static preview inspection
```

Transport layers read the shared domain seams. They do not duplicate portfolio
accounting, risk, matching, feature calculations, or provider policy.

## Naming and compatibility

Implementation modules now use capability names. The old milestone module names
remain as small compatibility aliases so historical tests, reports, and external
local imports continue to work while callers migrate:

| Historical import | Current implementation |
|---|---|
| `b41_broker` | `portfolio_broker` |
| `b411_backup` / `b412_migration` | `portfolio_backup` / `portfolio_migration` |
| `b34_strategy` / `b35_strategy_replay` / `b36_accounting` | `strategy` / `strategy_replay` / `accounting` |
| `b38_synthetic_session` / `b39_synthetic_api` | `synthetic_session` / `synthetic_session_api` |
| `b310_synthetic_server` / `b311_synthetic_catalog` | `synthetic_server` / `synthetic_catalog` |
| `b31_offline` / `b31_synthetic_*` | `evaluation_protocol` / `synthetic_*` |
| `btc_b2` / `btc_b3` / `btc_b31` | `btc_features` / `btc_jev_evaluation` / `btc_question_evaluation` |

Test modules also use capability names, for example `test_portfolio_broker.py`,
`test_btc_features.py`, and `test_synthetic_acceptance.py`. CI and documentation
refer to the new paths. Fixture directories, evidence filenames, and versioned
API/schema identifiers preserve their historical identities.

`cli.py`, `api.py`, and `pyproject.toml` remain stable public entrypoints and
configuration paths.

The `apps/` surfaces are thin compatibility-friendly entrypoints. They do not
move or rename the canonical `market_os` modules until a real web, desktop, or
mobile workflow requires that change.

The application-surface contract and naming decision live in
`docs/APP-SURFACES-CONTRACT.md` and
`docs/decisions/ADR-0026-application-surfaces-and-naming.md`.
The web stack and authenticated connected-access gate live in
`docs/WEB-STACK-OPTIONS.md`,
`docs/U5.5-AUTHENTICATED-CONNECTED-WEB-CONTRACT.md`, and
`docs/decisions/ADR-0029-web-stack-and-auth-gate.md`.

## Future application split

The local Next.js operator now lives under `apps/web/next-operator/` as a thin
consumer of the shared Python contracts. It remains loopback-only and
read-only. Desktop and mobile shells do not exist yet; when a concrete shell
workflow is approved, add them under `apps/desktop` and `apps/mobile` without
moving domain logic out of `market_os`. The target layout and promotion rules
are documented in [`docs/TARGET-STRUCTURE.md`](docs/TARGET-STRUCTURE.md).

The B4.18 local persistence transformer lives in `market_os/schema_migration.py`.
Its contract, decision record, and readiness evidence live under `docs/`; it
preserves source stores through backup-first copy-on-write replay validation.

The B4.19 local capability-authorization seam lives in
`market_os/local_mutation.py`. It verifies in-memory HMAC capabilities for the
existing broker mutations and records only safe authorization context; it does
not add HTTP or CLI mutation routes and does not claim human authentication.

Next.js is selected for the local operator and private single-tenant preview
direction. This does not select a connected host, identity provider, or public
listener; those decisions remain in the U5.5 access gate.

The U5.5 runtime/identity contract v1, recorded in
`docs/decisions/ADR-0050-u5-5-runtime-identity-contract.md`, now defines those runtime, identity,
authorization, storage-isolation, session, audit, rollback, secrets, and abuse
boundaries, but remains planning-only until a concrete host and identity path
are selected and verified. DirectAdmin remains a static preview target only.

## Safe change rules

1. Put domain truth in `market_os`; keep transport and presentation thin.
2. Add a package only when a real workflow needs it.
3. Preserve synthetic, paper-only, local boundaries unless a new milestone explicitly changes them.
4. Update tests and evidence when a contract or schema changes.
5. Keep source repositories, credentials, temporary probes, and unrelated worktree changes out of rename work.

The current local-first exit gate is recorded in `docs/LOCAL-EXIT-GATE-REPORT.md` and `docs/evidence/local-exit-gate.json`. B4.20 adds only a read-only retention/archive preflight; source history remains indefinitely retained and deletion remains disabled. Connected web/deployment and other explicitly deferred gates remain closed.
