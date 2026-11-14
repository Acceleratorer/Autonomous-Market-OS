"use strict";

const crypto = require("node:crypto");
const fsp = require("node:fs/promises");
const fs = require("node:fs");
const path = require("node:path");
const { inspectInstallPreflight, isInside } = require("./install-preflight.cjs");
const { verifyArtifact } = require("../src/release.cjs");

const SCHEMA = "market-os.u6.4-install-simulation@v1";
const MUTABLE_STORAGE = "python/.market_os";

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = { artifact: null, destination: null, json: null, markdown: null, allowUnsigned: false };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--") continue;
    if (value === "--artifact") options.artifact = argv[++index];
    else if (value === "--destination") options.destination = argv[++index];
    else if (value === "--json") options.json = argv[++index];
    else if (value === "--markdown") options.markdown = argv[++index];
    else if (value === "--allow-unsigned") options.allowUnsigned = true;
    else if (value === "--help" || value === "-h") {
      console.log("Usage: node scripts/install-simulate.cjs --artifact <dir> --destination <dir> [--allow-unsigned] [--json <file>] [--markdown <file>]");
      process.exit(0);
    } else fail(`unknown argument: ${value}`);
  }
  if (!options.artifact) fail("--artifact is required");
  if (!options.destination) fail("--destination is required");
  return {
    ...options,
    artifact: path.resolve(options.artifact),
    destination: path.resolve(options.destination),
    json: options.json ? path.resolve(options.json) : null,
    markdown: options.markdown ? path.resolve(options.markdown) : null,
  };
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

function relativePosix(root, candidate) {
  return path.relative(root, candidate).split(path.sep).join("/");
}

function isMutableStorage(relative) {
  return relative === MUTABLE_STORAGE || relative.startsWith(`${MUTABLE_STORAGE}/`);
}

async function sha256File(file) {
  const hash = crypto.createHash("sha256");
  const stream = fs.createReadStream(file);
  for await (const chunk of stream) hash.update(chunk);
  return hash.digest("hex");
}

async function digestTree(root) {
  const entries = [];
  const stack = [path.resolve(root)];
  while (stack.length) {
    const current = stack.pop();
    const relative = relativePosix(root, current);
    if (relative && isMutableStorage(relative)) continue;
    const stat = await fsp.lstat(current);
    if (stat.isSymbolicLink()) {
      entries.push(`${relative}\0symlink\0${await fsp.readlink(current)}\n`);
      continue;
    }
    if (stat.isDirectory()) {
      const children = await fsp.readdir(current);
      for (const child of children.sort().reverse()) stack.push(path.join(current, child));
      continue;
    }
    if (!stat.isFile()) fail(`unsupported artifact entry: ${relative}`);
    entries.push(`${relative}\0file\0${stat.size}\0${await sha256File(current)}\n`);
  }
  entries.sort();
  return crypto.createHash("sha256").update(entries.join(""), "utf8").digest("hex");
}

async function copyArtifact(source, staging) {
  await fsp.cp(source, staging, {
    recursive: true,
    force: false,
    errorOnExist: false,
    dereference: false,
    verbatimSymlinks: true,
    filter: (candidate) => !isMutableStorage(relativePosix(source, candidate)),
  });
  await fsp.mkdir(path.join(staging, MUTABLE_STORAGE.replaceAll("/", path.sep)), { recursive: true });
}

async function storageIsEmpty(root) {
  const storage = path.join(root, MUTABLE_STORAGE.replaceAll("/", path.sep));
  return (await fsp.readdir(storage)).length === 0;
}

function renderMarkdown(report) {
  const checks = Object.entries(report.checks).map(([key, value]) => `| ${key} | ${value ? "PASS" : "FAIL"} |`).join("\n");
  const boundary = Object.entries(report.boundary).map(([key, value]) => `| ${key} | ${String(value)} |`).join("\n");
  return [
    "# U6.4-E Offline Install Simulation",
    "",
    `- Status: **${report.status.toUpperCase()}**`,
    `- Target: \`${report.target}\``,
    `- Version: \`${report.version}\``,
    `- Signature: **${report.signature_status}**`,
    `- Source manifest: \`${report.source_manifest_sha256}\``,
    `- Destination manifest: \`${report.destination_manifest_sha256}\``,
    `- Artifact tree: \`${report.source_tree_sha256}\``,
    "",
    "The simulation publishes a verified artifact through a separate staging directory and resets artifact-local mutable storage. It does not install a service, embed Python, or change release slots.",
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
    "Deferred: embedded Python runtime, native service installation, credentials, providers, mutation routes, live execution, and U5.5 owner-VM promotion.",
    "",
  ].join("\n");
}

