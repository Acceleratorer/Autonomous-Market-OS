"use strict";

const assert = require("node:assert/strict");
const fsp = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { test } = require("node:test");
const { render } = require("../scripts/render-release-catalog-report.cjs");

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

function catalog() {
  return {
    schema: "market-os.u7-e-cross-target-release-catalog@v1",
    status: "passed",
    release_versions: ["0.1.0-ci.test.1", "0.1.0-ci.test.2"],
    targets: ["windows-x64", "linux-x64"],
    artifacts: [
      artifact("windows-x64", "known-good", "0.1.0-ci.test.1", "1"),
      artifact("windows-x64", "candidate", "0.1.0-ci.test.2", "2"),
      artifact("linux-x64", "known-good", "0.1.0-ci.test.1", "3"),
      artifact("linux-x64", "candidate", "0.1.0-ci.test.2", "4"),
    ],
    checks: {
      windows_verified: true,
      linux_verified: true,
      target_identity: true,
      role_versions_match: true,
      archive_hashes_unique: true,
      signatures_verified: true,
      boundaries_consistent: true,
      boundary: { ...boundary },
    },
  };
}

test("U7-F renders stable JSON and Markdown from a validated catalog", async () => {
  const root = await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-u7-f-report-"));
  const catalogPath = path.join(root, "cross-target-release-catalog.json");
  const markdown = path.join(root, "report.md");
  const json = path.join(root, "report.json");
  await writeJson(catalogPath, catalog());

  const result = await render({ catalog: catalogPath, markdown, json });
  assert.equal(result.schema, "market-os.u7-f-cross-target-release-catalog-report@v1");
  assert.equal(result.status, "passed");
  assert.equal(result.artifacts.length, 4);
  assert.match(await fsp.readFile(markdown, "utf8"), /# U7-F Cross-Target Release Catalog Report/);
  assert.deepEqual(JSON.parse(await fsp.readFile(json, "utf8")), result);

  const invalid = catalog();
  invalid.checks.boundary.live_trading = true;
  await writeJson(catalogPath, invalid);
  await assert.rejects(render({ catalog: catalogPath, markdown, json }), /boundary live_trading is unsafe/);

  const mismatched = catalog();
  mismatched.artifacts[3].version = "0.1.0-ci.test.1";
  await writeJson(catalogPath, mismatched);
  await assert.rejects(render({ catalog: catalogPath, markdown, json }), /candidate version differs between targets/);
});
