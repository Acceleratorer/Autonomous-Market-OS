import { readFile } from "node:fs/promises";
import { test } from "node:test";
import assert from "node:assert/strict";
import { resolve } from "node:path";

const root = resolve(process.cwd());

async function source(relativePath: string): Promise<string> {
  return readFile(resolve(root, relativePath), "utf8");
}

test("U6.3 records a verified local Electron lifecycle slice", async () => {
  const evidence = JSON.parse(
    await source("docs/evidence/u6-electron-shell.json"),
  ) as Record<string, any>;
  const runtime = evidence.verification.runtime_smoke as Record<string, any>;

  assert.equal(evidence.schema, "market-os.u6-electron-shell@v1");
  assert.equal(evidence.status, "local-electron-shell-slice-verified-packaging-deferred");
  assert.equal(evidence.platform.container, "electron");
  assert.equal(runtime.readyz_status, 200);
  assert.equal(runtime.healthz_status, 200);
  assert.equal(runtime.overview_status, 200);
  assert.match(runtime.graceful_cleanup, /both custom loopback ports closed/);
  assert.match(evidence.next_gate, /U6\.4/);
});

test("U6.3 keeps the native shell local, read-only, and unprivileged", async () => {
  const [main, preload, runtimeText, evidenceText] = await Promise.all([
    source("apps/desktop/electron/src/main.cjs"),
    source("apps/desktop/electron/src/preload.cjs"),
    source("apps/desktop/electron/src/runtime.cjs"),
    source("docs/evidence/u6-electron-shell.json"),
  ]);
  const evidence = JSON.parse(evidenceText) as Record<string, any>;

  assert.match(main, /contextIsolation:\s*true/);
  assert.match(main, /nodeIntegration:\s*false/);
  assert.match(main, /sandbox:\s*true/);
  assert.match(main, /setWindowOpenHandler\(\(\) => \(\{ action: "deny" \}\)\)/);
  assert.match(main, /will-navigate/);
  assert.match(runtimeText, /shell:\s*false/);
  assert.match(runtimeText, /127\.0\.0\.1/);
  assert.match(preload, /readOnly: true/);
  assert.deepEqual(evidence.boundary, {
    local_only: true,
    synthetic: true,
    paper_only: true,
    get_only: true,
    provider_requests: 0,
    credentials: false,
    mutation_routes: false,
    live_trading: false,
    connected_runtime: false,
    public_listener: false,
    tailscale_enabled: false,
  });
});
