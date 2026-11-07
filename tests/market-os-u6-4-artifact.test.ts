import { readFile } from "node:fs/promises";
import { test } from "node:test";
import assert from "node:assert/strict";
import { resolve } from "node:path";

const root = resolve(process.cwd());

async function source(relativePath: string): Promise<string> {
  return readFile(resolve(root, relativePath), "utf8");
}

test("U6.4-A packages the renderer and Python sidecar without a second UI", async () => {
  const [packager, runtime, packageJson] = await Promise.all([
    source("apps/desktop/electron/scripts/package.cjs"),
    source("apps/desktop/electron/src/runtime.cjs"),
    source("apps/desktop/electron/package.json"),
  ]);

  const manifest = JSON.parse(packageJson) as Record<string, any>;
  assert.equal(manifest.scripts["package:unsigned"], "node scripts/package.cjs");
  assert.match(packager, /market-os\.u6\.4-artifact@v1/);
  assert.match(packager, /python-source/);
  assert.match(packager, /electron_windows/);
  assert.match(packager, /next_cli/);
  assert.match(packager, /runtime_boundary/);
  assert.match(runtime, /detectArtifactRoot/);
  assert.match(runtime, /MARKET_OS_RELEASE_MANIFEST/);
  assert.match(runtime, /pythonRoot/);
});

test("U6.4 runtime page reads release state from the artifact manifest", async () => {
  const [page, metadata] = await Promise.all([
    source("apps/web/next-operator/src/app/runtime/page.tsx"),
    source("apps/web/next-operator/src/lib/release-metadata.ts"),
  ]);

  assert.match(page, /getReleaseMetadata/);
  assert.match(page, /release\.currentSlot/);
  assert.match(metadata, /MARKET_OS_RELEASE_MANIFEST/);
  assert.match(metadata, /rollback_available/);
  assert.match(metadata, /Unsigned · U6\.4-A artifact/);
});

test("U6.4-B keeps signing and slot promotion outside the renderer", async () => {
  const [signer, slots, releaseRuntime, packageJson] = await Promise.all([
    source("apps/desktop/electron/scripts/sign-artifact.cjs"),
    source("apps/desktop/electron/scripts/release-slots.cjs"),
    source("apps/desktop/electron/src/release.cjs"),
    source("apps/desktop/electron/package.json"),
  ]);

  const manifest = JSON.parse(packageJson) as Record<string, any>;
  assert.equal(manifest.scripts["sign:artifact"], "node scripts/sign-artifact.cjs");
  assert.equal(manifest.scripts["release:promote"], "node scripts/release-slots.cjs promote");
  assert.equal(manifest.scripts["release:rollback"], "node scripts/release-slots.cjs rollback");
  assert.match(signer, /private signing key must live outside the repository and artifact directory/);
  assert.match(signer, /ed25519/);
  assert.match(slots, /simulated release launch failure/);
  assert.match(slots, /previous release slots restored/);
  assert.match(slots, /verifySlotTarget/);
  assert.match(releaseRuntime, /release-signature\.json/);
  assert.match(releaseRuntime, /manifest_sha256/);
});

test("U6.4-C packages target-native Python metadata and CI rollback evidence", async () => {
  const [packager, runtime, smoke, drill, ci, validator, reporter, archiver, archiveIndexer, cataloger, packageJson] = await Promise.all([
    source("apps/desktop/electron/scripts/package.cjs"),
    source("apps/desktop/electron/src/runtime.cjs"),
    source("apps/desktop/electron/scripts/smoke-artifact.cjs"),
    source("apps/desktop/electron/scripts/release-drill.cjs"),
    source("apps/desktop/electron/scripts/ci-release.cjs"),
    source("apps/desktop/electron/scripts/validate-ci-evidence.cjs"),
    source("apps/desktop/electron/scripts/render-ci-evidence-report.cjs"),
    source("apps/desktop/electron/scripts/archive-artifact.cjs"),
    source("apps/desktop/electron/scripts/index-portable-archives.cjs"),
    source("apps/desktop/electron/scripts/catalog-release.cjs"),
    source("apps/desktop/electron/package.json"),
  ]);

  const manifest = JSON.parse(packageJson) as Record<string, any>;
  assert.equal(manifest.scripts["release:drill"], "node scripts/release-drill.cjs");
  assert.equal(manifest.scripts["release:ci"], "node scripts/ci-release.cjs");
  assert.equal(manifest.scripts["release:validate"], "node scripts/validate-ci-evidence.cjs");
  assert.equal(manifest.scripts["release:report"], "node scripts/render-ci-evidence-report.cjs");
  assert.equal(manifest.scripts["release:archive"], "node scripts/archive-artifact.cjs");
  assert.equal(manifest.scripts["release:index"], "node scripts/index-portable-archives.cjs");
  assert.equal(manifest.scripts["release:catalog"], "node scripts/catalog-release.cjs");
  assert.match(packager, /target-native-source/);
  assert.match(packager, /python\/\.market_os/);
  assert.match(packager, /--version/);
  assert.match(runtime, /sidecar\?\.interpreter/);
  assert.match(runtime, /MARKET_OS_STORE_ROOT/);
  assert.match(smoke, /read_only_paper_only/);
  assert.match(smoke, /storage_isolation/);
  assert.match(smoke, /append-only local observations/);
  assert.match(drill, /rollback_available_before/);
  assert.match(drill, /failed_launch_restored_metadata/);
  assert.match(ci, /windows-x64/);
  assert.match(ci, /linux-x64/);
  assert.match(ci, /release-drill\.json/);
  assert.match(validator, /market-os\.u7-a-ci-evidence-validation@v1/);
  assert.match(validator, /verifyArtifact/);
  assert.match(validator, /rollback_available_before/);
  assert.match(reporter, /market-os\.u7-b-release-evidence-report@v1/);
  assert.match(reporter, /release-evidence-report\.md/);
  assert.match(archiver, /market-os\.u7-c-portable-archive@v1/);
  assert.match(archiver, /python\/\.market_os/);
  assert.match(archiver, /verifyArtifact/);
  assert.match(archiveIndexer, /market-os\.u7-d-portable-archive-index@v1/);
  assert.match(archiveIndexer, /archive_hashes_match_reports/);
  assert.match(archiveIndexer, /mutable_sidecar_state_excluded/);
  assert.match(archiveIndexer, /sha256File/);
  assert.match(cataloger, /market-os\.u7-e-cross-target-release-catalog@v1/);
  assert.match(cataloger, /boundaries_consistent/);
  assert.match(cataloger, /archive_hashes_unique/);
});
