"use strict";

const crypto = require("node:crypto");
const fsp = require("node:fs/promises");
const path = require("node:path");
const REPO_ROOT = path.resolve(__dirname, "../../../..");
const {
  SIGNATURE_SCHEMA,
  signaturePath,
  readManifest,
  verifyArtifact,
  writeJsonAtomic,
} = require("../src/release.cjs");

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = { artifact: null, privateKey: null, publicKey: null, output: null };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--") continue;
    if (value === "--artifact") options.artifact = argv[++index];
    else if (value === "--private-key") options.privateKey = argv[++index];
    else if (value === "--public-key") options.publicKey = argv[++index];
    else if (value === "--output") options.output = argv[++index];
    else if (value === "--help" || value === "-h") {
      console.log("Usage: node scripts/sign-artifact.cjs --artifact <dir> --private-key <external.pem> [--public-key <pem>] [--output <file>]");
      process.exit(0);
    } else fail(`unknown argument: ${value}`);
  }
  if (!options.artifact) fail("--artifact is required");
  if (!options.privateKey) fail("--private-key is required");
  return {
    artifact: path.resolve(options.artifact),
    privateKey: path.resolve(options.privateKey),
    publicKey: options.publicKey ? path.resolve(options.publicKey) : null,
    output: options.output ? path.resolve(options.output) : null,
  };
}

function isInside(parent, candidate) {
  const relative = path.relative(path.resolve(parent), path.resolve(candidate));
  return relative === "" || (relative && !relative.startsWith("..") && !path.isAbsolute(relative));
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (isInside(REPO_ROOT, options.privateKey)) {
    fail("private signing key must live outside the repository and artifact directory");
  }
  if (options.output && !isInside(options.artifact, options.output)) {
    fail("signature metadata must be written inside the artifact directory");
  }
  const manifest = await readManifest(options.artifact);
  const privateKeyPem = await fsp.readFile(options.privateKey, "utf8");
  const privateKey = crypto.createPrivateKey(privateKeyPem);
  const derivedPublicKey = crypto.createPublicKey(privateKey);
  const publicKey = options.publicKey
    ? crypto.createPublicKey(await fsp.readFile(options.publicKey, "utf8"))
    : derivedPublicKey;
  const derivedPublicDer = derivedPublicKey.export({ format: "der", type: "spki" });
  const publicDer = publicKey.export({ format: "der", type: "spki" });
  if (!Buffer.from(derivedPublicDer).equals(Buffer.from(publicDer))) {
    fail("provided public key does not match the private key");
  }
  const signatureBytes = crypto.sign(null, manifest.bytes, privateKey);
  const record = {
    schema: SIGNATURE_SCHEMA,
    algorithm: "ed25519",
    manifest_sha256: manifest.sha256,
    key_id: crypto.createHash("sha256").update(publicDer).digest("hex").slice(0, 16),
    public_key_pem: publicKey.export({ format: "pem", type: "spki" }).toString(),
    signature_base64: signatureBytes.toString("base64"),
  };
  const output = options.output || signaturePath(options.artifact);
  await writeJsonAtomic(output, record);
  const verification = await verifyArtifact(options.artifact, { requireSignature: true });
  if (verification.signature?.key_id !== record.key_id) fail("written signature metadata failed verification");
  console.log(JSON.stringify({
    artifact: options.artifact,
    signature: output,
    manifest_sha256: manifest.sha256,
    key_id: record.key_id,
    status: verification.signatureStatus,
  }, null, 2));
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}

module.exports = { parseArgs, isInside };
