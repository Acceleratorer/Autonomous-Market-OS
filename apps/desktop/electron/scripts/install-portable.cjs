"use strict";

const fsp = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { inspectInstallPreflight, isInside } = require("./install-preflight.cjs");
const { copyArtifact, digestTree } = require("./install-simulate.cjs");
const { validateRuntimeManifest } = require("./python-runtime.cjs");
const { verifyArtifact, sha256File } = require("../src/release.cjs");

const SCHEMA = "market-os.u6.4-installation-result@v1";
const MUTABLE_STORAGE = "python/.market_os";
const ROLLBACK_SUFFIX = ".rollback";
const RETAINED_DATA_SUFFIX = ".data";

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = { artifact: null, destination: null, json: null, markdown: null };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--") continue;
    if (value === "--artifact") options.artifact = argv[++index];
    else if (value === "--destination") options.destination = argv[++index];
    else if (value === "--json") options.json = argv[++index];
    else if (value === "--markdown") options.markdown = argv[++index];
    else if (value === "--help" || value === "-h") {
      console.log("Usage: node scripts/install-portable.cjs --artifact <dir> [--destination <dir>] [--json <file>] [--markdown <file>]");
      process.exit(0);
    } else fail(`unknown argument: ${value}`);
  }
  if (!options.artifact) fail("--artifact is required");
  return {
    ...options,
    artifact: path.resolve(options.artifact),
    destination: options.destination ? path.resolve(options.destination) : null,
    json: options.json ? path.resolve(options.json) : null,
    markdown: options.markdown ? path.resolve(options.markdown) : null,
  };
}

function defaultDestination() {
  if (process.platform === "win32") {
    return path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local"), "Market OS");
  }
  return path.join(process.env.XDG_DATA_HOME || path.join(os.homedir(), ".local", "share"), "market-os");
}

async function exists(file) {
  try {
    await fsp.lstat(file);
    return true;
  } catch (error) {
    if (error?.code === "ENOENT") return false;
    throw error;
  }
}

async function readJson(file, label) {
  try {
    return JSON.parse(await fsp.readFile(file, "utf8"));
  } catch (error) {
    fail(`${label} is unreadable: ${error instanceof Error ? error.message : String(error)}`);
  }
}

async function embeddedRuntimeIdentity(root, manifest) {
  if (manifest.sidecar?.distribution !== "target-native-embedded-cpython" || !manifest.runtime) {
    fail("portable installation requires an embedded CPython artifact");
  }
  const runtimeManifestPath = path.join(root, manifest.runtime.manifest);
  const runtimeManifest = await readJson(runtimeManifestPath, "embedded Python runtime manifest");
  const runtime = validateRuntimeManifest(runtimeManifest, { target: manifest.target });
  const runtimeManifestSha256 = await sha256File(runtimeManifestPath);
  if (manifest.runtime.manifest_sha256 !== runtimeManifestSha256) fail("embedded Python runtime manifest hash does not match artifact manifest");
  const runtimeTree = await digestTree(path.join(root, manifest.runtime.root), { excludeRelative: "runtime-manifest.json" });
  if (runtimeTree.sha256 !== manifest.runtime.tree_sha256) {
    fail(`embedded Python runtime tree hash does not match artifact manifest: expected ${manifest.runtime.tree_sha256}, got ${runtimeTree.sha256}`);
  }
  return {
    schema: runtime.schema,
    distribution: runtime.distribution,
    version: runtime.version,
    target: runtime.target,
    source: runtime.source,
    source_url: runtime.source_url,
    archive_sha256: runtime.archive_sha256,
    manifest_sha256: runtimeManifestSha256,
    tree_sha256: runtimeTree.sha256,
    interpreter: manifest.runtime.interpreter,
    dependencies: runtime.dependencies,
  };
}

async function preserveStorage(source, staging) {
  const sourceStorage = path.join(source, MUTABLE_STORAGE);
  if (!await exists(sourceStorage)) return false;
  const destinationStorage = path.join(staging, MUTABLE_STORAGE);
  await fsp.cp(sourceStorage, destinationStorage, {
    recursive: true,
    force: true,
    errorOnExist: false,
    dereference: false,
    verbatimSymlinks: true,
  });
  return true;
}

