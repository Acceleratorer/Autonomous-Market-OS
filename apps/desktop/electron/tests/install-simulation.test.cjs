"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fsp = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { execFile } = require("node:child_process");
const { promisify } = require("node:util");
const test = require("node:test");

const { simulateInstall } = require("../scripts/install-simulate.cjs");

const execFileAsync = promisify(execFile);

async function writeJson(file, value) {
  await fsp.mkdir(path.dirname(file), { recursive: true });
  await fsp.writeFile(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

async function makeArtifact() {
  const root = await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-install-simulation-"));
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
    "python/.market_os/runs.jsonl",
  ];
  for (const relative of files) {
    const file = path.join(root, relative);
    await fsp.mkdir(path.dirname(file), { recursive: true });
    await fsp.writeFile(file, relative.endsWith("runs.jsonl") ? "mutable\n" : "fixture\n", {
      encoding: "utf8",
      mode: relative.endsWith(electronBinary) ? 0o755 : 0o644,
    });
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

async function signArtifact(root, privateKey) {
  await execFileAsync(process.execPath, [
    path.resolve(__dirname, "../scripts/sign-artifact.cjs"),
    "--artifact", root,
    "--private-key", privateKey,
  ]);
}

test("offline install simulation atomically publishes a signed artifact and resets mutable storage", async () => {
  const root = await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-install-simulation-case-"));
  const artifact = path.join(root, "artifact");
  const destination = path.join(root, "installed");
  const privateKey = path.join(root, "release-private.pem");
  await makeArtifact().then(async (fixture) => {
    await fsp.cp(fixture, artifact, { recursive: true, verbatimSymlinks: true });
    await fsp.rm(fixture, { recursive: true, force: true });
  });
  const keyPair = crypto.generateKeyPairSync("ed25519");
  await fsp.writeFile(privateKey, keyPair.privateKey.export({ format: "pem", type: "pkcs8" }));
  await signArtifact(artifact, privateKey);

  try {
    const report = await simulateInstall({ artifactRoot: artifact, destination });
    assert.equal(report.status, "passed");
    assert.equal(report.signature_status, "verified");
    assert.equal(report.simulation.performed, true);
    assert.equal(report.simulation.atomic_publish, true);
    assert.equal(report.simulation.embedded_python, false);
    assert.equal(report.simulation.native_service, false);
    assert.ok(Object.values(report.checks).every(Boolean));
    assert.equal((await fsp.readdir(path.join(destination, "python", ".market_os"))).length, 0);
    assert.equal(await fsp.readFile(path.join(artifact, "python", ".market_os", "runs.jsonl"), "utf8"), "mutable\n");
  } finally {
    await fsp.rm(root, { recursive: true, force: true });
  }
});

test("offline install simulation rejects a destination nested inside the source", async () => {
  const artifact = await makeArtifact();
  try {
    await assert.rejects(
      simulateInstall({ artifactRoot: artifact, destination: path.join(artifact, "installed") }),
      /destination must be separate from artifact source/,
    );
  } finally {
    await fsp.rm(artifact, { recursive: true, force: true });
  }
});

test("offline install simulation rejects an existing destination without overwriting it", async () => {
  const root = await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-install-simulation-existing-"));
  const artifact = await makeArtifact();
  const destination = path.join(root, "installed");
  await fsp.mkdir(destination, { recursive: true });
  await fsp.writeFile(path.join(destination, "keep.txt"), "keep\n", "utf8");
  try {
    await assert.rejects(simulateInstall({ artifactRoot: artifact, destination }), /destination already exists/);
    assert.equal(await fsp.readFile(path.join(destination, "keep.txt"), "utf8"), "keep\n");
  } finally {
    await fsp.rm(root, { recursive: true, force: true });
    await fsp.rm(artifact, { recursive: true, force: true });
  }
});

test("offline install simulation rejects unsigned artifacts by default", async () => {
  const root = await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-install-simulation-unsigned-"));
  const artifact = await makeArtifact();
  try {
    await assert.rejects(simulateInstall({ artifactRoot: artifact, destination: path.join(root, "installed") }), /artifact has no release-signature.json/);
  } finally {
    await fsp.rm(root, { recursive: true, force: true });
    await fsp.rm(artifact, { recursive: true, force: true });
  }
});
