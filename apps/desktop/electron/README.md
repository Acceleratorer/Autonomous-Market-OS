# Market OS Electron shell

This is the U6 local desktop slice. It wraps the existing server-rendered
Next.js operator and starts the existing Python gateway on loopback. Python
remains the accounting, storage, recovery, and inspection authority.

## Local development

Enable Corepack once on a new machine so the pinned pnpm release is available:

```text
corepack enable
```

Build the web operator first:

```text
cd apps/web/next-operator
pnpm install --frozen-lockfile
pnpm run build
```

Install the shell dependency and start it from the repository root:

```text
cd apps/desktop/electron
pnpm install --frozen-lockfile
pnpm run start
```

Run the shell's local checks with `pnpm test`. The Electron package is an
independent package root and shares the Next.js renderer; it does not create a
second desktop UI or move domain logic out of Python.

The shell prefers `python -m apps.gateway --host 127.0.0.1 --port 8787` and
`next start --hostname 127.0.0.1 --port 3000`, waits for `/readyz` and
`/healthz`, then loads `/overview`. If either default port is already occupied,
the shell selects a free loopback port automatically. Set
`MARKET_OS_API_PORT` or `MARKET_OS_NEXT_PORT` to pin a port; set
`MARKET_OS_PYTHON`,
`MARKET_OS_NEXT_NODE`, or `MARKET_OS_NEXT_COMMAND` only to point at an explicit
local executable; the default commands are intentionally fixed and use no
shell interpolation.

## U6.4-A unsigned artifact

The first packaging slice creates a target-labelled directory containing the
Electron shell, the built Next.js renderer, and the Python source sidecar. The
artifact includes `artifact-manifest.json`, component SHA-256 fingerprints,
and `slots/current.json` plus `slots/known-good.json` metadata.

Build and smoke a Windows artifact from this package root:

```text
cd apps/web/next-operator
pnpm run build

cd ../../desktop/electron
pnpm install --frozen-lockfile
pnpm exec electron --version
pnpm run package:unsigned -- --target windows-x64 --output ../../../output/u6.4/market-os-windows-x64
pnpm run smoke:artifact -- --artifact ../../../output/u6.4/market-os-windows-x64
```

Electron 45 publishes its launcher without a lifecycle download hook. The
`pnpm exec electron --version` step explicitly fetches the target-native binary
before packaging; `package.cjs` fails closed if the binary is still missing.

The smoke runs the artifact from its own directory and verifies `/readyz`,
`/healthz`, `/overview`, `/runtime`, the unsigned release state, and loopback
cleanup. Linux builds use `--target linux-x64` on a Linux host. The Python
sidecar is source-bundled and requires system Python 3.11+ with the packages in
the root `pyproject.toml`. Its default state root is `python/.market_os`, so
artifact state stays local to the packaged sidecar directory.

After signing, repeat the same check with `--expect-signed` to verify the
runtime page exposes the Ed25519 public-key state:

```text
pnpm run smoke:artifact -- --artifact ../../../output/u6.4/market-os-windows-x64 --expect-signed
```

The artifact is intentionally unsigned and has rollback disabled. Signing,
current/known-good promotion, hash-gated rollback, and CI release artifacts
are implemented as the local U6.4-B release contract below. No credentials,
providers, mutation routes, public listeners, Tailscale identity, or live
trading are added.

## U6.4-B signing and release slots

Signing uses an external Ed25519 private key. The key is never copied into the
artifact or committed to the repository. The signer signs the exact final
`artifact-manifest.json` bytes and writes only public verification metadata to
`release-signature.json`:

```text
cd apps/desktop/electron
pnpm run sign:artifact -- \
  --artifact ../../../output/u6.4/market-os-windows-x64 \
  --private-key C:/secure/market-os-release-private.pem
pnpm run release:inspect -- \
  --artifact ../../../output/u6.4/market-os-windows-x64
```

Promotion verifies the manifest sidecar hash and Ed25519 signature before
atomically writing `slots/current.json`. The previous current slot is retained
as `slots/known-good.json`. A failed launch can be simulated locally; the
transaction restores both slot files before returning the failure:

```text
pnpm run release:promote -- \
  --artifact ../../../output/u6.4/market-os-windows-x64 \
  --simulate-launch-failure
pnpm run release:promote -- \
  --artifact ../../../output/u6.4/market-os-windows-x64
pnpm run release:rollback -- \
  --artifact ../../../output/u6.4/market-os-windows-x64
```

Rollback is hash-gated: the known-good slot must resolve to an artifact whose
manifest digest and signature still verify. A tampered or incomplete release
is rejected without changing the current slot. `pnpm test` covers external-key
signing, failed-launch restoration, successful promotion, rollback, and
tamper rejection. A single freshly packaged directory has no distinct prior
artifact, so its first promotion may correctly report rollback unavailable;
the promotion test uses separate candidate and known-good directories.

U5.5 owner-VM promotion and rollback remain a separate pending gate. The
runtime page is observational and continues to show local, private,
read-only, paper-only, and execution-disabled boundaries.

## U6.4-C target-native CI hardening

U6.4-C builds the directory artifact on the matching GitHub runner:
`windows-x64` on `windows-latest` and `linux-x64` on `ubuntu-latest`. The
Python sidecar remains source-bundled under `python/` and launches with the
runner's native `python` or `python3` command. This keeps the sidecar isolated
without introducing an embedded runtime or native installer.

The CI job creates two signed versions, runs the four-route smoke on each, and
uploads both manifests, public signature metadata, smoke reports, and the
promotion/rollback drill report. The drill proves failed-launch metadata
restoration, preserves the previous artifact as `known-good`, observes
`rollback_available: true` after promotion, and restores the older artifact.

Run the same local drill after a production build:

```text
cd apps/desktop/electron
pnpm exec electron --version
pnpm run release:ci -- --target windows-x64 --output ../../../output/u6.4-ci/windows-x64
```

The command needs the matching host platform, a built Next.js renderer, and
Python 3.11+ with the project dependencies. It never enables credentials,
provider access, mutation routes, public listeners, or live execution.
