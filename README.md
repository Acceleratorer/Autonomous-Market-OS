# Autonomous Market OS

Synthetic, paper-only market research and portfolio inspection workspace.
The default product boundary is read-only: no live trading, provider
credentials, Binance transport, public Python gateway, or HTTP/CLI mutation
route is enabled.

## Clone and run

```bash
git clone https://github.com/Acceleratorer/Autonomous-Market-OS.git
cd Autonomous-Market-OS

python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1

python -m pip install -e . pytest
python -m pytest -q
python -m apps.gateway --host 127.0.0.1 --port 8787
```

In a second terminal:

```bash
cd apps/web/next-operator
corepack enable
pnpm install --frozen-lockfile
pnpm run dev
```

Open `http://127.0.0.1:3000`. The Next.js operator reads the Python gateway
server-side and keeps all accounting, risk, persistence, recovery, replay,
audit, backup, and portfolio inspection authority in Python.

The repository keeps the web operator and Electron shell as independent
JavaScript package roots. Both pin `pnpm@11.25.0` through `packageManager` and
commit a `pnpm-lock.yaml`; there is intentionally no root JavaScript workspace.
See [`docs/JS-PACKAGE-MANAGEMENT.md`](docs/JS-PACKAGE-MANAGEMENT.md) for the
reproducible install, CI, Docker, and desktop workflows.

## Local Electron shell

The desktop slice reuses the built Next.js operator and starts the Python
gateway on loopback; it does not ship a second renderer:

```bash
cd apps/web/next-operator
pnpm install --frozen-lockfile
pnpm run build

cd ../../desktop/electron
pnpm install --frozen-lockfile
pnpm run start
```

Use `pnpm test` in `apps/desktop/electron` for the local lifecycle/security
and U6.4-B release-contract checks. U6.4-A provides the unsigned artifact and
clean-directory smoke; U6.4-B adds external-key signing, hash-gated
current/known-good slot promotion, failed-launch restoration, and explicit
rollback. U6.4-C runs target-native Windows/Linux CI packaging, signed smoke,
and a two-version rollback drill. U7-G adds a deterministic quality-benchmark
reviewer report, U7-H adds a synthetic-session accounting reviewer report, and
U7-I adds a fail-closed local evidence pack index, U7-J adds a synthetic
economic observability report, and U7-K adds a typed CLI tool registry audit,
all with stable JSON/Markdown output; real-model
promotion and provider cost reporting remain deferred. Owner-VM
promotion remains a separate U5.5 gate.

## Container quick start

The local container shape keeps Python on loopback inside a shared network
namespace and exposes only the operator on host loopback:

```bash
docker compose up --build
```

Open `http://127.0.0.1:3000`. This is a private development package. It does
not configure Tailscale, public ingress, credentials, live data, or mutation
routes.

For a private Kubernetes development shape, see
[`deploy/k8s/README.md`](deploy/k8s/README.md). For the owner-approved U5.5
Linux/systemd/Tailscale promotion path, see
[`deploy/u5-5/README.md`](deploy/u5-5/README.md).

Infrastructure and operations packaging lives under `deploy/iac/`:
Terraform validates the provider-neutral U5.5 contract and Ansible prepares
the private Linux host. Optional local observability is documented in
[`observability/README.md`](observability/README.md); optional offline MLOps
tracking is documented in [`mlops/README.md`](mlops/README.md).

## Workspace layout

This repository is the separate fusion project. The original HKUDS repositories live under `company-projects/` and remain independent Git repositories with their own histories, branches, dependencies, and working changes.

```text
HKUDS/
├── company-projects/        # Original repositories; do not merge into this Git history
│   ├── AI-Trader/
│   ├── ClawWork/
│   ├── CLI-Anything/
│   ├── DeepCode/
│   ├── DeepTutor/
│   ├── LightRAG/
│   ├── MiniRAG/
│   ├── nanobot/
│   ├── OpenHarness/
│   ├── Paper2Slides/
│   ├── RAG-Anything/
│   ├── Vibe-Trading/
│   └── ViMax/
├── market_os/               # Fusion product implementation; see STRUCTURE.md
├── apps/                    # thin web, CLI, and gateway surfaces
├── docs/                    # Fusion plans, decisions, and evidence
└── pyproject.toml
```

The fusion project consumes the original repositories through adapters and documented contracts. It does not own their source trees.

This is a personal project for market research, reproducible backtesting, paper trading, and later controlled execution.

This repository owns the shared contracts, workflow orchestration boundary, persistence model, CLI, and service API. The source projects remain independent repositories and are connected through narrow adapters:

- `Vibe-Trading`: research and backtesting
- `LightRAG` / `RAG-Anything`: retrieval and document understanding
- `AI-Trader`: signals and paper execution
- `OpenHarness`: proposed orchestration runtime
- `nanobot` / `DeepCode`: future runtime and channel adapters

## Current Slice

The Phase 0 slice runs a deterministic US equities/ETF workflow:

1. Create a research task.
2. Retrieve timestamped market and document evidence.
3. Produce cited research.
4. Run a reproducible backtest.
5. Create a paper-only order plan.
6. Apply risk checks.
7. Persist events and artifacts.
8. Expose the workflow through the CLI and service API.

Live execution is disabled in `market-os.v1`.

## Checks

```text
python -m pytest -q market_os/tests
python -m compileall -q market_os
```

See `STRUCTURE.md`, `docs/PRODUCT-VISION.md`, `docs/PHASES.md`, `docs/ROADMAP.md`, `docs/TARGET-STRUCTURE.md`, `docs/APP-SURFACES-CONTRACT.md`, `docs/WEB-STACK-OPTIONS.md`, `docs/U5.5-AUTHENTICATED-CONNECTED-WEB-CONTRACT.md`, `docs/U5.2-STATIC-DEPLOYMENT-READINESS.md`, `docs/FUSION-MAP.md`, `docs/INTEGRATION-GUIDE.md`, and `docs/decisions/ADR-0001-phase-0.md` for the product boundary and next milestone.

The current web surface is a static, read-only paper-only preview. Build it
with `python scripts/build_web_artifact.py --output <new-directory>`; public
deployment and authenticated access remain separate gates.

## Project guidance

- [Contributing](CONTRIBUTING.md)
- [JavaScript package management](docs/JS-PACKAGE-MANAGEMENT.md)
- [Security policy](SECURITY.md)
- [MIT License](LICENSE)
- [DevOps runbook](docs/DEVOPS-RUNBOOK.md)
