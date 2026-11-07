"use strict";

const fsp = require("node:fs/promises");
const path = require("node:path");

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = { root: null, markdown: null, json: null };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--") continue;
    if (value === "--root") options.root = argv[++index];
    else if (value === "--markdown") options.markdown = argv[++index];
    else if (value === "--json") options.json = argv[++index];
    else if (value === "--help" || value === "-h") {
      console.log("Usage: node scripts/render-ci-evidence-report.cjs --root <ci-output> [--markdown <file>] [--json <file>]");
      process.exit(0);
    } else fail(`unknown argument: ${value}`);
  }
  if (!options.root) fail("--root is required");
  const root = path.resolve(options.root);
  return {
    root,
    markdown: path.resolve(options.markdown || path.join(root, "release-evidence-report.md")),
    json: path.resolve(options.json || path.join(root, "release-evidence-report.json")),
  };
}

async function readJson(file, label) {
  try {
    return JSON.parse(await fsp.readFile(file, "utf8"));
  } catch (error) {
    fail(`${label} is unreadable: ${error instanceof Error ? error.message : String(error)}`);
  }
}

function pass(value) {
  return value ? "PASS" : "FAIL";
}

function markdownTable(rows) {
  return rows.map((row) => `| ${row.join(" | ")} |`).join("\n");
}

function renderMarkdown(report) {
  const artifactRows = report.artifacts.map((artifact) => [
    artifact.role,
    artifact.version,
    `\`${artifact.manifest_sha256}\``,
    artifact.signature,
  ]);
  const smokeRows = report.signed_smoke.map((smoke) => [
    smoke.version,
    smoke.routes.readyz,
    smoke.routes.healthz,
    smoke.routes.overview,
    smoke.routes.runtime,
    pass(smoke.cleanup.api_closed && smoke.cleanup.next_closed),
  ]);
  const promotionRows = Object.entries(report.promotion_rollback)
    .filter(([, value]) => typeof value === "boolean")
    .map(([key, value]) => [key, pass(value)]);
  const boundaryRows = Object.entries(report.boundary).map(([key, value]) => [key, String(value), pass(
    (typeof value === "boolean" && value === true)
      || (key === "credentials" && value === false)
      || (key === "provider_requests" && value === 0)
      || (key === "mutation_routes" && value === false)
      || (key === "live_trading" && value === false),
  )]);
  return [
    "# U6.4-C Release Evidence",
    "",
    `- Status: **${report.status.toUpperCase()}**`,
    `- Target: \`${report.target}\``,
    "- Scope: signed, private, read-only, paper-only artifact release",
    "",
    "## Artifacts",
    "",
    "| Role | Version | Manifest SHA-256 | Signature |",
    "| --- | --- | --- | --- |",
    markdownTable(artifactRows),
    "",
    "## Signed smoke",
    "",
    "| Version | `/readyz` | `/healthz` | `/overview` | `/runtime` | Ports closed |",
    "| --- | ---: | ---: | ---: | ---: | --- |",
    markdownTable(smokeRows),
    "",
    "## Promotion and rollback",
    "",
    "| Check | Result |",
    "| --- | --- |",
    markdownTable(promotionRows),
    "",
    "## Runtime boundary",
    "",
    "| Boundary | Value | Result |",
    "| --- | --- | --- |",
    markdownTable(boundaryRows),
    "",
    "Generated from `ci-evidence-validation.json` after offline signature and evidence validation.",
    "",
  ].join("\n");
}

async function render(options) {
  const validation = await readJson(path.join(options.root, "ci-evidence-validation.json"), "validated CI evidence");
  if (validation.schema !== "market-os.u7-a-ci-evidence-validation@v1" || validation.status !== "passed") {
    fail("CI evidence must pass U7-A validation before rendering");
  }
  const smoke = [];
  for (const artifact of [validation.artifacts.known_good, validation.artifacts.candidate]) {
    const report = await readJson(path.join(options.root, `smoke-${artifact.version}.json`), `${artifact.version} smoke report`);
    smoke.push({
      version: artifact.version,
      routes: {
        readyz: report.checks?.readyz_status,
        healthz: report.checks?.healthz_status,
        overview: report.checks?.overview_status,
        runtime: report.checks?.runtime_status,
      },
      cleanup: {
        api_closed: report.cleanup?.api_closed === true,
        next_closed: report.cleanup?.next_closed === true,
      },
    });
  }
  const report = {
    schema: "market-os.u7-b-release-evidence-report@v1",
    status: "passed",
    target: validation.target,
    artifacts: [
      { role: "known-good", ...validation.artifacts.known_good },
      { role: "candidate", ...validation.artifacts.candidate },
    ],
    signed_smoke: smoke,
    promotion_rollback: validation.checks.promotion_rollback,
    boundary: validation.checks.boundary,
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
  console.log(JSON.stringify({
    status: report.status,
    target: report.target,
    markdown: options.markdown,
    json: options.json,
  }, null, 2));
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}

module.exports = { parseArgs, render, renderMarkdown };
