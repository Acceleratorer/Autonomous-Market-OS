"use strict";

const fsp = require("node:fs/promises");
const path = require("node:path");
const {
  verifyArtifact,
  writeSlot,
} = require("../src/release.cjs");
const {
  inspectArtifact,
  promoteArtifact,
  rollbackArtifact,
} = require("./release-slots.cjs");

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = { candidate: null, knownGood: null, report: null };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--") continue;
    if (value === "--candidate") options.candidate = argv[++index];
    else if (value === "--known-good") options.knownGood = argv[++index];
    else if (value === "--report") options.report = argv[++index];
    else if (value === "--help" || value === "-h") {
      console.log("Usage: node scripts/release-drill.cjs --candidate <dir> --known-good <dir> [--report <file>]");
      process.exit(0);
    } else fail(`unknown argument: ${value}`);
  }
  if (!options.candidate || !options.knownGood) fail("--candidate and --known-good are required");
  return {
    candidate: path.resolve(options.candidate),
    knownGood: path.resolve(options.knownGood),
    report: options.report ? path.resolve(options.report) : null,
  };
}

function boundaryChecks(manifest) {
  const boundary = manifest.runtime_boundary || {};
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
  return Object.fromEntries(Object.entries(expected).map(([key, value]) => [
    key,
    boundary[key] === value,
  ]));
}

async function seedKnownGood(candidateRoot, knownGoodRoot, verification) {
  const artifactRoot = path.relative(candidateRoot, knownGoodRoot) || ".";
  const slot = {
    slot: "known-good",
    version: verification.manifest.version,
    target: verification.manifest.target,
    status: "known-good",
    signature: verification.signatureStatus,
    artifact_root: artifactRoot,
    manifest_sha256: verification.manifestSha256,
  };
  await writeSlot(candidateRoot, "current", { ...slot, slot: "known-good", status: "current-verified" });
  await writeSlot(candidateRoot, "known-good", slot);
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const candidateVerification = await verifyArtifact(options.candidate, { requireSignature: true });
  const knownGoodVerification = await verifyArtifact(options.knownGood, { requireSignature: true });
  if (candidateVerification.manifest.target !== knownGoodVerification.manifest.target) {
    fail("candidate and known-good targets differ");
  }
  if (candidateVerification.manifest.version === knownGoodVerification.manifest.version) {
    fail("candidate and known-good versions must differ");
  }
  if (path.resolve(options.candidate) === path.resolve(options.knownGood)) {
    fail("candidate and known-good artifacts must be separate directories");
  }

  const candidateBoundary = boundaryChecks(candidateVerification.manifest);
  const knownGoodBoundary = boundaryChecks(knownGoodVerification.manifest);
  if (!Object.values(candidateBoundary).every(Boolean) || !Object.values(knownGoodBoundary).every(Boolean)) {
    fail("artifact runtime boundary is not private, read-only, paper-only, and execution-disabled");
  }
  if (
    candidateVerification.manifest.sidecar?.root !== "python"
    || knownGoodVerification.manifest.sidecar?.root !== "python"
    || candidateVerification.manifest.storage?.root !== "python/.market_os"
    || knownGoodVerification.manifest.storage?.root !== "python/.market_os"
    || candidateVerification.manifest.storage?.scope !== "artifact-local"
    || knownGoodVerification.manifest.storage?.scope !== "artifact-local"
    || candidateVerification.manifest.storage?.shared_host_root !== false
    || knownGoodVerification.manifest.storage?.shared_host_root !== false
  ) {
    fail("Python sidecar storage must remain isolated under the artifact python root");
  }

  await seedKnownGood(options.candidate, options.knownGood, knownGoodVerification);
  const seeded = await inspectArtifact(options.candidate);
  let failedLaunchError = null;
  try {
    await promoteArtifact(options.candidate, { simulateLaunchFailure: true });
  } catch (error) {
    failedLaunchError = error instanceof Error ? error.message : String(error);
  }
  const restored = await inspectArtifact(options.candidate);
  if (!failedLaunchError || restored.current?.manifest_sha256 !== knownGoodVerification.manifestSha256 || restored.known_good?.manifest_sha256 !== knownGoodVerification.manifestSha256) {
    fail("failed launch did not restore current and known-good metadata");
  }

  const promoted = await promoteArtifact(options.candidate);
  if (promoted.current?.manifest_sha256 !== candidateVerification.manifestSha256 || promoted.known_good?.manifest_sha256 !== knownGoodVerification.manifestSha256) {
    fail("promotion did not move current to the candidate and preserve known-good");
  }
  const promotedInspection = await inspectArtifact(options.candidate);
  if (!promotedInspection.rollback_available) fail("promotion did not make rollback availability true");

  const rolledBack = await rollbackArtifact(options.candidate);
  if (rolledBack.current?.manifest_sha256 !== knownGoodVerification.manifestSha256) {
    fail("rollback did not restore the previous artifact");
  }
  const finalInspection = await inspectArtifact(options.candidate);
  const report = {
    schema: "market-os.u6.4-release-hardening@v1",
    milestone: "U6.4-C",
    status: "passed",
    target: candidateVerification.manifest.target,
    artifacts: {
      known_good: {
        path: path.relative(process.cwd(), options.knownGood),
        version: knownGoodVerification.manifest.version,
        manifest_sha256: knownGoodVerification.manifestSha256,
        signature: knownGoodVerification.signatureStatus,
      },
      candidate: {
        path: path.relative(process.cwd(), options.candidate),
        version: candidateVerification.manifest.version,
        manifest_sha256: candidateVerification.manifestSha256,
        signature: candidateVerification.signatureStatus,
      },
    },
    checks: {
      candidate_signed: candidateVerification.signatureStatus === "verified",
      known_good_signed: knownGoodVerification.signatureStatus === "verified",
      versions_differ: candidateVerification.manifest.version !== knownGoodVerification.manifest.version,
      failed_launch_restored_metadata: restored.current?.manifest_sha256 === knownGoodVerification.manifestSha256 && restored.known_good?.manifest_sha256 === knownGoodVerification.manifestSha256,
      promotion_current_candidate: promotedInspection.current?.manifest_sha256 === candidateVerification.manifestSha256,
      known_good_preserved: promotedInspection.known_good?.manifest_sha256 === knownGoodVerification.manifestSha256,
      rollback_available_before: promotedInspection.rollback_available,
      rollback_to_known_good: finalInspection.current?.manifest_sha256 === knownGoodVerification.manifestSha256,
      storage_isolation: candidateVerification.manifest.storage?.root === "python/.market_os"
        && knownGoodVerification.manifest.storage?.root === "python/.market_os"
        && candidateVerification.manifest.storage?.shared_host_root === false
        && knownGoodVerification.manifest.storage?.shared_host_root === false,
      boundary: candidateBoundary,
    },
    evidence: {
      seeded_current: seeded.current?.manifest_sha256 || null,
      failed_launch_error: failedLaunchError,
      final_current: finalInspection.current?.manifest_sha256 || null,
      final_known_good: finalInspection.known_good?.manifest_sha256 || null,
    },
  };
  if (options.report) {
    await fsp.mkdir(path.dirname(options.report), { recursive: true });
    await fsp.writeFile(options.report, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  }
  console.log(JSON.stringify(report, null, 2));
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});

module.exports = { boundaryChecks, parseArgs, seedKnownGood };
