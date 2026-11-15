"use strict";

const crypto = require("node:crypto");
const fsp = require("node:fs/promises");
const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { validateRuntimeManifest, RUNTIME_MANIFEST_SCHEMA } = require("./python-runtime.cjs");

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = { runtimeRoot: null, target: null, version: null, sourceUrl: null, archive: null, interpreter: null, expectedSha256: null };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--") continue;
    if (value === "--runtime-root") options.runtimeRoot = argv[++index];
    else if (value === "--target") options.target = argv[++index];
    else if (value === "--version") options.version = argv[++index];
    else if (value === "--source-url") options.sourceUrl = argv[++index];
    else if (value === "--archive") options.archive = argv[++index];
    else if (value === "--interpreter") options.interpreter = argv[++index];
    else if (value === "--expected-sha256") options.expectedSha256 = argv[++index];
    else if (value === "--help" || value === "-h") {
      console.log("Usage: node scripts/prepare-python-runtime.cjs --runtime-root <dir> --target <target> --version <3.11.x> --source-url <python.org-url> --archive <file> --interpreter <relative-path> [--expected-sha256 <hash>]");
      process.exit(0);
    } else fail(`unknown argument: ${value}`);
  }
  for (const key of ["runtimeRoot", "target", "version", "sourceUrl", "archive", "interpreter"]) {
    if (!options[key]) fail(`--${key.replace(/[A-Z]/g, (match) => `-${match.toLowerCase()}`)} is required`);
  }
  if (!["windows-x64", "linux-x64"].includes(options.target)) fail(`unsupported target: ${options.target}`);
  return { ...options, runtimeRoot: path.resolve(options.runtimeRoot), archive: path.resolve(options.archive) };
}

async function sha256File(file) {
  const hash = crypto.createHash("sha256");
  const stream = fs.createReadStream(file);
  for await (const chunk of stream) hash.update(chunk);
  return hash.digest("hex");
}

function run(interpreter, args) {
  const result = spawnSync(interpreter, args, { encoding: "utf8", windowsHide: true });
  if (result.status !== 0) fail(`${path.basename(interpreter)} ${args.join(" ")} failed: ${(result.stderr || result.stdout || "").trim()}`);
  return (result.stdout || "").trim();
}

async function preparePythonRuntime(options) {
  const root = path.resolve(options.runtimeRoot);
  const interpreter = path.resolve(root, options.interpreter);
  await fsp.access(interpreter, fs.constants.X_OK).catch(() => fail(`runtime interpreter is missing or not executable: ${options.interpreter}`));
  await fsp.access(options.archive, fs.constants.R_OK).catch(() => fail(`official CPython archive is missing: ${options.archive}`));
  const reportedVersion = run(interpreter, ["--version"]);
  const versionMatch = reportedVersion.match(/Python\s+(3\.11\.\d+)/);
  if (!versionMatch || versionMatch[1] !== options.version) fail(`runtime interpreter reports ${reportedVersion}, expected Python ${options.version}`);
  run(interpreter, ["-c", "import duckdb, pyarrow"]);
  const archiveSha256 = await sha256File(options.archive);
  if (options.expectedSha256 && archiveSha256 !== options.expectedSha256.toLowerCase()) {
    fail(`official CPython archive SHA-256 mismatch: expected ${options.expectedSha256}, got ${archiveSha256}`);
  }
  const manifest = {
    schema: RUNTIME_MANIFEST_SCHEMA,
    distribution: "cpython",
    version: options.version,
    target: options.target,
    source: "python.org",
    source_url: options.sourceUrl,
    archive_sha256: archiveSha256,
    interpreter: options.interpreter.replaceAll(path.sep, "/"),
    dependencies: ["duckdb>=1.4,<3", "pyarrow>=18,<27"],
  };
  validateRuntimeManifest(manifest, { target: options.target });
  await fsp.writeFile(path.join(root, "runtime-manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  return manifest;
}

async function main() {
  const manifest = await preparePythonRuntime(parseArgs(process.argv.slice(2)));
  console.log(JSON.stringify({ status: "passed", manifest }, null, 2));
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}

module.exports = { parseArgs, preparePythonRuntime, sha256File };