async function preserveRetainedData(retainedRoot, staging) {
  const sourceStorage = path.join(retainedRoot, MUTABLE_STORAGE);
  if (!await exists(sourceStorage)) return false;
  const destinationStorage = path.join(staging, MUTABLE_STORAGE);
  await fsp.cp(sourceStorage, destinationStorage, {
    recursive: true,
    force: true,
    errorOnExist: false,
    dereference: false,
    verbatimSymlinks: true,
  });
  return true;
}

async function isInstalledDestination(target) {
  try {
    const manifest = await readJson(path.join(target, "artifact-manifest.json"), "existing destination manifest");
    return manifest.schema === "market-os.u6.4-artifact@v1"
      && await exists(path.join(target, "slots", "current.json"))
      && await exists(path.join(target, "slots", "known-good.json"));
  } catch {
    return false;
  }
}

function renderMarkdown(report) {
  const checks = Object.entries(report.checks).map(([key, value]) => `| ${key} | ${value ? "PASS" : "FAIL"} |`).join("\n");
  const boundary = Object.entries(report.boundary).map(([key, value]) => `| ${key} | ${String(value)} |`).join("\n");
  return [
    "# U6.4-F Portable Installation",
    "",
    `- Status: **${report.status.toUpperCase()}**`,
    `- Scope: **${report.scope}**`,
    `- Target: \`${report.target}\``,
    `- Version: \`${report.version}\``,
    `- Destination: \`${report.destination}\``,
    `- Source manifest: \`${report.source_manifest_sha256}\``,
    `- Destination manifest: \`${report.destination_manifest_sha256}\``,
    "",
    "The installer verifies a signed embedded-CPython artifact, publishes through a staging directory and one rename, preserves mutable state on upgrade, and leaves the previous install as a manual rollback copy. It does not register a service.",
    "",
    "## Checks",
    "",
    "| Check | Result |",
    "| --- | --- |",
    checks,
    "",
    "## Runtime",
    "",
    `- CPython: \`${report.runtime.version}\` from \`${report.runtime.source}\``,
    `- Runtime tree: \`${report.runtime.tree_sha256}\``,
    `- Archive SHA-256: \`${report.runtime.archive_sha256}\``,
    "",
    "## Rollback and state",
    "",
    `- Manual rollback copy: \`${report.rollback.path || "none (first install)"}\``,
    `- Mutable state preserved: **${report.storage.preserved}**`,
    `- Service registration: **${report.launch.service_registered}**`,
    "",
    "## Boundary",
    "",
    "| Field | Value |",
    "| --- | --- |",
    boundary,
    "",
  ].join("\n");
}

