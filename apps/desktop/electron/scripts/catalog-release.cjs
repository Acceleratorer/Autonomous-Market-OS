"use strict";

const fsp = require("node:fs/promises");
const path = require("node:path");
const { assertBoundary } = require("./validate-ci-evidence.cjs");

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = { windows: null, linux: null, output: null };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--") continue;
    if (value === "--windows") options.windows = argv[++index];
    else if (value === "--linux") options.linux = argv[++index];
    else if (value === "--output") options.output = argv[++index];
    else if (value === "--help" || value === "-h") {
      console.log("Usage: node scripts/catalog-release.cjs --windows <evidence-dir> --linux <evidence-dir> --output <file>");
      process.exit(0);
    } else fail(`unknown argument: ${value}`);
  }
  if (!options.windows) fail("--windows is required");
  if (!options.linux) fail("--linux is required");
  if (!options.output) fail("--output is required");
  return {
    windows: path.resolve(options.windows),
    linux: path.resolve(options.linux),
    output: path.resolve(options.output),
  };
}

async function readJson(file, label) {
  try {
    return JSON.parse(await fsp.readFile(file, "utf8"));
  } catch (error) {
    fail(`${label} is unreadable: ${error instanceof Error ? error.message : String(error)}`);
  }
}

function assertArtifact(artifact, target, role) {
  if (!artifact || artifact.role !== role || artifact.target !== target) {
    fail(`${target} ${role} archive identity is invalid`);
  }
  if (!artifact.version || !artifact.archive_sha256 || !artifact.manifest_sha256) {
    fail(`${target} ${role} archive metadata is incomplete`);
  }
  if (artifact.signature !== "verified") fail(`${target} ${role} archive is not signed`);
  if (typeof artifact.archive !== "string" || !artifact.archive.endsWith(".tar.gz") || !artifact.archive.includes(target)) {
    fail(`${target} ${role} archive filename is invalid`);
  }
  if (JSON.stringify(artifact.excluded_paths) !== JSON.stringify(["python/.market_os"])) {
    fail(`${target} ${role} archive does not exclude mutable sidecar state`);
  }
}

async function readIndex(root, target) {
  const index = await readJson(path.join(root, "portable-archive-index.json"), `${target} portable archive index`);
  if (index.schema !== "market-os.u7-d-portable-archive-index@v1" || index.status !== "passed") {
    fail(`${target} portable archive index is not passed`);
  }
  if (index.target !== target || !Array.isArray(index.artifacts) || index.artifacts.length !== 2) {
    fail(`${target} portable archive index has the wrong target or artifact count`);
  }
  for (const key of ["archive_hashes_match_reports", "manifests_match_validation", "signatures_verified", "mutable_sidecar_state_excluded"]) {
    if (index.checks?.[key] !== true) fail(`${target} archive index check ${key} is not true`);
  }
  assertBoundary(index.checks?.boundary, `${target} archive index`);
  return index;
}

async function catalogRelease(options) {
  const sources = [
    ["windows-x64", options.windows],
    ["linux-x64", options.linux],
  ];
  const indexes = [];
  for (const [target, root] of sources) indexes.push({ target, index: await readIndex(root, target) });
  const boundary = indexes[0].index.checks.boundary;
  if (JSON.stringify(boundary) !== JSON.stringify(indexes[1].index.checks.boundary)) {
    fail("target boundaries differ");
  }
  const artifacts = [];
  for (const { target, index } of indexes) {
    for (const role of ["known-good", "candidate"]) {
      const artifact = index.artifacts.find((entry) => entry.role === role);
      assertArtifact(artifact, target, role);
      artifacts.push({ ...artifact });
    }
  }
  const versions = new Set(artifacts.map((artifact) => artifact.version));
  if (versions.size !== 2) fail("known-good and candidate versions must be distinct and shared across targets");
  for (const role of ["known-good", "candidate"]) {
    const roleVersions = new Set(artifacts.filter((artifact) => artifact.role === role).map((artifact) => artifact.version));
    if (roleVersions.size !== 1) fail(`${role} version differs between targets`);
  }
  if (new Set(artifacts.map((artifact) => artifact.archive_sha256)).size !== artifacts.length) {
    fail("cross-target archive hashes must be unique");
  }

  const result = {
    schema: "market-os.u7-e-cross-target-release-catalog@v1",
    status: "passed",
    release_versions: [...versions],
    targets: ["windows-x64", "linux-x64"],
    artifacts,
    checks: {
      windows_verified: true,
      linux_verified: true,
      target_identity: true,
      role_versions_match: true,
      archive_hashes_unique: true,
      signatures_verified: true,
      boundaries_consistent: true,
      boundary,
    },
  };
  await fsp.mkdir(path.dirname(options.output), { recursive: true });
  await fsp.writeFile(options.output, `${JSON.stringify(result, null, 2)}\n`, "utf8");
  return result;
}

async function main() {
  const result = await catalogRelease(parseArgs(process.argv.slice(2)));
  console.log(JSON.stringify(result, null, 2));
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}

module.exports = { assertArtifact, catalogRelease, parseArgs, readIndex };
