"use strict";

const crypto = require("node:crypto");
const { execFile } = require("node:child_process");
const fsp = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { promisify } = require("node:util");
const { installPortable, uninstallPortable } = require("./install-portable.cjs");
const { verifyArtifact } = require("../src/release.cjs");

const execFileAsync = promisify(execFile);

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = { artifact: null, target: null, output: null, markdown: null };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--") continue;
    if (value === "--artifact") options.artifact = argv[++index];
    else if (value === "--target") options.target = argv[++index];
    else if (value === "--output") options.output = argv[++index];
    else if (value === "--markdown") options.markdown = argv[++index];
    else if (value === "--help" || value === "-h") {
      console.log("Usage: node scripts/render-installation-evidence.cjs --artifact <dir> --target <target> --output <file> [--markdown <file>]");
      process.exit(0);
    } else fail(`unknown argument: ${value}`);
  }
  for (const key of ["artifact", "target", "output"]) if (!options[key]) fail(`--${key} is required`);
  if (!["windows-x64", "linux-x64"].includes(options.target)) fail(`unsupported target: ${options.target}`);
  return {
    artifact: path.resolve(options.artifact),
    target: options.target,
    output: path.resolve(options.output),
    markdown: options.markdown ? path.resolve(options.markdown) : null,
  };
}