async function installPortable({ artifactRoot, destination = null, requireSigned = true } = {}) {
  if (!artifactRoot) fail("artifactRoot is required");
  const source = path.resolve(artifactRoot);
  const target = path.resolve(destination || defaultDestination());
  if (isInside(source, target) || isInside(target, source)) fail("destination must be separate from artifact source");

  const sourcePreflight = await inspectInstallPreflight({ artifactRoot: source, destination: target, requireSigned });
  const sourceVerification = await verifyArtifact(source, { requireSignature: requireSigned });
  const sourceRuntime = await embeddedRuntimeIdentity(source, sourceVerification.manifest);
  const sourceTree = await digestTree(source);
  const rollback = `${target}${ROLLBACK_SUFFIX}`;
  const retainedData = `${target}${RETAINED_DATA_SUFFIX}`;
  const hadExisting = await exists(target);
  if (await exists(rollback)) fail("manual rollback path already exists; resolve it before upgrading");
  if (hadExisting && !await isInstalledDestination(target)) {
    fail("destination already exists and is not an installed Market OS artifact");
  }

  const parent = path.dirname(target);
  await fsp.mkdir(parent, { recursive: true });
  const staging = await fsp.mkdtemp(path.join(parent, ".market-os-install-stage-"));
  let movedExisting = false;
  let published = false;
  try {
    await copyArtifact(source, staging);
    const preserved = hadExisting
      ? await preserveStorage(target, staging)
      : await preserveRetainedData(retainedData, staging);
    const stagedPreflight = await inspectInstallPreflight({ artifactRoot: staging, destination: source, requireSigned });
    const stagedVerification = await verifyArtifact(staging, { requireSignature: requireSigned });
    const stagedRuntime = await embeddedRuntimeIdentity(staging, stagedVerification.manifest);
    const stagedTree = await digestTree(staging);
    if (stagedTree.sha256 !== sourceTree.sha256) fail("staged artifact tree does not match source artifact");
    if (stagedRuntime.tree_sha256 !== sourceRuntime.tree_sha256) fail("staged Python runtime does not match source artifact");

    if (hadExisting) {
      await fsp.rename(target, rollback);
      movedExisting = true;
    }
    await fsp.rename(staging, target);
    published = true;
    const destinationPreflight = await inspectInstallPreflight({ artifactRoot: target, destination: source, requireSigned });
    const destinationVerification = await verifyArtifact(target, { requireSignature: requireSigned });
    const destinationRuntime = await embeddedRuntimeIdentity(target, destinationVerification.manifest);
    const destinationTree = await digestTree(target);
    if (destinationVerification.manifestSha256 !== sourceVerification.manifestSha256) fail("destination manifest hash does not match source artifact");
    if (destinationTree.sha256 !== sourceTree.sha256) fail("destination artifact tree does not match source artifact");
    if (destinationRuntime.tree_sha256 !== sourceRuntime.tree_sha256) fail("destination Python runtime does not match source artifact");

    return {
      schema: SCHEMA,
      status: "passed",
      package_format: "portable-tar-gz-extracted-directory",
      scope: "per-user",
      elevation: false,
      target: destinationPreflight.target,
      version: destinationPreflight.version,
      source_manifest_sha256: sourceVerification.manifestSha256,
      destination_manifest_sha256: destinationVerification.manifestSha256,
      source_tree_sha256: sourceTree.sha256,
      destination_tree_sha256: destinationTree.sha256,
      destination: target,
      runtime: destinationRuntime,
      storage: { root: MUTABLE_STORAGE, preserved, reset: !preserved },
      rollback: { available: movedExisting, path: movedExisting ? rollback : null, mode: "manual" },
      launch: { mode: "manual", service_registered: false },
      checks: {
        signed_artifact: sourceVerification.signatureStatus === "verified",
        embedded_python: true,
        staged_tree_match: true,
        destination_tree_match: true,
        mutable_state_preserved: preserved || !hadExisting,
        manual_rollback_recorded: true,
        service_registration_disabled: true,
      },
      boundary: destinationPreflight.boundary,
      deferred: ["native service installation", "credentials", "providers", "mutation routes", "live execution"],
    };
  } catch (error) {
    if (published) await fsp.rm(target, { recursive: true, force: true });
    else await fsp.rm(staging, { recursive: true, force: true });
    if (movedExisting && await exists(rollback) && !await exists(target)) await fsp.rename(rollback, target);
    throw error;
  }
}

async function uninstallPortable({ destination } = {}) {
  if (!destination) fail("destination is required");
  const target = path.resolve(destination);
  if (!await exists(target)) fail("installed application is missing");
  const retainedData = `${target}${RETAINED_DATA_SUFFIX}`;
  if (await exists(retainedData)) fail("retained data path already exists; resolve it before uninstalling");
  const sourceStorage = path.join(target, MUTABLE_STORAGE);
  const retainedStorage = path.join(retainedData, MUTABLE_STORAGE);
  const hasState = await exists(sourceStorage);
  if (hasState) {
    await fsp.mkdir(path.dirname(retainedStorage), { recursive: true });
    await fsp.rename(sourceStorage, retainedStorage);
  }
  try {
    await fsp.rm(target, { recursive: true, force: false });
  } catch (error) {
    if (hasState && !await exists(sourceStorage) && await exists(retainedStorage)) {
      await fsp.mkdir(path.dirname(sourceStorage), { recursive: true });
      await fsp.rename(retainedStorage, sourceStorage);
      await fsp.rm(retainedData, { recursive: true, force: true });
    }
    throw error;
  }
  return {
    schema: SCHEMA,
    status: "passed",
    scope: "per-user",
    destination: target,
    application_removed: true,
    retained_data: { path: hasState ? retainedData : null, preserved: hasState, removal_required: hasState },
    launch: { service_registered: false },
    deferred: ["native service installation", "credentials", "providers", "mutation routes", "live execution"],
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
  const report = await installPortable({ artifactRoot: options.artifact, destination: options.destination, requireSigned: true });
  await writeReport(options, report);
  console.log(JSON.stringify(report, null, 2));
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}

module.exports = { defaultDestination, installPortable, uninstallPortable, parseArgs, renderMarkdown };
