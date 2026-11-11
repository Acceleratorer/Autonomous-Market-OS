"use strict";

const assert = require("node:assert/strict");
const fsp = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { test } = require("node:test");
const { catalogRelease } = require("../scripts/catalog-release.cjs");
const { auditDrift } = require("../scripts/audit-release-drift.cjs");

const boundary = {
  loopback_only: true,
  synthetic: true,
  paper_only: true,
  read_only: true,
  credentials: false,
  provider_requests: 0,
  mutation_routes: false,
  live_trading: false,
};

async function writeJson(file, value) {
  await fsp.mkdir(path.dirname(file), { recursive: true });
  await fsp.writeFile(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function artifact(target, role, version, suffix) {
  return {
    target,
    role,
    version,
    archive: `market-os-${target}-${role}.tar.gz`,
    archive_sha256: suffix.repeat(64),
    manifest_sha256: (role === "known-good" ? "a" : "b").repeat(64),
    signature: "verified",
    excluded_paths: ["python/.market_os"],
  };
}

async function writeBundle(root, target, options = {}) {
  const knownGoodVersion = options.knownGoodVersion || "0.1.0-ci.test.1";
  const candidateVersion = options.candidateVersion || "0.1.0-ci.test.2";
  const knownGood = artifact(target, "known-good", knownGoodVersion, target === "windows-x64" ? "1" : "3");
  const candidate = artifact(target, "candidate", candidateVersion, target === "windows-x64" ? "2" : "4");
  const targetBoundary = { ...boundary, ...(options.boundary || {}) };
  const smoke = (entry) => ({
    schema: "market-os.u6.4-artifact-smoke@v1",
    status: "passed",
    target,
    version: entry.version,
    manifest_sha256: entry.manifest_sha256,
    checks: {
      readyz_status: 200,
      healthz_status: options.healthzStatus || 200,
      overview_status: 200,
      runtime_status: 200,
      runtime_exposes_signed_state: true,
      boundary: { loopback_only: true, synthetic: true, paper_only: true, read_only: true },
    },
    cleanup: { api_closed: true, next_closed: true },
  });
  const promotionRollback = {
    candidate_signed: true,
    known_good_signed: true,
    versions_differ: true,
    failed_launch_restored_metadata: true,
    promotion_current_candidate: true,
    known_good_preserved: true,
    rollback_available_before: true,
    rollback_to_known_good: true,
    storage_isolation: true,
  };
  const promotionBoundaryChecks = Object.fromEntries(Object.keys(targetBoundary).map((key) => [key, true]));
  await writeJson(path.join(root, "ci-evidence.json"), {
    schema: "market-os.u6.4-ci-evidence@v1", milestone: "U6.4-C", status: "passed", target,
    artifacts: { known_good: { version: knownGoodVersion }, candidate: { version: candidateVersion } },
    checks: { target_native_build: true },
    boundary: { values: targetBoundary, checks: Object.fromEntries(Object.keys(targetBoundary).map((key) => [key, true])) },
  });
  await writeJson(path.join(root, "ci-evidence-validation.json"), {
    schema: "market-os.u7-a-ci-evidence-validation@v1", status: "passed", target,
    artifacts: {
      known_good: { version: knownGoodVersion, manifest_sha256: knownGood.manifest_sha256, signature: "verified" },
      candidate: { version: candidateVersion, manifest_sha256: candidate.manifest_sha256, signature: "verified" },
    },
    checks: {
      signed_smoke: [
        { version: knownGoodVersion, manifest_sha256: knownGood.manifest_sha256, signature: "verified" },
        { version: candidateVersion, manifest_sha256: candidate.manifest_sha256, signature: "verified" },
      ],
      promotion_rollback: promotionRollback, boundary: targetBoundary,
    },
  });
  await writeJson(path.join(root, "release-evidence-report.json"), {
    schema: "market-os.u7-b-release-evidence-report@v1", status: "passed", target,
    artifacts: [
      { role: "known-good", target, version: knownGoodVersion, manifest_sha256: knownGood.manifest_sha256, signature: "verified" },
      { role: "candidate", target, version: candidateVersion, manifest_sha256: candidate.manifest_sha256, signature: "verified" },
    ], promotion_rollback: promotionRollback, boundary: targetBoundary,
  });
  await writeJson(path.join(root, "portable-archive-index.json"), {
    schema: "market-os.u7-d-portable-archive-index@v1", status: "passed", target, artifacts: [knownGood, candidate],
    checks: { archive_hashes_match_reports: true, manifests_match_validation: true, signatures_verified: true, mutable_sidecar_state_excluded: true, boundary: targetBoundary },
  });
  await writeJson(path.join(root, "release-drill.json"), {
    schema: "market-os.u6.4-release-hardening@v1",
    status: "passed",
    target,
    artifacts: {
      known_good: { version: knownGoodVersion, manifest_sha256: knownGood.manifest_sha256, signature: "verified" },
      candidate: { version: candidateVersion, manifest_sha256: candidate.manifest_sha256, signature: "verified" },
    },
    checks: { ...promotionRollback, boundary: promotionBoundaryChecks },
  });
  await writeJson(path.join(root, `smoke-${knownGoodVersion}.json`), smoke(knownGood));
  await writeJson(path.join(root, `smoke-${candidateVersion}.json`), smoke(candidate));
}

async function makeFixture(options = {}) {
  const root = await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-u7-m-drift-"));
  const windows = path.join(root, "windows-x64");
  const linux = path.join(root, "linux-x64");
  await writeBundle(windows, "windows-x64", options.windows);
  await writeBundle(linux, "linux-x64", options.linux);
  const catalog = path.join(root, "cross-target-release-catalog.json");
  await catalogRelease({ windows, linux, output: catalog });
  return { root, windows, linux, catalog };
}

test("U7-M passes when target bundles agree on shared release evidence", async () => {
  const fixture = await makeFixture();
  const result = await auditDrift({ ...fixture, markdown: path.join(fixture.root, "drift.md"), json: path.join(fixture.root, "drift.json") });
  assert.equal(result.schema, "market-os.u7-m-release-evidence-drift@v1");
  assert.equal(result.status, "passed");
  assert.deepEqual(result.drift, []);
  assert.equal(result.checks.boundaries_consistent, true);
  assert.match(await fsp.readFile(path.join(fixture.root, "drift.md"), "utf8"), /# U7-M Release Evidence Drift Audit/);
});

test("U7-M fails closed on boundary drift", async () => {
  const fixture = await makeFixture();
  const validationPath = path.join(fixture.linux, "ci-evidence-validation.json");
  const validation = JSON.parse(await fsp.readFile(validationPath, "utf8"));
  validation.checks.boundary.live_trading = true;
  await writeJson(validationPath, validation);
  const result = await auditDrift({ ...fixture });
  assert.equal(result.status, "failed");
  assert.ok(result.drift.some((entry) => entry.code === "boundary_mismatch"));
});

test("U7-M fails closed on raw-to-derived manifest drift", async () => {
  const fixture = await makeFixture();
  const reportPath = path.join(fixture.windows, "release-evidence-report.json");
  const report = JSON.parse(await fsp.readFile(reportPath, "utf8"));
  report.artifacts[1].manifest_sha256 = "c".repeat(64);
  await writeJson(reportPath, report);
  const result = await auditDrift({ ...fixture });
  assert.equal(result.status, "failed");
  assert.ok(result.drift.some((entry) => entry.code === "manifest_hash_mismatch"));
});

test("U7-M fails closed when a signed smoke route is not healthy", async () => {
  const fixture = await makeFixture();
  const smokePath = path.join(fixture.linux, "smoke-0.1.0-ci.test.1.json");
  const smoke = JSON.parse(await fsp.readFile(smokePath, "utf8"));
  smoke.checks.healthz_status = 503;
  await writeJson(smokePath, smoke);
  const result = await auditDrift({ ...fixture });
  assert.equal(result.status, "failed");
  assert.ok(result.drift.some((entry) => entry.code === "smoke_route_failed"));
});
