"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fsp = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const { digestTree } = require("../scripts/install-simulate.cjs");
const { defaultDestination, installPortable, uninstallPortable } = require("../scripts/install-portable.cjs");
const { RUNTIME_MANIFEST_SCHEMA } = require("../scripts/python-runtime.cjs");

const target = process.platform === "win32" ? "windows-x64" : "linux-x64";
const runtimeInterpreter = process.platform === "win32" ? "python.exe" : "bin/python3";

async function writeJson(file, value) {
  await fsp.mkdir(path.dirname(file), { recursive: true });
  await fsp.writeFile(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

async function makeArtifact(version) {
  const root = await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-u6-4-f-artifact-"));
  const files = [
    "shell/src/main.cjs",
    `shell/node_modules/electron/dist/${process.platform === "win32" ? "electron.exe" : "electron"}`,
    "web/.next/BUILD_ID",
    "web/node_modules/next/dist/bin/next",
    "python/market_os/__init__.py",
    "python/apps/__init__.py",
    "python/apps/gateway/__main__.py",
    "python/pyproject.toml",
    `python/runtime/${runtimeInterpreter}`,
  ];
  for (const relative of files) {
    const file = path.join(root, relative);
    await fsp.mkdir(path.dirname(file), { recursive: true });
    const executable = relative.endsWith("python3") || relative.endsWith(process.platform === "win32" ? "electron.exe" : "electron");
    await fsp.writeFile(file, "fixture\n", { encoding: "utf8", mode: executable ? 0o755 : 0o644 });
  }
  const runtimeRoot = path.join(root, "python", "runtime");
  const runtimeManifestPath = path.join(runtimeRoot, "runtime-manifest.json");
  await writeJson(runtimeManifestPath, {
    schema: RUNTIME_MANIFEST_SCHEMA,
    distribution: "cpython",
    version: "3.11.14",
    target,
    source: "python.org",
    source_url: "https://www.python.org/ftp/python/3.11.14/Python-3.11.14.tgz",
    archive_sha256: "a".repeat(64),
    interpreter: runtimeInterpreter,
    dependencies: ["duckdb>=1.4,<3", "pyarrow>=18,<27"],
  });
  const runtimeManifestSha256 = crypto.createHash("sha256").update(await fsp.readFile(runtimeManifestPath)).digest("hex");
  const runtimeTree = await digestTree(runtimeRoot, { excludeRelative: "runtime-manifest.json" });
  const electronBinary = target === "windows-x64" ? "electron.exe" : "electron";
  const manifest = {
    schema: "market-os.u6.4-artifact@v1",
    status: "unsigned-reproducible",
    version,
    target,
    platform: { os: target.split("-")[0], arch: "x64", node: ">=20.9.0", electron: "45.2.3" },
    renderer: { framework: "nextjs", version: "16.4.3", root: "web", route: "/overview" },
    sidecar: {
      type: "python-source",
      distribution: "target-native-embedded-cpython",
      root: "python",
      command: [`runtime/${runtimeInterpreter}`, "-m", "apps.gateway"],
      interpreter: `runtime/${runtimeInterpreter}`,
      requires_python: "3.11.14",
      dependencies: ["duckdb>=1.4,<3", "pyarrow>=18,<27"],
      host: "127.0.0.1",
    },
    runtime: {
      schema: RUNTIME_MANIFEST_SCHEMA,
      distribution: "cpython",
      version: "3.11.14",
      target,
      source: "python.org",
      source_url: "https://www.python.org/ftp/python/3.11.14/Python-3.11.14.tgz",
      archive_sha256: "a".repeat(64),
      manifest_sha256: runtimeManifestSha256,
      root: "python/runtime",
      manifest: "python/runtime/runtime-manifest.json",
      interpreter: `runtime/${runtimeInterpreter}`,
      tree_sha256: runtimeTree,
      dependencies: ["duckdb>=1.4,<3", "pyarrow>=18,<27"],
    },
    storage: { root: "python/.market_os", scope: "artifact-local", shared_host_root: false },
    entrypoints: {
      shell: "shell/src/main.cjs",
      electron_windows: `shell/node_modules/electron/dist/${electronBinary}`,
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
  const digest = crypto.createHash("sha256").update(await fsp.readFile(path.join(root, "artifact-manifest.json"))).digest("hex");
  await fsp.writeFile(path.join(root, "artifact-manifest.json.sha256"), `${digest}  artifact-manifest.json\n`, "utf8");
  await writeJson(path.join(root, "slots/current.json"), { schema: "market-os.u6.4-slot@v1", slot: "candidate", version, manifest_sha256: digest });
  await writeJson(path.join(root, "slots/known-good.json"), { schema: "market-os.u6.4-slot@v1", slot: "known-good", version: "0.1.0-test.0", manifest_sha256: "old" });
  return root;
}

test("portable installer publishes an embedded-runtime artifact per user", async () => {
  const root = await makeArtifact("0.1.0-test.1");
  const destination = await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-u6-4-f-destination-"));
  await fsp.rm(destination, { recursive: true, force: true });
  try {
    const result = await installPortable({ artifactRoot: root, destination, requireSigned: false });
    assert.equal(result.status, "passed");
    assert.equal(result.scope, "per-user");
    assert.equal(result.runtime.version, "3.11.14");
    assert.equal(result.storage.reset, true);
    assert.equal(result.rollback.available, false);
    assert.equal((await fsp.stat(path.join(destination, "artifact-manifest.json"))).isFile(), true);
  } finally {
    await fsp.rm(root, { recursive: true, force: true });
    await fsp.rm(destination, { recursive: true, force: true });
  }
});

test("portable installer rejects a conflicting destination and stale rollback", async () => {
  const root = await makeArtifact("0.1.0-test.6");
  const parent = await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-u6-4-f-conflict-"));
  const destination = path.join(parent, "app");
  try {
    await fsp.mkdir(destination, { recursive: true });
    await fsp.writeFile(path.join(destination, "keep.txt"), "keep\n", "utf8");
    await assert.rejects(
      installPortable({ artifactRoot: root, destination, requireSigned: false }),
      /destination already exists and is not an installed Market OS artifact/,
    );
    await fsp.rm(destination, { recursive: true, force: true });
    await fsp.mkdir(`${destination}.rollback`, { recursive: true });
    await assert.rejects(
      installPortable({ artifactRoot: root, destination, requireSigned: false }),
      /manual rollback path already exists/,
    );
  } finally {
    await fsp.rm(root, { recursive: true, force: true });
    await fsp.rm(parent, { recursive: true, force: true });
  }
});

test("portable installer preserves mutable state and leaves a manual rollback copy", async () => {
  const first = await makeArtifact("0.1.0-test.1");
  const second = await makeArtifact("0.1.0-test.2");
  const destination = path.join(await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-u6-4-f-upgrade-")), "app");
  try {
    await installPortable({ artifactRoot: first, destination, requireSigned: false });
    const state = path.join(destination, "python", ".market_os", "portfolio.json");
    await writeJson(state, { preserved: true });
    const result = await installPortable({ artifactRoot: second, destination, requireSigned: false });
    assert.equal(result.version, "0.1.0-test.2");
    assert.equal(result.storage.preserved, true);
    assert.equal(result.rollback.available, true);
    assert.equal((await fsp.stat(`${destination}.rollback`)).isDirectory(), true);
    assert.deepEqual(JSON.parse(await fsp.readFile(state, "utf8")), { preserved: true });
  } finally {
    await fsp.rm(first, { recursive: true, force: true });
    await fsp.rm(second, { recursive: true, force: true });
    await fsp.rm(path.dirname(destination), { recursive: true, force: true });
  }
});

test("portable installer requires a signed artifact by default", async () => {
  const root = await makeArtifact("0.1.0-test.1");
  const destination = path.join(await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-u6-4-f-signed-")), "app");
  try {
    await assert.rejects(installPortable({ artifactRoot: root, destination }), /release-signature\.json/);
  } finally {
    await fsp.rm(root, { recursive: true, force: true });
    await fsp.rm(path.dirname(destination), { recursive: true, force: true });
  }
});

test("portable installer leaves the current app intact when source verification fails", async () => {
  const first = await makeArtifact("0.1.0-test.4");
  const invalid = await makeArtifact("0.1.0-test.5");
  const destination = path.join(await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-u6-4-f-recovery-")), "app");
  try {
    await installPortable({ artifactRoot: first, destination, requireSigned: false });
    const manifestPath = path.join(invalid, "artifact-manifest.json");
    const manifest = JSON.parse(await fsp.readFile(manifestPath, "utf8"));
    manifest.version = "tampered";
    await fsp.writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
    await assert.rejects(installPortable({ artifactRoot: invalid, destination, requireSigned: false }), /manifest SHA-256 mismatch/);
    const current = JSON.parse(await fsp.readFile(path.join(destination, "artifact-manifest.json"), "utf8"));
    assert.equal(current.version, "0.1.0-test.4");
    assert.equal(await fsp.stat(`${destination}.rollback`).then(() => false).catch(() => true), true);
  } finally {
    await fsp.rm(first, { recursive: true, force: true });
    await fsp.rm(invalid, { recursive: true, force: true });
    await fsp.rm(path.dirname(destination), { recursive: true, force: true });
  }
});

test("portable installer keeps the platform default per-user destination stable", () => {
  const destination = defaultDestination();
  assert.match(destination, process.platform === "win32" ? /Market OS$/ : /market-os$/);
});

test("portable uninstall removes the app and retains mutable state for reinstall", async () => {
  const root = await makeArtifact("0.1.0-test.3");
  const destination = path.join(await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-u6-4-f-uninstall-")), "app");
  try {
    await installPortable({ artifactRoot: root, destination, requireSigned: false });
    const state = path.join(destination, "python", ".market_os", "portfolio.json");
    await writeJson(state, { retained: true });
    const report = await uninstallPortable({ destination });
    assert.equal(report.application_removed, true);
    assert.equal(report.retained_data.preserved, true);
    assert.equal((await fsp.stat(`${destination}.data/python/.market_os/portfolio.json`)).isFile(), true);
    await installPortable({ artifactRoot: root, destination, requireSigned: false });
    assert.deepEqual(JSON.parse(await fsp.readFile(state, "utf8")), { retained: true });
  } finally {
    await fsp.rm(root, { recursive: true, force: true });
    await fsp.rm(path.dirname(destination), { recursive: true, force: true });
    await fsp.rm(`${destination}.data`, { recursive: true, force: true });
  }
});
