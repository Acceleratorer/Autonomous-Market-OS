"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fsp = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { execFile } = require("node:child_process");
const { promisify } = require("node:util");
const { test } = require("node:test");
const { promoteArtifact, rollbackArtifact } = require("../scripts/release-slots.cjs");
const { readSlot, verifyArtifact, writeSlot } = require("../src/release.cjs");

const execFileAsync = promisify(execFile);

async function writeArtifact(root, version) {
  await fsp.mkdir(path.join(root, "slots"), { recursive: true });
  const manifest = {
    schema: "market-os.u6.4-artifact@v1",
    status: "unsigned-reproducible",
    version,
    target: "linux-x64",
    runtime_boundary: { read_only: true, live_trading: false },
  };
  const manifestBytes = Buffer.from(`${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  await fsp.writeFile(path.join(root, "artifact-manifest.json"), manifestBytes);
  const digest = crypto.createHash("sha256").update(manifestBytes).digest("hex");
  await fsp.writeFile(path.join(root, "artifact-manifest.json.sha256"), `${digest}  artifact-manifest.json\n`);
  await writeSlot(root, "current", {
    slot: `old-${version}`,
    version,
    target: "linux-x64",
    status: "current-verified",
    signature: "verified",
    artifact_root: ".",
    manifest_sha256: digest,
  });
  await writeSlot(root, "known-good", {
    slot: `old-${version}`,
    version,
    target: "linux-x64",
    status: "known-good",
    signature: "verified",
    artifact_root: ".",
    manifest_sha256: digest,
  });
  return digest;
}

async function signArtifact(root, privateKey) {
  await execFileAsync(process.execPath, [
    path.resolve(__dirname, "../scripts/sign-artifact.cjs"),
    "--artifact", root,
    "--private-key", privateKey,
  ]);
}

test("U6.4-B signs final manifest bytes and verifies with an external key", async () => {
  const tempRoot = await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-u6-4-sign-"));
  const artifact = path.join(tempRoot, "artifact");
  const keyPair = crypto.generateKeyPairSync("ed25519");
  const privateKey = path.join(tempRoot, "release-private.pem");
  await fsp.writeFile(privateKey, keyPair.privateKey.export({ format: "pem", type: "pkcs8" }));
  await writeArtifact(artifact, "0.6.4-test");
  await signArtifact(artifact, privateKey);
  const verification = await verifyArtifact(artifact, { requireSignature: true });
  assert.equal(verification.signatureStatus, "verified");
  assert.equal(verification.signature.manifest_sha256, verification.manifestSha256);
  assert.equal(await fsp.access(privateKey).then(() => true), true);
});

test("U6.4-B promotes only verified artifacts and restores slots after a failed launch", async () => {
  const tempRoot = await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-u6-4-slots-"));
  const previous = path.join(tempRoot, "known-good");
  const candidate = path.join(tempRoot, "candidate");
  const keyPair = crypto.generateKeyPairSync("ed25519");
  const privateKey = path.join(tempRoot, "release-private.pem");
  await fsp.writeFile(privateKey, keyPair.privateKey.export({ format: "pem", type: "pkcs8" }));
  const previousDigest = await writeArtifact(previous, "0.6.3-test");
  await writeArtifact(candidate, "0.6.4-test");
  await signArtifact(previous, privateKey);
  await signArtifact(candidate, privateKey);
  await writeSlot(candidate, "current", {
    slot: "0.6.3-test",
    version: "0.6.3-test",
    target: "linux-x64",
    status: "current-verified",
    signature: "verified",
    artifact_root: "../known-good",
    manifest_sha256: previousDigest,
  });
  await writeSlot(candidate, "known-good", {
    slot: "0.6.3-test",
    version: "0.6.3-test",
    target: "linux-x64",
    status: "known-good",
    signature: "verified",
    artifact_root: "../known-good",
    manifest_sha256: previousDigest,
  });

  await assert.rejects(
    promoteArtifact(candidate, { simulateLaunchFailure: true }),
    /simulated release launch failure; previous release slots restored/,
  );
  assert.equal((await readSlot(candidate, "current")).manifest_sha256, previousDigest);
  assert.equal((await readSlot(candidate, "known-good")).manifest_sha256, previousDigest);

  const promoted = await promoteArtifact(candidate);
  assert.equal(promoted.current.slot, "candidate");
  assert.equal(promoted.known_good.manifest_sha256, previousDigest);
  const rolledBack = await rollbackArtifact(candidate);
  assert.equal(rolledBack.current.manifest_sha256, previousDigest);
  assert.equal(rolledBack.current.status, "rollback-current");

  const previousManifest = path.join(previous, "artifact-manifest.json");
  const tamperedManifest = JSON.parse(await fsp.readFile(previousManifest, "utf8"));
  tamperedManifest.version = "0.6.3-tampered";
  await fsp.writeFile(previousManifest, `${JSON.stringify(tamperedManifest, null, 2)}\n`);
  await assert.rejects(rollbackArtifact(candidate), /manifest SHA-256 mismatch/);
  assert.equal((await readSlot(candidate, "current")).manifest_sha256, previousDigest);
});
