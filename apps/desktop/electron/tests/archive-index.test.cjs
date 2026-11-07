"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fsp = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { test } = require("node:test");
const { indexArchives } = require("../scripts/index-portable-archives.cjs");

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

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

async function writeJson(file, value) {
  await fsp.writeFile(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

test("U7-D indexes portable archives only when report and file hashes agree", async () => {
  const root = await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-u7-d-index-"));
  const output = path.join(root, "portable-archive-index.json");
  const artifacts = {
    known_good: { version: "0.1.0-ci.test.1", manifest_sha256: "a".repeat(64) },
    candidate: { version: "0.1.0-ci.test.2", manifest_sha256: "b".repeat(64) },
  };
  await writeJson(path.join(root, "ci-evidence.json"), {
    schema: "market-os.u6.4-ci-evidence@v1",
    status: "passed",
    target: "linux-x64",
  });
  await writeJson(path.join(root, "ci-evidence-validation.json"), {
    schema: "market-os.u7-a-ci-evidence-validation@v1",
    status: "passed",
    target: "linux-x64",
    artifacts,
    checks: { boundary },
  });
  for (const [role, name] of [["known-good", "known_good"], ["candidate", "candidate"]]) {
    const archive = `market-os-linux-x64-${name}.tar.gz`;
    const bytes = Buffer.from(`${role} archive\n`, "utf8");
    await fsp.writeFile(path.join(root, archive), bytes);
    await writeJson(path.join(root, `portable-archive-${name}.json`), {
      schema: "market-os.u7-c-portable-archive@v1",
      status: "passed",
      format: "tar.gz",
      target: "linux-x64",
      version: artifacts[name].version,
      source_manifest_sha256: artifacts[name].manifest_sha256,
      signature: "verified",
      archive,
      archive_sha256: sha256(bytes),
      excluded_paths: ["python/.market_os"],
      boundary,
    });
  }

  const result = await indexArchives({ root, output });
  assert.equal(result.schema, "market-os.u7-d-portable-archive-index@v1");
  assert.equal(result.status, "passed");
  assert.equal(result.artifacts.length, 2);
  assert.equal(JSON.parse(await fsp.readFile(output, "utf8")).checks.signatures_verified, true);

  await fsp.appendFile(path.join(root, "market-os-linux-x64-candidate.tar.gz"), "tampered");
  await assert.rejects(indexArchives({ root, output }), /portable archive SHA-256 mismatch/);
});
