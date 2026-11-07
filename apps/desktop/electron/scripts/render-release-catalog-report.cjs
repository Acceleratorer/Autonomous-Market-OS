"use strict";

const fsp = require("node:fs/promises");
const path = require("node:path");
const { assertBoundary } = require("./validate-ci-evidence.cjs");

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = { catalog: null, markdown: null, json: null };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--") continue;
    if (value === "--catalog") options.catalog = argv[++index];
    else if (value === "--markdown") options.markdown = argv[++index];
    else if (value === "--json") options.json = argv[++index];
    else if (value === "--help" || value === "-h") {
      console.log("Usage: node scripts/render-release-catalog-report.cjs --catalog <catalog.json> [--markdown <file>] [--json <file>]");
      process.exit(0);
    } else fail(`unknown argument: ${value}`);
  }
  if (!options.catalog) fail("--catalog is required");
  const catalog = path.resolve(options.catalog);
  const root = path.dirname(catalog);
  return {
    catalog,
    markdown: path.resolve(options.markdown || path.join(root, "cross-target-release-catalog.md")),
    json: path.resolve(options.json || path.join(root, "cross-target-release-catalog-report.json")),
  };
}

async function readJson(file, label) {
  try {
    return JSON.parse(await fsp.readFile(file, "utf8"));
  } catch (error) {
    fail(`${label} is unreadable: ${error instanceof Error ? error.message : String(error)}`);
  }
}

function requireTrue(value, label) {
  if (value !== true) fail(`${label} is not true`);
}

function validateCatalog(catalog) {
  if (catalog.schema !== "market-os.u7-e-cross-target-release-catalog@v1") fail("unexpected cross-target catalog schema");
  if (catalog.status !== "passed") fail("cross-target catalog is not passed");
  if (JSON.stringify(catalog.targets) !== JSON.stringify(["windows-x64", "linux-x64"])) {
    fail("cross-target catalog targets are invalid");
  }
  if (!Array.isArray(catalog.release_versions) || catalog.release_versions.length !== 2
    || new Set(catalog.release_versions).size !== 2) {
    fail("cross-target catalog release versions are invalid");
  }
  for (const key of [
    "windows_verified",
    "linux_verified",
    "target_identity",
    "role_versions_match",
    "archive_hashes_unique",
    "signatures_verified",
    "boundaries_consistent",
  ]) requireTrue(catalog.checks?.[key], `catalog check ${key}`);
  assertBoundary(catalog.checks?.boundary, "cross-target catalog");

  if (!Array.isArray(catalog.artifacts) || catalog.artifacts.length !== 4) {
    fail("cross-target catalog must contain four artifacts");
  }
  const seenHashes = new Set();
  const versionsByRole = new Map();
  for (const target of catalog.targets) {
    for (const role of ["known-good", "candidate"]) {
      const matches = catalog.artifacts.filter((artifact) => artifact.target === target && artifact.role === role);
      if (matches.length !== 1) fail(`${target} ${role} artifact is missing or duplicated`);
      const artifact = matches[0];
      if (!catalog.release_versions.includes(artifact.version)) fail(`${target} ${role} version is not cataloged`);
      if (artifact.signature !== "verified") fail(`${target} ${role} signature is not verified`);
      if (typeof artifact.archive_sha256 !== "string" || !/^[0-9a-f]{64}$/.test(artifact.archive_sha256)) {
        fail(`${target} ${role} archive hash is invalid`);
      }
      if (typeof artifact.manifest_sha256 !== "string" || !/^[0-9a-f]{64}$/.test(artifact.manifest_sha256)) {
        fail(`${target} ${role} manifest hash is invalid`);
      }
      if (seenHashes.has(artifact.archive_sha256)) fail("cross-target archive hashes are not unique");
      seenHashes.add(artifact.archive_sha256);
      const expectedVersion = versionsByRole.get(role);
      if (expectedVersion && expectedVersion !== artifact.version) fail(`${role} version differs between targets`);
      versionsByRole.set(role, artifact.version);
      if (JSON.stringify(artifact.excluded_paths) !== JSON.stringify(["python/.market_os"])) {
        fail(`${target} ${role} mutable sidecar state is not excluded`);
      }
    }
  }
  return catalog;
}

function pass(value) {
  return value ? "PASS" : "FAIL";
}

function renderMarkdown(report) {
  const artifactRows = report.artifacts.map((artifact) => [
    artifact.target,
    artifact.role,
    artifact.version,
    `\`${artifact.archive_sha256}\``,
    artifact.signature,
  ]);
  const checkRows = Object.entries(report.checks).map(([key, value]) => [key, pass(value)]);
  const boundaryRows = Object.entries(report.boundary).map(([key, value]) => [key, String(value)]);
  return [
    "# U7-F Cross-Target Release Catalog Report",
    "",
    `- Status: **${report.status.toUpperCase()}**`,
    `- Release versions: ${report.release_versions.map((version) => `\`${version}\``).join(", ")}`,
    "- Targets: `windows-x64`, `linux-x64`",
    "- Scope: signed, private, read-only, paper-only release evidence",
    "",
    "## Artifacts",
    "",
    "| Target | Role | Version | Archive SHA-256 | Signature |",
    "| --- | --- | --- | --- | --- |",
    artifactRows.map((row) => `| ${row.join(" | ")} |`).join("\n"),
    "",
    "## Catalog checks",
    "",
    "| Check | Result |",
    "| --- | --- |",
    checkRows.map((row) => `| ${row.join(" | ")} |`).join("\n"),
    "",
    "## Runtime boundary",
    "",
    "| Boundary | Value |",
    "| --- | --- |",
    boundaryRows.map((row) => `| ${row.join(" | ")} |`).join("\n"),
    "",
    "Generated from the validated U7-E cross-target release catalog.",
    "",
  ].join("\n");
}

async function render(options) {
  const catalog = validateCatalog(await readJson(options.catalog, "cross-target release catalog"));
  const report = {
    schema: "market-os.u7-f-cross-target-release-catalog-report@v1",
    status: "passed",
    release_versions: catalog.release_versions,
    targets: catalog.targets,
    artifacts: catalog.artifacts.map((artifact) => ({
      target: artifact.target,
      role: artifact.role,
      version: artifact.version,
      archive: artifact.archive,
      archive_sha256: artifact.archive_sha256,
      manifest_sha256: artifact.manifest_sha256,
      signature: artifact.signature,
      excluded_paths: artifact.excluded_paths,
    })),
    checks: {
      windows_verified: true,
      linux_verified: true,
      target_identity: true,
      role_versions_match: true,
      archive_hashes_unique: true,
      signatures_verified: true,
      boundaries_consistent: true,
    },
    boundary: catalog.checks.boundary,
  };
  await fsp.mkdir(path.dirname(options.markdown), { recursive: true });
  await fsp.mkdir(path.dirname(options.json), { recursive: true });
  await fsp.writeFile(options.markdown, renderMarkdown(report), "utf8");
  await fsp.writeFile(options.json, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  return report;
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const report = await render(options);
  console.log(JSON.stringify({ status: report.status, markdown: options.markdown, json: options.json }, null, 2));
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}

module.exports = { parseArgs, render, renderMarkdown, validateCatalog };
