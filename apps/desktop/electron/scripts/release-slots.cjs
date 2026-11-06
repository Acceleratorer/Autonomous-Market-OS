"use strict";

const fsp = require("node:fs/promises");
const path = require("node:path");
const {
  readSlot,
  resolveSlotRoot,
  slotFromVerification,
  verifyArtifact,
  writeSlot,
} = require("../src/release.cjs");

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = { command: null, artifact: null, simulateLaunchFailure: false };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--") continue;
    if (!options.command && ["inspect", "promote", "rollback"].includes(value)) options.command = value;
    else if (value === "--artifact") options.artifact = argv[++index];
    else if (value === "--simulate-launch-failure") options.simulateLaunchFailure = true;
    else if (value === "--help" || value === "-h") {
      console.log("Usage: node scripts/release-slots.cjs <inspect|promote|rollback> --artifact <dir> [--simulate-launch-failure]");
      process.exit(0);
    } else fail(`unknown argument: ${value}`);
  }
  if (!options.command) fail("a release command is required: inspect, promote, or rollback");
  if (!options.artifact) fail("--artifact is required");
  return { ...options, artifact: path.resolve(options.artifact) };
}

async function verifySlotTarget(artifactRoot, slot) {
  const targetRoot = resolveSlotRoot(artifactRoot, slot);
  if (!targetRoot) fail(`slot ${slot?.slot || "unknown"} has no artifact root`);
  const verification = await verifyArtifact(targetRoot, { requireSignature: true });
  if (slot.manifest_sha256 !== verification.manifestSha256) {
    fail(`slot ${slot.slot} manifest hash does not match its artifact`);
  }
  return verification;
}

async function inspectArtifact(artifactRoot) {
  const verification = await verifyArtifact(artifactRoot);
  const current = await readSlot(artifactRoot, "current");
  const knownGood = await readSlot(artifactRoot, "known-good");
  return {
    artifact: artifactRoot,
    manifest_sha256: verification.manifestSha256,
    signature: verification.signatureStatus,
    current,
    known_good: knownGood,
    rollback_available: Boolean(current?.manifest_sha256 && knownGood?.manifest_sha256 && current.manifest_sha256 !== knownGood.manifest_sha256),
  };
}

async function promoteArtifact(artifactRoot, { simulateLaunchFailure = false } = {}) {
  const verification = await verifyArtifact(artifactRoot, { requireSignature: true });
  const previousCurrent = await readSlot(artifactRoot, "current");
  const previousKnownGood = await readSlot(artifactRoot, "known-good");
  const candidate = slotFromVerification(verification, "candidate", "current-verified");
  try {
    await writeSlot(artifactRoot, "current", candidate);
    if (previousCurrent) {
      await writeSlot(artifactRoot, "known-good", {
        ...previousCurrent,
        status: "known-good",
      });
    }
    if (simulateLaunchFailure) {
      throw new Error("simulated release launch failure");
    }
    return await inspectArtifact(artifactRoot);
  } catch (error) {
    if (previousCurrent) await writeSlot(artifactRoot, "current", previousCurrent);
    else await fsp.rm(path.join(artifactRoot, "slots", "current.json"), { force: true });
    if (previousKnownGood) await writeSlot(artifactRoot, "known-good", previousKnownGood);
    else await fsp.rm(path.join(artifactRoot, "slots", "known-good.json"), { force: true });
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`${message}; previous release slots restored`);
  }
}

async function rollbackArtifact(artifactRoot) {
  const current = await readSlot(artifactRoot, "current");
  const knownGood = await readSlot(artifactRoot, "known-good");
  if (!knownGood) fail("no known-good release slot is available");
  const verification = await verifySlotTarget(artifactRoot, knownGood);
  const restored = {
    ...knownGood,
    version: verification.manifest.version,
    target: verification.manifest.target,
    signature: verification.signatureStatus,
    status: "rollback-current",
  };
  await writeSlot(artifactRoot, "current", restored);
  return {
    artifact: artifactRoot,
    manifest_sha256: verification.manifestSha256,
    current: restored,
    known_good: knownGood,
    previous_current: current,
    rollback_available: Boolean(restored.manifest_sha256 && knownGood.manifest_sha256 && restored.manifest_sha256 !== knownGood.manifest_sha256),
  };
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const result = options.command === "inspect"
    ? await inspectArtifact(options.artifact)
    : options.command === "promote"
      ? await promoteArtifact(options.artifact, { simulateLaunchFailure: options.simulateLaunchFailure })
      : await rollbackArtifact(options.artifact);
  console.log(JSON.stringify(result, null, 2));
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}

module.exports = {
  parseArgs,
  inspectArtifact,
  promoteArtifact,
  rollbackArtifact,
};
