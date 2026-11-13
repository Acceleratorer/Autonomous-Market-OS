"use strict";

const crypto = require("node:crypto");
const fsp = require("node:fs/promises");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { verifyArtifact, readSlot } = require("../src/release.cjs");

const SCHEMA = "market-os.u6.4-install-preflight@v1";
const TARGETS = new Set(["windows-x64", "linux-x64"]);

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = { artifact: null, destination: null, target: null, json: null, markdown: null, requireSigned: false };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--") continue;
    if (value === "--artifact") options.artifact = argv[++index];
    else if (value === "--destination") options.destination = argv[++index];
    else if (value === "--target") options.target = argv[++index];
    else if (value === "--json") options.json = argv[++index];
    else if (value === "--markdown") options.markdown = argv[++index];
    else if (value === "--require-signed") options.requireSigned = true;
    else if (value === "--help" || value === "-h") {
      console.log("Usage: node scripts/install-preflight.cjs --artifact <dir> [--destination <dir>] [--target windows-x64|linux-x64] [--require-signed] [--json <file>] [--markdown <file>]");
      process.exit(0);
    } else fail(`unknown argument: ${value}`);
  }
  if (!options.artifact) fail("--artifact is required");
  if (options.target !== null && !TARGETS.has(options.target)) fail(`unsupported target: ${options.target}`);
  if (options.destination !== null && !options.destination) fail("--destination must not be empty");
  return {
    ...options,
    artifact: path.resolve(options.artifact),
    destination: options.destination ? path.resolve(options.destination) : null,
    json: options.json ? path.resolve(options.json) : null,
    markdown: options.markdown ? path.resolve(options.markdown) : null,
  };
}

async function readJson(file, label) {
  try {
    return JSON.parse(await fsp.readFile(file, "utf8"));
  } catch (error) {
    fail(`${label} is unreadable: ${error instanceof Error ? error.message : String(error)}`);
  }
}

function isInside(root, candidate) {
  const relative = path.relative(path.resolve(root), path.resolve(candidate));
  return relative === "" || (!relative.startsWith(`..${path.sep}`) && relative !== ".." && !path.isAbsolute(relative));
}

function expectedHostTarget() {
  if (process.platform === "win32" && process.arch === "x64") return "windows-x64";
  if (process.platform === "linux" && process.arch === "x64") return "linux-x64";
  return null;
}

async function assertFile(root, relative, label, executable = false) {
  const file = path.resolve(root, relative);
  if (!isInside(root, file)) fail(`${label} escapes artifact root`);
  let stat;
  try {
    stat = await fsp.stat(file);
  } catch {
    fail(`${label} is missing`);
  }
  if (!stat.isFile()) fail(`${label} is not a file`);
  if (executable && process.platform !== "win32") {
    try {
      await fsp.access(file, fs.constants.X_OK);
    } catch {
      fail(`${label} is not executable`);
    }
  }
  return file;
}

function assertBoundary(boundary) {
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
  for (const [key, value] of Object.entries(expected)) {
    if (boundary?.[key] !== value) fail(`runtime boundary ${key} is unsafe`);
  }
}

function stableFingerprint(value) {
  return crypto.createHash("sha256").update(JSON.stringify(value), "utf8").digest("hex");
}

function renderMarkdown(report) {
  const checks = Object.entries(report.checks).map(([key, value]) => `| ${key} | ${value ? "PASS" : "FAIL"} |`).join("\n");
  const boundary = Object.entries(report.boundary).map(([key, value]) => `| ${key} | ${String(value)} |`).join("\n");
  return [
    "# U6.4-D Installer Preflight",
    "",
    `- Status: **${report.status.toUpperCase()}**`,
    `- Target: \`${report.target}\``,
    `- Version: \`${report.version}\``,
    `- Signature: **${report.signature_status}**`,
    `- Preflight fingerprint: \`${report.preflight_fingerprint}\``,
    "",
    "The preflight validates an unpacked target-native artifact without installing a service, embedding Python, changing release slots, or changing the execution boundary.",
    "",
    "## Checks",
    "",
    "| Check | Result |",
    "| --- | --- |",
    checks,
    "",
    "## Boundary",
    "",
    "| Field | Value |",
    "| --- | --- |",
    boundary,
    "",
    "## Installation actions",
    "",
    `- performed: **${report.installation.performed}**`,
    `- embedded_python: **${report.installation.embedded_python}**`,
    `- native_service: **${report.installation.native_service}**`,
    `- destination: \`${report.installation.destination || "not supplied"}\``,
    "",
    "Deferred: embedded Python runtime, native service installation, credentials, providers, mutation routes, and live execution.",
    "",
  ].join("\n");
}

