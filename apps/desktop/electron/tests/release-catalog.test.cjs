"use strict";

const assert = require("node:assert/strict");
const fsp = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { test } = require("node:test");
const { catalogRelease } = require("../scripts/catalog-release.cjs");

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

function archive(target, role, version, suffix) {
  return {
    role,
    target,
    version,
    archive: `market-os-${target}-${role}.tar.gz`,
    archive_sha256: `${suffix}`.repeat(64),
    manifest_sha256: `${role === "known-good" ? "a" : "b"}${suffix}`.repeat(32),
    signature: "verified",
    excluded_paths: ["python/.market_os"],
  };
}

async function writeIndex(root, target, candidateVersion = "0.1.0-ci.test.2") {
  const knownGood = archive(target, "known-good", "0.1.0-ci.test.1", target.startsWith("windows") ? "1" : "3");
  const candidate = archive(target, "candidate", candidateVersion, target.startsWith("windows") ? "2" : "4");
  await writeJson(path.join(root, "portable-archive-index.json"), {
    schema: "market-os.u7-d-portable-archive-index@v1",
    status: "passed",
    target,
    artifacts: [knownGood, candidate],
    checks: {
      archive_hashes_match_reports: true,
      manifests_match_validation: true,
      signatures_verified: true,
      mutable_sidecar_state_excluded: true,
      boundary,
    },
  });
}

test("U7-E catalogs both target-native release indexes", async () => {
  const root = await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-u7-e-catalog-"));
  const windows = path.join(root, "windows-x64");
  const linux = path.join(root, "linux-x64");
  const output = path.join(root, "release-catalog.json");
  await writeIndex(windows, "windows-x64");
  await writeIndex(linux, "linux-x64");

  const result = await catalogRelease({ windows, linux, output });
  assert.equal(result.schema, "market-os.u7-e-cross-target-release-catalog@v1");
  assert.equal(result.status, "passed");
  assert.deepEqual(result.targets, ["windows-x64", "linux-x64"]);
  assert.equal(result.artifacts.length, 4);
  assert.equal(JSON.parse(await fsp.readFile(output, "utf8")).checks.boundaries_consistent, true);

  await writeIndex(linux, "linux-x64", "0.1.0-ci.test.3");
  await assert.rejects(catalogRelease({ windows, linux, output }), /versions must be distinct and shared across targets/);
});