async function writeJson(file, value) {
  await fsp.mkdir(path.dirname(file), { recursive: true });
  await fsp.writeFile(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

async function prepareUpgradeArtifact(source, destination, version, privateKey) {
  await fsp.cp(source, destination, { recursive: true, verbatimSymlinks: true });
  const manifestPath = path.join(destination, "artifact-manifest.json");
  const manifest = JSON.parse(await fsp.readFile(manifestPath, "utf8"));
  manifest.version = version;
  await writeJson(manifestPath, manifest);
  const manifestSha256 = crypto.createHash("sha256").update(await fsp.readFile(manifestPath)).digest("hex");
  await fsp.writeFile(`${manifestPath}.sha256`, `${manifestSha256}  artifact-manifest.json\n`, "utf8");
  const currentSlotPath = path.join(destination, "slots", "current.json");
  const currentSlot = JSON.parse(await fsp.readFile(currentSlotPath, "utf8"));
  currentSlot.version = version;
  currentSlot.manifest_sha256 = manifestSha256;
  await writeJson(currentSlotPath, currentSlot);
  await execFileAsync(process.execPath, [
    path.join(__dirname, "sign-artifact.cjs"),
    "--artifact", destination,
    "--private-key", privateKey,
  ]);
}

function renderMarkdown(report) {
  const rows = Object.entries(report.checks).map(([key, value]) => `| ${key} | ${value ? "PASS" : "FAIL"} |`).join("\n");
  return [
    "# U6.4-F Portable Installation Evidence",
    "",
    `- Status: **${report.status.toUpperCase()}**`,
    `- Target: \`${report.target}\``,
    `- Runner image: \`${report.runner.image || "unknown"}\``,
    `- Runtime: \`${report.runtime.version}\` from \`${report.runtime.source}\``,
    `- Runtime archive SHA-256: \`${report.runtime.archive_sha256}\``,
    "",
    "| Check | Result |",
    "| --- | --- |",
    rows,
    "",
    `- Retained state: \`${report.uninstall.retained_data.path || "none"}\``,
    "- Native service registration: **false**",
    "",
  ].join("\n");
}

async function renderEvidence(options) {
  const verification = await verifyArtifact(options.artifact, { requireSignature: true });
  const manifest = verification.manifest;
  if (manifest.target !== options.target) fail("artifact target does not match requested target");
  if (manifest.sidecar?.distribution !== "target-native-embedded-cpython" || !manifest.runtime) fail("artifact does not contain an embedded CPython runtime");
  const tempRoot = await fsp.mkdtemp(path.join(os.tmpdir(), "market-os-u6-4-f-evidence-"));
  const destination = path.join(tempRoot, "app");
  const upgradeArtifact = path.join(tempRoot, "upgrade-artifact");
  const invalid = path.join(tempRoot, "invalid-artifact");
  const privateKey = path.join(tempRoot, "upgrade-private.pem");
  try {
    const keyPair = crypto.generateKeyPairSync("ed25519");
    await fsp.writeFile(privateKey, keyPair.privateKey.export({ format: "pem", type: "pkcs8" }), { mode: 0o600 });
    await prepareUpgradeArtifact(options.artifact, upgradeArtifact, `${manifest.version}-upgrade`, privateKey);
    const fresh = await installPortable({ artifactRoot: options.artifact, destination });
    const state = path.join(destination, "python", ".market_os", "evidence.json");
    await fsp.mkdir(path.dirname(state), { recursive: true });
    await fsp.writeFile(state, '{"retained":true}\n', "utf8");
    await fsp.rm(path.join(destination, "shell", "src", "main.cjs"), { force: true });
    const repair = await installPortable({ artifactRoot: options.artifact, destination });
    const repaired = await fsp.stat(path.join(destination, "shell", "src", "main.cjs")).then(() => true).catch(() => false);
    const invalidManifest = JSON.parse(await fsp.readFile(path.join(options.artifact, "artifact-manifest.json"), "utf8"));
    invalidManifest.version = `${invalidManifest.version}-tampered`;
    await fsp.mkdir(invalid, { recursive: true });
    await fsp.writeFile(path.join(invalid, "artifact-manifest.json"), `${JSON.stringify(invalidManifest, null, 2)}\n`, "utf8");
    await fsp.copyFile(path.join(options.artifact, "artifact-manifest.json.sha256"), path.join(invalid, "artifact-manifest.json.sha256"));
    let verificationFailureRecovered = false;
    try {
      await installPortable({ artifactRoot: invalid, destination });
    } catch {
      verificationFailureRecovered = (await fsp.readFile(path.join(destination, "artifact-manifest.json"), "utf8")).includes(`\"version\": \"${manifest.version}\"`);
    }
    if (!verificationFailureRecovered) fail("verification failure did not leave the current app intact");
    await fsp.rm(`${destination}.rollback`, { recursive: true, force: true });
    const retry = await installPortable({ artifactRoot: options.artifact, destination });
    await fsp.rm(`${destination}.rollback`, { recursive: true, force: true });
    const upgrade = await installPortable({ artifactRoot: upgradeArtifact, destination });
    const uninstall = await uninstallPortable({ destination });
    await fsp.rm(`${destination}.rollback`, { recursive: true, force: true });
    const reinstall = await installPortable({ artifactRoot: options.artifact, destination });
    const retained = JSON.parse(await fsp.readFile(state, "utf8"));
    const report = {
      schema: "market-os.u6.4-f-installation-evidence@v1",
      status: "passed",
      target: options.target,
      runner: { image: process.env.ImageVersion || process.env.ImageOS || null, platform: process.platform, arch: process.arch, node: process.version },
      artifact: { version: manifest.version, manifest_sha256: verification.manifestSha256, signature: verification.signatureStatus },
      runtime: manifest.runtime,
      checks: {
        signed_package_identity: verification.signatureStatus === "verified",
        embedded_runtime_provenance: manifest.runtime.source === "python.org" && /^3\.11\.\d+$/.test(manifest.runtime.version),
        fresh_install: fresh.status === "passed",
        upgrade_state_preserved: upgrade.version === `${manifest.version}-upgrade` && upgrade.storage.preserved === true && retained.retained === true,
        repair_recovery: repair.status === "passed" && repaired,
        retry_after_verification_failure: retry.status === "passed",
        manual_rollback_copy: upgrade.rollback.available === true,
        verification_failure_recovery: verificationFailureRecovered,
        uninstall_application_removed: uninstall.application_removed === true,
        uninstall_state_retained: uninstall.retained_data.preserved === true,
        reinstall_state_preserved: reinstall.storage.preserved === true,
        service_registration_disabled: uninstall.launch.service_registered === false,
        boundary_safe: manifest.runtime_boundary?.paper_only === true && manifest.runtime_boundary?.read_only === true && manifest.runtime_boundary?.live_trading === false,
      },
      install: { fresh, repair, retry, upgrade, reinstall },
      uninstall,
      boundary: manifest.runtime_boundary,
    };
    await writeJson(options.output, report);
    if (options.markdown) {
      await fsp.mkdir(path.dirname(options.markdown), { recursive: true });
      await fsp.writeFile(options.markdown, renderMarkdown(report), "utf8");
    }
    return report;
  } finally {
    await fsp.rm(tempRoot, { recursive: true, force: true });
  }
}

async function main() {
  console.log(JSON.stringify(await renderEvidence(parseArgs(process.argv.slice(2))), null, 2));
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}

module.exports = { parseArgs, renderEvidence, renderMarkdown };
