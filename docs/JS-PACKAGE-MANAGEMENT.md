# JavaScript package management

The repository has two JavaScript applications:

| App | Path | Purpose |
| --- | --- | --- |
| Next.js operator | `apps/web/next-operator/` | Canonical web renderer and local operator |
| Electron shell | `apps/desktop/electron/` | Thin desktop wrapper around the Next.js renderer |

They remain independent package roots so each packaging contract stays local.
There is no root `package.json` or JavaScript workspace.

## Pinned toolchain

Both `package.json` files declare `pnpm@11.25.0` in `packageManager`, and each
app commits its own `pnpm-lock.yaml`. Node.js 20.9 or newer is required by the
apps. On a new machine, enable Corepack once:

```bash
corepack enable
```

Corepack then selects the pinned pnpm release when a command is run inside
either app directory.

## Local workflows

Install and run the web operator:

```bash
cd apps/web/next-operator
pnpm install --frozen-lockfile
pnpm run dev
```

Build and inspect the web operator:

```bash
cd apps/web/next-operator
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run build
pnpm run start
```

Build the web renderer and run the Electron shell:

```bash
cd apps/web/next-operator
pnpm install --frozen-lockfile
pnpm run build

cd ../../desktop/electron
pnpm install --frozen-lockfile
pnpm run start
```

Run Electron's local tests with `pnpm test`.

The Electron package also owns the U6.4 release-contract commands:

```bash
cd apps/desktop/electron
pnpm run sign:artifact -- --artifact <artifact-dir> --private-key <external.pem>
pnpm run release:inspect -- --artifact <artifact-dir>
pnpm run release:promote -- --artifact <artifact-dir>
pnpm run release:rollback -- --artifact <artifact-dir>
```

The private key path must remain outside the repository. These commands only
write public signature metadata and slot records; they do not add credentials,
provider access, mutation routes, or live execution.

## CI and container rules

- CI uses `pnpm install --frozen-lockfile` and `pnpm run ...`.
- The Next.js Docker image copies `pnpm-lock.yaml`, enables Corepack, and
  installs with the frozen lockfile before typechecking and building.
- A lockfile update must be generated from the matching app directory and
  committed with the manifest change.

The migration removed the legacy lockfiles. It does not change the Python
gateway, accounting authority, read-only boundary, or Electron packaging
contract.

Historical evidence JSON keeps its original audit field names so old records
remain machine-readable; those fields describe pre-migration runs and are not
current install instructions.
