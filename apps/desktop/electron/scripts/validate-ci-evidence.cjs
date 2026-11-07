"use strict";

const fsp = require("node:fs/promises");
const path = require("node:path");
const { verifyArtifact } = require("../src/release.cjs");

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = { root: null, report: null };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--") continue;
    if (value === "--root") options.root = argv[++index];
    else if (value === "--report") options.report = argv[++index];
    else if (value === "--help" || value === "-h") {
      console.log("Usage: node scripts/validate-ci-evidence.cjs --root <ci-output> [--report <file>]");
      process.exit(0);
    } else fail(`unknown argument: ${value}`);
  }
  if (!options.root) fail("--root is required");
  return {
    root: path.resolve(options.root),
    report: options.report ? path.resolve(options.report) : null,
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

function assertBoundary(boundary, label) {
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
    if (boundary?.[key] !== value) fail(`${label} boundary ${key} is unsafe`);
  }
}

function assertSmoke(report, expectedVersion, expectedTarget, artifactDigest) {
  if (report.schema !== "market-os.u6.4-artifact-smoke@v1") fail("unexpected smoke report schema");
  if (report.status !== "passed") fail(`smoke report for ${expectedVersion} is not passed`);
  if (report.version !== expectedVersion || report.target !== expectedTarget) {
    fail(`smoke report does not match ${expectedTarget}/${expectedVersion}`);
  }
  for (const route of ["readyz", "healthz", "overview", "runtime"]) {
    if (report.checks?.[`${route}_status`] !== 200) fail(`${route} smoke did not return 200`);
  }
  for (const [key, value] of Object.entries(report.checks?.boundary || {})) {
    requireTrue(value, `smoke boundary ${key}`);
  }
  requireTrue(report.checks?.runtime_exposes_signed_state, "signed runtime state");
  requireTrue(report.cleanup?.api_closed, "API cleanup");
  requireTrue(report.cleanup?.next_closed, "Next.js cleanup");
  if (report.manifest_sha256 !== artifactDigest) fail(`smoke manifest hash mismatch for ${expectedVersion}`);
}

async function validate(options) {
  const evidence = await readJson(path.join(options.root, "ci-evidence.json"), "CI evidence");
  if (evidence.schema !== "market-os.u6.4-ci-evidence@v1") fail("unexpected CI evidence schema");
  if (evidence.status !== "passed" || evidence.milestone !== "U6.4-C") fail("CI evidence is not a passed U6.4-C record");
  if (!evidence.target || !["windows-x64", "linux-x64"].includes(evidence.target)) fail("CI evidence target is unsupported");
  requireTrue(evidence.checks?.target_native_build, "target-native build");

  const artifactSpecs = [
    ["known_good", "artifact-known-good"],
    ["candidate", "artifact-candidate"],
  ];
  const artifacts = {};
  const smokeReports = [];
  for (const [name, directory] of artifactSpecs) {
    const expected = evidence.artifacts?.[name];
    if (!expected?.version) fail(`CI evidence is missing ${name} version`);
    const verification = await verifyArtifact(path.join(options.root, directory), { requireSignature: true });
    if (verification.manifest.target !== evidence.target || verification.manifest.version !== expected.version) {
      fail(`${name} artifact manifest does not match CI evidence`);
    }
    const smoke = await readJson(path.join(options.root, `smoke-${expected.version}.json`), `${name} smoke report`);
    assertSmoke(smoke, expected.version, evidence.target, verification.manifestSha256);
    smokeReports.push({
      version: expected.version,
      manifest_sha256: verification.manifestSha256,
      signature: verification.signatureStatus,
    });
    artifacts[name] = {
      version: expected.version,
      manifest_sha256: verification.manifestSha256,
      signature: verification.signatureStatus,
    };
  }

  if (artifacts.known_good.version === artifacts.candidate.version) fail("known-good and candidate versions must differ");
  if (artifacts.known_good.manifest_sha256 === artifacts.candidate.manifest_sha256) fail("known-good and candidate manifests must differ");

  const drill = await readJson(path.join(options.root, "release-drill.json"), "release drill");
  if (drill.schema !== "market-os.u6.4-release-hardening@v1" || drill.status !== "passed") {
    fail("release drill is not a passed U6.4-C record");
  }
  for (const key of [
    "candidate_signed",
    "known_good_signed",
    "versions_differ",
    "failed_launch_restored_metadata",
    "promotion_current_candidate",
    "known_good_preserved",
    "rollback_available_before",
    "rollback_to_known_good",
    "storage_isolation",
  ]) requireTrue(drill.checks?.[key], `release drill ${key}`);
  assertBoundary(evidence.boundary?.values, "CI evidence");

  const result = {
    schema: "market-os.u7-a-ci-evidence-validation@v1",
    status: "passed",
    target: evidence.target,
    artifacts,
    checks: {
      signed_smoke: smokeReports,
      promotion_rollback: drill.checks,
      boundary: evidence.boundary.values,
    },
  };
  if (options.report) {
    await fsp.mkdir(path.dirname(options.report), { recursive: true });
    await fsp.writeFile(options.report, `${JSON.stringify(result, null, 2)}\n`, "utf8");
  }
  return result;
}

async function main() {
  const result = await validate(parseArgs(process.argv.slice(2)));
  console.log(JSON.stringify(result, null, 2));
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}

module.exports = { assertBoundary, assertSmoke, parseArgs, validate };