async function simulateInstall({ artifactRoot, destination, requireSigned = true } = {}) {
  if (!artifactRoot) fail("artifactRoot is required");
  if (!destination) fail("destination is required");
  const source = path.resolve(artifactRoot);
  const target = path.resolve(destination);
  if (isInside(source, target) || isInside(target, source)) fail("destination must be separate from artifact source");
  if (await exists(target)) fail("destination already exists");

  const sourcePreflight = await inspectInstallPreflight({ artifactRoot: source, destination: target, requireSigned });
  const sourceVerification = await verifyArtifact(source, { requireSignature: requireSigned });
  const sourceTreeSha256 = await digestTree(source);
  const parent = path.dirname(target);
  await fsp.mkdir(parent, { recursive: true });
  const staging = await fsp.mkdtemp(path.join(parent, ".market-os-install-stage-"));
  let published = false;
  try {
    await copyArtifact(source, staging);
    const stagedPreflight = await inspectInstallPreflight({ artifactRoot: staging, destination: source, requireSigned });
    const stagedTreeSha256 = await digestTree(staging);
    if (stagedTreeSha256 !== sourceTreeSha256) fail("staged artifact tree does not match source artifact");
    await fsp.rename(staging, target);
    published = true;
    const destinationPreflight = await inspectInstallPreflight({ artifactRoot: target, destination: source, requireSigned });
    const destinationVerification = await verifyArtifact(target, { requireSignature: requireSigned });
    const destinationTreeSha256 = await digestTree(target);
    const sourceAfter = await verifyArtifact(source, { requireSignature: requireSigned });
    const mutableStorageReset = await storageIsEmpty(target);
    if (destinationVerification.manifestSha256 !== sourceVerification.manifestSha256) fail("destination manifest hash does not match source artifact");
    if (destinationTreeSha256 !== sourceTreeSha256) fail("destination artifact tree does not match source artifact");
    if (sourceAfter.manifestSha256 !== sourceVerification.manifestSha256) fail("source artifact changed during install simulation");
    if (!mutableStorageReset) fail("destination mutable storage was not reset");

    return {
      schema: SCHEMA,
      status: "passed",
      target: destinationPreflight.target,
      version: destinationPreflight.version,
      source_manifest_sha256: sourceVerification.manifestSha256,
      destination_manifest_sha256: destinationVerification.manifestSha256,
      source_tree_sha256: sourceTreeSha256,
      destination_tree_sha256: destinationTreeSha256,
      signature_status: destinationVerification.signatureStatus,
      source: path.relative(process.cwd(), source),
      destination: path.relative(process.cwd(), target),
      checks: {
        source_preflight: sourcePreflight.status === "passed",
        staged_preflight: stagedPreflight.status === "passed",
        destination_preflight: destinationPreflight.status === "passed",
        destination_separate: true,
        staged_tree_matches_source: stagedTreeSha256 === sourceTreeSha256,
        destination_tree_matches_source: destinationTreeSha256 === sourceTreeSha256,
        destination_manifest_matches_source: destinationVerification.manifestSha256 === sourceVerification.manifestSha256,
        source_unchanged: sourceAfter.manifestSha256 === sourceVerification.manifestSha256,
        mutable_storage_reset: mutableStorageReset,
        staging_clean: !(await exists(staging)),
        boundary: destinationPreflight.checks.runtime_boundary === true,
      },
      boundary: destinationPreflight.boundary,
      simulation: {
        performed: true,
        atomic_publish: true,
        embedded_python: false,
        native_service: false,
        release_slots_changed: false,
      },
      deferred: ["embedded Python runtime", "native service installation", "credentials", "providers", "mutation routes", "live execution", "U5.5 owner-VM promotion"],
    };
  } catch (error) {
    if (published) await fsp.rm(target, { recursive: true, force: true });
    else await fsp.rm(staging, { recursive: true, force: true });
    throw error;
  }
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
  const report = await simulateInstall({ artifactRoot: options.artifact, destination: options.destination, requireSigned: !options.allowUnsigned });
  await writeReport(options, report);
  console.log(JSON.stringify(report, null, 2));
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}

module.exports = { copyArtifact, digestTree, parseArgs, renderMarkdown, simulateInstall, storageIsEmpty };
