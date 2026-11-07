"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const fsp = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { verifyArtifact } = require("../src/release.cjs");

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = { artifact: null, output: null, report: null };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--") continue;
    if (value === "--artifact") options.artifact = argv[++index];
    else if (value === "--output") options.output = argv[++index];
    else if (value === "--report") options.report = argv[++index];
    else if (value === "--help" || value === "-h") {
      console.log("Usage: node scripts/archive-artifact.cjs --artifact <dir> --output <archive.tar.gz> [--report <file>]");
      process.exit(0);
    } else fail(`unknown argument: ${value}`);
  }
  if (!options.artifact) fail("--artifact is required");
  if (!options.output) fail("--output is required");
  return {
    artifact: path.resolve(options.artifact),
    output: path.resolve(options.output),
    report: options.report ? path.resolve(options.report) : null,
  };
}

function isInside(parent, candidate) {
  const relative = path.relative(path.resolve(parent), path.resolve(candidate));
  return relative === "" || (relative && !relative.startsWith("..") && !path.isAbsolute(relative));
}

async function sha256File(file) {
  const hash = crypto.createHash("sha256");
  const stream = fs.createReadStream(file);
  for await (const chunk of stream) hash.update(chunk);
  return hash.digest("hex");
}

function runTar(args) {
  const result = spawnSync("tar", args, { stdio: "inherit", windowsHide: true });
  if (result.error) fail(`tar is unavailable: ${result.error.message}`);
  if (result.status !== 0) fail(`tar failed with exit code ${result.status}`);
}

async function archiveArtifact(options) {
  if (isInside(options.artifact, options.output)) fail("archive output must be outside the artifact directory");
  const verification = await verifyArtifact(options.artifact, { requireSignature: true });
  const manifest = verification.manifest;
  const target = manifest.target;
  if (!target || !["windows-x64", "linux-x64"].includes(target)) fail("artifact target is unsupported");
  if (manifest.runtime_boundary?.read_only !== true || manifest.runtime_boundary?.live_trading !== false) {
    fail("artifact boundary is not read-only and live-trading disabled");
  }
  await fsp.mkdir(path.dirname(options.output), { recursive: true });
  await fsp.rm(options.output, { force: true });
  runTar(["-czf", options.output, "--exclude=python/.market_os", "-C", options.artifact, "."]);
  const archiveSha256 = await sha256File(options.output);
  const extractRoot = await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-u7-c-archive-"));
  try {
    runTar(["-xzf", options.output, "-C", extractRoot]);
    const extracted = await verifyArtifact(extractRoot, { requireSignature: true });
    if (extracted.manifestSha256 !== verification.manifestSha256) fail("extracted archive manifest hash does not match source artifact");
    if (await fsp.stat(path.join(extractRoot, "python", ".market_os")).then(() => true).catch(() => false)) {
      fail("portable archive contains mutable python/.market_os state");
    }
  } finally {
    await fsp.rm(extractRoot, { recursive: true, force: true });
  }
  const report = {
    schema: "market-os.u7-c-portable-archive@v1",
    status: "passed",
    format: "tar.gz",
    target,
    version: manifest.version,
    source_manifest_sha256: verification.manifestSha256,
    signature: verification.signatureStatus,
    archive: path.basename(options.output),
    archive_sha256: archiveSha256,
    excluded_paths: ["python/.market_os"],
    boundary: manifest.runtime_boundary,
  };
  if (options.report) {
    await fsp.mkdir(path.dirname(options.report), { recursive: true });
    await fsp.writeFile(options.report, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  }
  return report;
}

async function main() {
  const report = await archiveArtifact(parseArgs(process.argv.slice(2)));
  console.log(JSON.stringify(report, null, 2));
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}

module.exports = { archiveArtifact, isInside, parseArgs, sha256File };