async function inspectInstallPreflight({ artifactRoot, destination = null, target = null, requireSigned = false } = {}) {
  if (!artifactRoot) fail("artifactRoot is required");
  const root = path.resolve(artifactRoot);
  const manifest = await readJson(path.join(root, "artifact-manifest.json"), "artifact manifest");
  const manifestVerification = await verifyArtifact(root, { requireSignature: requireSigned });
  const expectedTarget = target || manifest.target;
  if (!TARGETS.has(expectedTarget)) fail(`unsupported artifact target: ${expectedTarget}`);
  if (manifest.schema !== "market-os.u6.4-artifact@v1") fail("unexpected artifact manifest schema");
  if (manifest.status !== "unsigned-reproducible") fail("artifact is not marked unsigned-reproducible");
  if (manifest.target !== expectedTarget) fail("artifact target does not match requested target");
  if (expectedHostTarget() !== expectedTarget) fail(`target ${expectedTarget} must match host ${process.platform}/${process.arch}`);
  if (manifest.sidecar?.type !== "python-source" || manifest.sidecar?.distribution !== "target-native-source" || manifest.sidecar?.root !== "python") {
    fail("Python sidecar is not a target-native source package under python/");
  }
  if (!/^(python|python3)$/.test(manifest.sidecar?.interpreter || "") || manifest.sidecar?.requires_python !== ">=3.11") {
    fail("Python sidecar interpreter contract is unsafe");
  }
  if (manifest.storage?.root !== "python/.market_os" || manifest.storage?.scope !== "artifact-local" || manifest.storage?.shared_host_root !== false) {
    fail("artifact storage is not isolated under python/.market_os");
  }
  assertBoundary(manifest.runtime_boundary);

  const electronEntry = expectedTarget === "windows-x64" ? manifest.entrypoints?.electron_windows : manifest.entrypoints?.electron_linux;
  await assertFile(root, electronEntry, "target-native Electron binary", true);
  await assertFile(root, manifest.entrypoints?.shell, "Electron shell entrypoint");
  await assertFile(root, manifest.entrypoints?.next_cli, "Next.js entrypoint");
  await assertFile(root, manifest.entrypoints?.gateway, "Python gateway entrypoint");
  await assertFile(root, path.join(manifest.sidecar.root, "pyproject.toml"), "Python dependency manifest");
  const current = await readSlot(root, "current");
  const knownGood = await readSlot(root, "known-good");
  if (!current || !knownGood) fail("current and known-good slot metadata are required");

  const resolvedDestination = destination ? path.resolve(destination) : null;
  if (resolvedDestination && (isInside(root, resolvedDestination) || isInside(resolvedDestination, root))) {
    fail("destination must be separate from artifact source");
  }
  const checks = {
    manifest_schema: true,
    target_matches_host: true,
    signature_or_unsigned_state: !requireSigned || manifestVerification.verified === true,
    electron_binary: true,
    python_sidecar: true,
    storage_isolation: true,
    slot_metadata: true,
    runtime_boundary: true,
    destination_separate: true,
  };
  const boundary = { ...manifest.runtime_boundary };
  const stable = {
    schema: SCHEMA,
    target: expectedTarget,
    version: manifest.version,
    manifest_sha256: manifestVerification.manifestSha256,
    signature_status: manifestVerification.signatureStatus,
    checks,
    boundary,
    installation: { performed: false, embedded_python: false, native_service: false },
  };
  return {
    schema: SCHEMA,
    status: "passed",
    target: expectedTarget,
    version: manifest.version,
    artifact_manifest_sha256: manifestVerification.manifestSha256,
    signature_status: manifestVerification.signatureStatus,
    checks,
    boundary,
    installation: {
      performed: false,
      embedded_python: false,
      native_service: false,
      destination: resolvedDestination,
    },
    deferred: ["embedded Python runtime", "native service installation", "credentials", "providers", "mutation routes", "live execution"],
    preflight_fingerprint: stableFingerprint(stable),
  };
}

async function writeReport(options, report) {
  if (options.json) {
    await fsp.mkdir(path.dirname(options.json), { recursive: true });
    await fsp.writeFile(options.json, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  }
  if (options.markdown) {
    await fsp.mkdir(path.dirname(options.markdown), { recursive: true });
    await fsp.writeFile(options.markdown, renderMarkdown(report), "utf8");
  }
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const report = await inspectInstallPreflight({
    artifactRoot: options.artifact,
    destination: options.destination,
    target: options.target,
    requireSigned: options.requireSigned,
  });
  await writeReport(options, report);
  console.log(JSON.stringify(report, null, 2));
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}

module.exports = { assertBoundary, expectedHostTarget, inspectInstallPreflight, isInside, parseArgs, renderMarkdown };
