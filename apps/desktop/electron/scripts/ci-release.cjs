"use strict";

const crypto = require("node:crypto");
const fsp = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");

const ELECTRON_ROOT = path.resolve(__dirname, "..");

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = {
    target: process.platform === "win32" ? "windows-x64" : "linux-x64",
    output: path.resolve(ELECTRON_ROOT, "../../../output/u6.4-ci"),
  };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--") continue;
    if (value === "--target") options.target = argv[++index];
    else if (value === "--output") options.output = argv[++index];
    else if (value === "--help" || value === "-h") {
      console.log("Usage: node scripts/ci-release.cjs [--target windows-x64|linux-x64] [--output <dir>]");
      process.exit(0);
    } else fail(`unknown argument: ${value}`);
  }
  if (!["windows-x64", "linux-x64"].includes(options.target)) fail(`unsupported target: ${options.target}`);
  return { ...options, output: path.resolve(options.output) };
}

function run(script, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [path.join(__dirname, script), ...args], {
      cwd: ELECTRON_ROOT,
      stdio: "inherit",
      windowsHide: true,
    });
    child.once("error", reject);
    child.once("exit", (code, signal) => {
      if (code === 0) resolve();
      else reject(new Error(`${script} failed with ${signal || `exit ${code}`}`));
    });
  });
}

async function readJson(file) {
  return JSON.parse(await fsp.readFile(file, "utf8"));
}

async function writeJson(file, value) {
  await fsp.mkdir(path.dirname(file), { recursive: true });
  await fsp.writeFile(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function assertBoundary(manifest) {
  const expected = {
    loopback_only: true,
    synthetic: true,
    paper_only: true,
    read_only: true,
    credentials: false,
    provider_requests: 0,
    mutation_routes: false,
    live_trading: false,
  };
  const observed = manifest.runtime_boundary || {};
  for (const [key, value] of Object.entries(expected)) {
    if (observed[key] !== value) fail(`runtime boundary ${key} is unsafe`);
  }
  if (manifest.sidecar?.root !== "python" || manifest.sidecar?.distribution !== "target-native-source") {
    fail("Python sidecar is not target-native and isolated under python/");
  }
  if (manifest.storage?.root !== "python/.market_os" || manifest.storage?.scope !== "artifact-local" || manifest.storage?.shared_host_root !== false) {
    fail("artifact storage is not isolated under python/.market_os");
  }
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const expectedPlatform = options.target === "windows-x64" ? "win32" : "linux";
  if (process.platform !== expectedPlatform) fail(`target ${options.target} must build on ${expectedPlatform}; current host is ${process.platform}`);
  await fsp.rm(options.output, { recursive: true, force: true });
  await fsp.mkdir(options.output, { recursive: true });

  const releaseBase = process.env.GITHUB_RUN_NUMBER || process.env.MARKET_OS_CI_VERSION || String(Date.now());
  const knownGoodVersion = `0.1.0-ci.${releaseBase}.1`;
  const candidateVersion = `0.1.0-ci.${releaseBase}.2`;
  const knownGood = path.join(options.output, "artifact-known-good");
  const candidate = path.join(options.output, "artifact-candidate");
  const keyRoot = await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-u6-4-key-"));
  const privateKey = path.join(keyRoot, "release-private.pem");
  const keyPair = crypto.generateKeyPairSync("ed25519");
  await fsp.writeFile(privateKey, keyPair.privateKey.export({ format: "pem", type: "pkcs8" }), { mode: 0o600 });

  try {
    for (const [version, artifact] of [[knownGoodVersion, knownGood], [candidateVersion, candidate]]) {
      await run("package.cjs", ["--target", options.target, "--version", version, "--output", artifact]);
      const manifest = await readJson(path.join(artifact, "artifact-manifest.json"));
      if (manifest.version !== version || manifest.target !== options.target || manifest.platform?.os !== options.target.split("-")[0]) {
        fail(`artifact manifest does not match ${options.target}/${version}`);
      }
      assertBoundary(manifest);
      await run("sign-artifact.cjs", ["--artifact", artifact, "--private-key", privateKey]);
      await run("smoke-artifact.cjs", ["--artifact", artifact, "--expect-signed", "--report", path.join(options.output, `smoke-${version}.json`)]);
    }

    const drillReport = path.join(options.output, "release-drill.json");
    await run("release-drill.cjs", ["--candidate", candidate, "--known-good", knownGood, "--report", drillReport]);
    const smokeReports = await Promise.all([
      readJson(path.join(options.output, `smoke-${knownGoodVersion}.json`)),
      readJson(path.join(options.output, `smoke-${candidateVersion}.json`)),
    ]);
    const drill = await readJson(drillReport);
    const candidateManifest = await readJson(path.join(candidate, "artifact-manifest.json"));
    const evidence = {
      schema: "market-os.u6.4-ci-evidence@v1",
      milestone: "U6.4-C",
      status: "passed",
      target: options.target,
      host: { platform: process.platform, arch: process.arch, node: process.version },
      artifacts: {
        known_good: { version: knownGoodVersion, path: path.relative(process.cwd(), knownGood), manifest: "artifact-manifest.json", signature: "release-signature.json" },
        candidate: { version: candidateVersion, path: path.relative(process.cwd(), candidate), manifest: "artifact-manifest.json", signature: "release-signature.json" },
      },
      checks: {
        target_native_build: true,
        signed_smoke: smokeReports.map((report) => ({
          version: report.version,
          readyz_status: report.checks.readyz_status,
          healthz_status: report.checks.healthz_status,
          overview_status: report.checks.overview_status,
          runtime_status: report.checks.runtime_status,
          boundary: report.checks.boundary,
          api_closed: report.cleanup.api_closed,
          next_closed: report.cleanup.next_closed,
        })),
        promotion_rollback: drill.checks,
      },
      evidence_files: [
        "artifact-known-good/artifact-manifest.json",
        "artifact-known-good/release-signature.json",
        "artifact-candidate/artifact-manifest.json",
        "artifact-candidate/release-signature.json",
        `smoke-${knownGoodVersion}.json`,
        `smoke-${candidateVersion}.json`,
        "release-drill.json",
      ],
      boundary: {
        values: candidateManifest.runtime_boundary,
        checks: drill.checks.boundary,
      },
    };
    await writeJson(path.join(options.output, "ci-evidence.json"), evidence);
    console.log(JSON.stringify(evidence, null, 2));
  } finally {
    await fsp.rm(keyRoot, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});

module.exports = { assertBoundary, parseArgs };
