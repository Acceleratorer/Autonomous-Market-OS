"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fsp = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { inspectInstallPreflight } = require("../scripts/install-preflight.cjs");

async function writeJson(file, value) {
  await fsp.mkdir(path.dirname(file), { recursive: true });
  await fsp.writeFile(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

async function makeArtifact() {
  const root = await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-install-preflight-"));
  const electronBinary = process.platform === "win32" ? "electron.exe" : "electron";
  const files = [
    `shell/node_modules/electron/dist/${electronBinary}`,
    "shell/src/main.cjs",
    "web/.next/BUILD_ID",
    "web/node_modules/next/dist/bin/next",
    "python/market_os/__init__.py",
    "python/apps/__init__.py",
    "python/apps/gateway/__main__.py",
    "python/pyproject.toml",
  ];
  for (const relative of files) {
    const file = path.join(root, relative);
    await fsp.mkdir(path.dirname(file), { recursive: true });
    await fsp.writeFile(file, "fixture\n", { encoding: "utf8", mode: relative.endsWith(electronBinary) ? 0o755 : 0o644 });
  }
  const manifest = {
    schema: "market-os.u6.4-artifact@v1",
    status: "unsigned-reproducible",
    version: "0.1.0-test.1",
    target: process.platform === "win32" ? "windows-x64" : "linux-x64",
    platform: { os: process.platform === "win32" ? "windows" : "linux", arch: "x64", node: ">=20.9.0", electron: "45.2.3" },
    sidecar: {
      type: "python-source",
      distribution: "target-native-source",
      root: "python",
      command: [process.platform === "win32" ? "python" : "python3", "-m", "apps.gateway"],
      interpreter: process.platform === "win32" ? "python" : "python3",
      requires_python: ">=3.11",
      host: "127.0.0.1",
    },
    storage: { root: "python/.market_os", scope: "artifact-local", shared_host_root: false },
    entrypoints: {
      shell: "shell/src/main.cjs",
      electron_windows: "shell/node_modules/electron/dist/electron.exe",
      electron_linux: "shell/node_modules/electron/dist/electron",
      next_cli: "web/node_modules/next/dist/bin/next",
      gateway: "python/apps/gateway/__main__.py",
    },
    runtime_boundary: {
      loopback_only: true,
      synthetic: true,
      paper_only: true,
      read_only: true,
      credentials: false,
      provider_requests: 0,
      mutation_routes: false,
      live_trading: false,
    },
  };
  await writeJson(path.join(root, "artifact-manifest.json"), manifest);
  const manifestBytes = await fsp.readFile(path.join(root, "artifact-manifest.json"));
  const digest = crypto.createHash("sha256").update(manifestBytes).digest("hex");
  await fsp.writeFile(path.join(root, "artifact-manifest.json.sha256"), `${digest}  artifact-manifest.json\n`, "utf8");
  await writeJson(path.join(root, "slots/current.json"), { schema: "market-os.u6.4-slot@v1", slot: "candidate", version: manifest.version, manifest_sha256: digest });
  await writeJson(path.join(root, "slots/known-good.json"), { schema: "market-os.u6.4-slot@v1", slot: "known-good", version: "0.1.0-test.0", manifest_sha256: "old" });
  return root;
}

test("installer preflight accepts an isolated signed-ready artifact shape", async () => {
  const root = await makeArtifact();
  try {
    const result = await inspectInstallPreflight({ artifactRoot: root });
    assert.equal(result.status, "passed");
    assert.equal(result.installation.performed, false);
    assert.equal(result.installation.embedded_python, false);
    assert.equal(result.installation.native_service, false);
    assert.equal(result.checks.runtime_boundary, true);
    assert.equal(result.checks.storage_isolation, true);
    assert.equal(result.signature_status, "unsigned");
  } finally {
    await fsp.rm(root, { recursive: true, force: true });
  }
});

test("installer preflight rejects a destination nested inside the source artifact", async () => {
  const root = await makeArtifact();
  try {
    await assert.rejects(
      inspectInstallPreflight({ artifactRoot: root, destination: path.join(root, "installed") }),
      /destination must be separate from artifact source/,
    );
  } finally {
    await fsp.rm(root, { recursive: true, force: true });
  }
});

test("installer preflight rejects a mutation-capable boundary", async () => {
  const root = await makeArtifact();
  try {
    const manifestPath = path.join(root, "artifact-manifest.json");
    const manifest = JSON.parse(await fsp.readFile(manifestPath, "utf8"));
    manifest.runtime_boundary.mutation_routes = true;
    await writeJson(manifestPath, manifest);
    const bytes = await fsp.readFile(manifestPath);
    const digest = crypto.createHash("sha256").update(bytes).digest("hex");
    await fsp.writeFile(path.join(root, "artifact-manifest.json.sha256"), `${digest}  artifact-manifest.json\n`, "utf8");
    await assert.rejects(inspectInstallPreflight({ artifactRoot: root }), /runtime boundary mutation_routes is unsafe/);
  } finally {
    await fsp.rm(root, { recursive: true, force: true });
  }
});
