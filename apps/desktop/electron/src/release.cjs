"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const fsp = require("node:fs/promises");
const path = require("node:path");

const SIGNATURE_FILE = "release-signature.json";
const MANIFEST_FILE = "artifact-manifest.json";
const MANIFEST_DIGEST_FILE = "artifact-manifest.json.sha256";
const SLOT_SCHEMA = "market-os.u6.4-slot@v1";
const SIGNATURE_SCHEMA = "market-os.u6.4-signature@v1";

function manifestPath(artifactRoot) {
  return path.join(artifactRoot, MANIFEST_FILE);
}

function signaturePath(artifactRoot) {
  return path.join(artifactRoot, SIGNATURE_FILE);
}

function slotsPath(artifactRoot, slot) {
  return path.join(artifactRoot, "slots", `${slot}.json`);
}

function sha256Bytes(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

async function sha256File(file) {
  const hash = crypto.createHash("sha256");
  const stream = fs.createReadStream(file);
  for await (const chunk of stream) hash.update(chunk);
  return hash.digest("hex");
}

async function readJson(file) {
  return JSON.parse(await fsp.readFile(file, "utf8"));
}

async function readManifest(artifactRoot) {
  const file = manifestPath(artifactRoot);
  const bytes = await fsp.readFile(file);
  const manifest = JSON.parse(bytes.toString("utf8"));
  return { file, bytes, manifest, sha256: sha256Bytes(bytes) };
}

async function verifyManifestDigest(artifactRoot, digest) {
  const digestFile = path.join(artifactRoot, MANIFEST_DIGEST_FILE);
  const expected = (await fsp.readFile(digestFile, "utf8")).trim().split(/\s+/)[0];
  if (expected !== digest) {
    throw new Error(`artifact manifest SHA-256 mismatch: expected ${expected}, got ${digest}`);
  }
  return digest;
}

function parsePublicKey(value) {
  if (!value || typeof value !== "string") throw new Error("signature public key is missing");
  return crypto.createPublicKey(value);
}

async function readSignature(artifactRoot) {
  try {
    return await readJson(signaturePath(artifactRoot));
  } catch (error) {
    if (error && error.code === "ENOENT") return null;
    throw error;
  }
}

async function verifyArtifact(artifactRoot, { requireSignature = false } = {}) {
  const root = path.resolve(artifactRoot);
  const { bytes, manifest, sha256 } = await readManifest(root);
  await verifyManifestDigest(root, sha256);
  const signature = await readSignature(root);
  if (!signature) {
    if (requireSignature) throw new Error("artifact has no release-signature.json");
    return {
      root,
      manifest,
      manifestSha256: sha256,
      signature: null,
      signatureStatus: "unsigned",
      verified: false,
    };
  }
  if (signature.schema !== SIGNATURE_SCHEMA) throw new Error("unexpected release signature schema");
  if (signature.algorithm !== "ed25519") throw new Error("unsupported release signature algorithm");
  if (signature.manifest_sha256 !== sha256) throw new Error("release signature manifest hash does not match artifact");
  const publicKey = parsePublicKey(signature.public_key_pem);
  const expectedKeyId = sha256Bytes(publicKey.export({ format: "der", type: "spki" })).slice(0, 16);
  if (signature.key_id !== expectedKeyId) throw new Error("release signature key fingerprint does not match public key");
  const signatureBytes = Buffer.from(signature.signature_base64, "base64");
  const verified = crypto.verify(null, bytes, publicKey, signatureBytes);
  if (!verified) throw new Error("release signature verification failed");
  return {
    root,
    manifest,
    manifestSha256: sha256,
    signature,
    signatureStatus: "verified",
    verified: true,
  };
}

async function readSlot(artifactRoot, slot) {
  try {
    const value = await readJson(slotsPath(artifactRoot, slot));
    if (!value || value.schema !== SLOT_SCHEMA) throw new Error(`invalid ${slot} slot metadata`);
    return value;
  } catch (error) {
    if (error && error.code === "ENOENT") return null;
    throw error;
  }
}

async function writeJsonAtomic(file, value) {
  await fsp.mkdir(path.dirname(file), { recursive: true });
  const temporary = `${file}.${process.pid}.${Date.now()}.tmp`;
  await fsp.writeFile(temporary, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  await fsp.rename(temporary, file);
}

async function writeSlot(artifactRoot, slot, value) {
  await writeJsonAtomic(slotsPath(artifactRoot, slot), { schema: SLOT_SCHEMA, ...value });
}

function slotFromVerification(verification, slot, status) {
  return {
    slot,
    version: verification.manifest.version,
    target: verification.manifest.target,
    status,
    signature: verification.signatureStatus,
    artifact_root: ".",
    manifest_sha256: verification.manifestSha256,
  };
}

function resolveSlotRoot(artifactRoot, slot) {
  if (!slot || typeof slot.artifact_root !== "string") return null;
  return path.resolve(artifactRoot, slot.artifact_root);
}

async function readReleaseState(artifactRoot, manifest = null) {
  const root = artifactRoot ? path.resolve(artifactRoot) : null;
  if (!root) {
    return { signature: "not-packaged", currentSlot: "working-tree", knownGoodSlot: "u6.3-local-shell", rollbackAvailable: false };
  }
  const verification = await verifyArtifact(root).catch(() => null);
  const signatureMetadata = await readSignature(root).catch(() => null);
  const current = await readSlot(root, "current").catch(() => null);
  const knownGood = await readSlot(root, "known-good").catch(() => null);
  const manifestState = manifest?.release_state || {};
  const signature = verification?.signatureStatus === "verified"
    ? "verified"
    : signatureMetadata
      ? "invalid"
    : typeof manifestState.signature === "string" ? manifestState.signature : "unsigned";
  const currentSlot = current?.slot || manifestState.current_slot || "working-tree";
  const knownGoodSlot = knownGood?.slot || manifestState.known_good_slot || "u6.3-local-shell";
  const rollbackAvailable = Boolean(
    current && knownGood && current.manifest_sha256 && knownGood.manifest_sha256
      && current.manifest_sha256 !== knownGood.manifest_sha256,
  );
  return { signature, currentSlot, knownGoodSlot, rollbackAvailable, current, knownGood, verification };
}

module.exports = {
  MANIFEST_FILE,
  MANIFEST_DIGEST_FILE,
  SIGNATURE_FILE,
  SIGNATURE_SCHEMA,
  SLOT_SCHEMA,
  manifestPath,
  signaturePath,
  slotsPath,
  sha256Bytes,
  sha256File,
  readManifest,
  readSignature,
  verifyArtifact,
  readSlot,
  writeJsonAtomic,
  writeSlot,
  slotFromVerification,
  resolveSlotRoot,
  readReleaseState,
};
