# Contributing

Thanks for helping improve Autonomous-Market-OS.

## Scope

Keep changes aligned with the repository boundary:

- synthetic and paper-only by default;
- read-only HTTP/CLI inspection;
- Python remains authoritative for accounting, risk, persistence, recovery,
  reservations, replay, audit, backup, and portfolio inspection;
- no Binance, live trading, provider credentials, or public mutation route;
- no changes to `company-projects/`.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e . pytest
python -m pytest -q
python -m compileall -q market_os
```

For the local Next.js operator:

```bash
cd apps/web/next-operator
corepack enable
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run build
```

The JavaScript surfaces are independent package roots and use the pinned
`pnpm@11.25.0` release. Keep `pnpm-lock.yaml` in sync with each app's
`package.json`; do not add a root workspace or restore legacy lockfiles. The
Electron shell follows the same rule in `apps/desktop/electron/`. See
[`docs/JS-PACKAGE-MANAGEMENT.md`](docs/JS-PACKAGE-MANAGEMENT.md) for the full
workflow.

## Before opening a pull request

Run the checks relevant to your change:

```bash
python scripts/ci_checks.py secret-scan
python scripts/ci_checks.py validate-evidence
python scripts/build_web_artifact.py --check
python scripts/ci_checks.py validate-mlops-manifest
git diff --check
```

Frontend changes should also include browser evidence for desktop and mobile,
keyboard focus, reduced motion, no horizontal overflow, and GET-only network
behavior.

Do not commit `.env` files, credentials, portfolio data, generated runtime
state, MLflow runs, Terraform state, Ansible inventories, or private
deployment metadata. Keep commits focused and explain contract or security
changes in the message.
