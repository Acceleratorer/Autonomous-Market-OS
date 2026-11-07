"use strict";

const fsp = require("node:fs/promises");
const path = require("node:path");
const { sha256File } = require("../src/release.cjs");
const { assertBoundary } = require("./validate-ci-evidence.cjs");

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = { root: null, output: null };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--") continue;
    if (value === "--root") options.root = argv[++index];
    else if (value === "--output") options.output = argv[++index];
    else if (value === "--help" || value === "-h") {
      console.log("Usage: node scripts/index-portable-archives.cjs --root <ci-output> [--output <file>]");
      process.exit(0);
    } else fail(`unknown argument: ${value}`);
  }
  if (!options.root) fail("--root is required");
  const root = path.resolve(options.root);
  return {
    root,
    output: path.resolve(options.output || path.join(root, "portable-archive-index.json")),
  };
}

async function readJson(file, label) {
  try {
    return JSON.parse(await fsp.readFile(file, "utf8"));
  } catch (error) {
    fail(`${label} is unreadable: ${error instanceof Error ? error.message : String(error)}`);
  }
}

function assertInside(root, file, label) {
  const relative = path.relative(root, file);
  if (!relative || relative.startsWith("..") || path.isAbsolute(relative)) {
    fail(`${label} must remain inside the CI evidence directory`);
  }
}

function assertArchiveReport(report, role, expected, root) {
  if (report.schema !== "market-os.u7-c-portable-archive@v1" || report.status !== "passed") {
    fail(`${role} portable archive report is not passed`);
  }
  if (report.target !== expected.target || report.version !== expected.version) {
    fail(`${role} portable archive report does not match CI evidence`);
  }
  if (report.signature !== "verified") fail(`${role} portable archive is not signed`);
  if (report.source_manifest_sha256 !== expected.manifest_sha256) {
    fail(`${role} portable archive manifest hash does not match validated artifact`);
  }
  if (JSON.stringify(report.excluded_paths) !== JSON.stringify(["python/.market_os"])) {
    fail(`${role} portable archive does not exclude mutable sidecar state`);
  }
  assertBoundary(report.boundary, `${role} portable archive`);
  if (typeof report.archive !== "string" || !report.archive.endsWith(".tar.gz")) {
    fail(`${role} portable archive filename is invalid`);
  }
  const archive = path.resolve(root, report.archive);
  assertInside(root, archive, `${role} portable archive`);
  return { ...report, archive_path: archive };
}

async function indexArchives(options) {
  const evidence = await readJson(path.join(options.root, "ci-evidence.json"), "CI evidence");
  const validation = await readJson(path.join(options.root, "ci-evidence-validation.json"), "validated CI evidence");
  if (evidence.schema !== "market-os.u6.4-ci-evidence@v1" || evidence.status !== "passed") {
    fail("CI evidence is not a passed U6.4-C record");
  }
  if (validation.schema !== "market-os.u7-a-ci-evidence-validation@v1" || validation.status !== "passed") {
    fail("CI evidence validation is not passed");
  }
  if (validation.target !== evidence.target) fail("portable archive target does not match CI evidence");
  assertBoundary(validation.checks?.boundary, "validated CI evidence");

  const specs = [
    ["known-good", "known_good", "known-good"],
    ["candidate", "candidate", "candidate"],
  ];
  const archives = [];
  for (const [role, name, reportName] of specs) {
    const expected = validation.artifacts?.[name];
    if (!expected?.version || !expected?.manifest_sha256) fail(`validated evidence is missing ${role} artifact`);
    const report = await readJson(path.join(options.root, `portable-archive-${reportName}.json`), `${role} portable archive report`);
    const checked = assertArchiveReport(report, role, {
      target: evidence.target,
      version: expected.version,
      manifest_sha256: expected.manifest_sha256,
    }, options.root);
    const archiveSha256 = await sha256File(checked.archive_path);
    if (archiveSha256 !== checked.archive_sha256) fail(`${role} portable archive SHA-256 mismatch`);
    archives.push({
      role,
      target: checked.target,
      version: checked.version,
      archive: checked.archive,
      archive_sha256: archiveSha256,
      manifest_sha256: checked.source_manifest_sha256,
      signature: checked.signature,
      excluded_paths: checked.excluded_paths,
    });
  }
  if (archives[0].version === archives[1].version) fail("portable archive versions must differ");
  if (archives[0].archive_sha256 === archives[1].archive_sha256) fail("portable archive hashes must differ");

  const result = {
    schema: "market-os.u7-d-portable-archive-index@v1",
    status: "passed",
    target: evidence.target,
    artifacts: archives,
    checks: {
      archives_present: true,
      archive_hashes_match_reports: true,
      manifests_match_validation: true,
      signatures_verified: true,
      mutable_sidecar_state_excluded: true,
      boundary: validation.checks.boundary,
    },
  };
  await fsp.mkdir(path.dirname(options.output), { recursive: true });
  await fsp.writeFile(options.output, `${JSON.stringify(result, null, 2)}\n`, "utf8");
  return result;
}

async function main() {
  const result = await indexArchives(parseArgs(process.argv.slice(2)));
  console.log(JSON.stringify(result, null, 2));
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}

module.exports = { assertArchiveReport, indexArchives, parseArgs };
