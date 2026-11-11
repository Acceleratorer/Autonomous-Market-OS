"use strict";

const fsp = require("node:fs/promises");
const path = require("node:path");
const { validateCatalog } = require("./render-release-catalog-report.cjs");

const TARGETS = ["windows-x64", "linux-x64"];
const ROLES = ["known-good", "candidate"];
const ROUTES = ["readyz", "healthz", "overview", "runtime"];
const DRILL_CHECKS = [
  "candidate_signed",
  "known_good_signed",
  "versions_differ",
  "failed_launch_restored_metadata",
  "promotion_current_candidate",
  "known_good_preserved",
  "rollback_available_before",
  "rollback_to_known_good",
  "storage_isolation",
];
const SAFE_BOUNDARY = {
  loopback_only: true,
  synthetic: true,
  paper_only: true,
  read_only: true,
  credentials: false,
  provider_requests: 0,
  mutation_routes: false,
  live_trading: false,
};

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = { windows: null, linux: null, catalog: null, markdown: null, json: null };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--") continue;
    if (value === "--windows") options.windows = argv[++index];
    else if (value === "--linux") options.linux = argv[++index];
    else if (value === "--catalog") options.catalog = argv[++index];
    else if (value === "--markdown") options.markdown = argv[++index];
    else if (value === "--json") options.json = argv[++index];
    else if (value === "--help" || value === "-h") {
      console.log("Usage: node scripts/audit-release-drift.cjs --windows <evidence-dir> --linux <evidence-dir> --catalog <catalog.json> [--markdown <file>] [--json <file>]");
      process.exit(0);
    } else fail(`unknown argument: ${value}`);
  }
  if (!options.windows || !options.linux || !options.catalog) fail("--windows, --linux, and --catalog are required");
  const root = path.dirname(path.resolve(options.catalog));
  return {
    windows: path.resolve(options.windows),
    linux: path.resolve(options.linux),
    catalog: path.resolve(options.catalog),
    markdown: path.resolve(options.markdown || path.join(root, "release-evidence-drift.md")),
    json: path.resolve(options.json || path.join(root, "release-evidence-drift.json")),
  };
}

async function readJson(file) {
  try {
    return JSON.parse(await fsp.readFile(file, "utf8"));
  } catch {
    return null;
  }
}

function stable(value) {
  return JSON.stringify(value);
}

function addTargetDrift(drifts, target, code, filePath, observed, expected) {
  drifts.push({ code, path: filePath, target, observed: observed ?? null, expected: expected ?? null });
}

function addGlobalDrift(drifts, code, filePath, windows, linux) {
  drifts.push({ code, path: filePath, windows: windows ?? null, linux: linux ?? null });
}

function checkBoundary(boundary) {
  if (!boundary || typeof boundary !== "object") return false;
  return Object.entries(SAFE_BOUNDARY).every(([key, expected]) => boundary[key] === expected);
}

function checkBoundaryChecks(checks) {
  if (!checks || typeof checks !== "object") return false;
  return Object.keys(SAFE_BOUNDARY).every((key) => checks[key] === true);
}

function artifactByRole(list, role) {
  return Array.isArray(list) ? list.find((artifact) => artifact?.role === role) : null;
}

function rawBoundaryValues(evidence) {
  if (!evidence || typeof evidence !== "object") return null;
  if (evidence.boundary && typeof evidence.boundary === "object" && evidence.boundary.values && typeof evidence.boundary.values === "object") {
    return evidence.boundary.values;
  }
  return evidence.boundary || null;
}

async function loadTarget(root, target, drifts) {
  const files = {};
  for (const name of [
    "ci-evidence.json",
    "ci-evidence-validation.json",
    "release-evidence-report.json",
    "portable-archive-index.json",
    "release-drill.json",
  ]) {
    files[name] = await readJson(path.join(root, name));
    if (!files[name]) addTargetDrift(drifts, target, "missing_input", name, null, "readable JSON");
  }
  const { "ci-evidence.json": evidence, "ci-evidence-validation.json": validation, "release-evidence-report.json": releaseReport, "portable-archive-index.json": index, "release-drill.json": drill } = files;
  const summary = { target, root: path.basename(root), artifacts: {}, boundary: validation?.checks?.boundary || null, checks: {} };

  const required = [
    [evidence, "market-os.u6.4-ci-evidence@v1", "ci-evidence.json", true],
    [validation, "market-os.u7-a-ci-evidence-validation@v1", "ci-evidence-validation.json", true],
    [releaseReport, "market-os.u7-b-release-evidence-report@v1", "release-evidence-report.json", true],
    [index, "market-os.u7-d-portable-archive-index@v1", "portable-archive-index.json", true],
    [drill, "market-os.u6.4-release-hardening@v1", "release-drill.json", true],
  ];
  for (const [value, schema, filePath, targetRequired] of required) {
    if (value?.schema !== schema) addTargetDrift(drifts, target, "schema_mismatch", filePath, value?.schema, schema);
    if (value?.status !== "passed") addTargetDrift(drifts, target, "status_not_passed", filePath, value?.status, "passed");
    if (targetRequired && value?.target !== target) addTargetDrift(drifts, target, "target_mismatch", `${filePath}.target`, value?.target, target);
  }
  if (!checkBoundary(summary.boundary)) addTargetDrift(drifts, target, "unsafe_boundary", "ci-evidence-validation.json.checks.boundary", summary.boundary, SAFE_BOUNDARY);
  const rawBoundary = rawBoundaryValues(evidence);
  if (stable(rawBoundary) !== stable(summary.boundary)) {
    addTargetDrift(drifts, target, "boundary_source_mismatch", "ci-evidence.json.boundary.values", rawBoundary, summary.boundary);
  }
  if (evidence?.checks?.target_native_build !== true) {
    addTargetDrift(drifts, target, "target_native_build_failed", "ci-evidence.json.checks.target_native_build", evidence?.checks?.target_native_build, true);
  }
  if (!checkBoundaryChecks(evidence?.boundary?.checks)) {
    addTargetDrift(drifts, target, "boundary_check_failed", "ci-evidence.json.boundary.checks", evidence?.boundary?.checks, "all true");
  }
  if (releaseReport?.boundary && stable(releaseReport.boundary) !== stable(summary.boundary)) {
    addTargetDrift(drifts, target, "boundary_source_mismatch", "release-evidence-report.json.boundary", releaseReport.boundary, summary.boundary);
  }
  if (releaseReport?.promotion_rollback && stable(releaseReport.promotion_rollback) !== stable(validation?.checks?.promotion_rollback)) {
    addTargetDrift(drifts, target, "promotion_source_mismatch", "release-evidence-report.json.promotion_rollback", releaseReport.promotion_rollback, validation?.checks?.promotion_rollback);
  }
  if (stable(index?.checks?.boundary) !== stable(summary.boundary)) {
    addTargetDrift(drifts, target, "boundary_source_mismatch", "portable-archive-index.json.checks.boundary", index?.checks?.boundary, summary.boundary);
  }

  for (const role of ROLES) {
    const key = role === "known-good" ? "known_good" : "candidate";
    const validated = validation?.artifacts?.[key];
    const raw = evidence?.artifacts?.[key];
    const reported = artifactByRole(releaseReport?.artifacts, role);
    const indexed = artifactByRole(index?.artifacts, role);
    summary.artifacts[role] = {
      version: validated?.version || null,
      manifest_sha256: validated?.manifest_sha256 || null,
      archive_sha256: indexed?.archive_sha256 || null,
      signature: validated?.signature || null,
    };
    if (!validated?.version || !validated?.manifest_sha256) {
      addTargetDrift(drifts, target, "artifact_missing", `validation.artifacts.${key}`, validated, "version and manifest_sha256");
      continue;
    }
    if (raw?.version !== validated.version) {
      addTargetDrift(drifts, target, "raw_artifact_version_mismatch", `ci-evidence.json.artifacts.${key}.version`, raw?.version, validated.version);
    }
    const drilled = drill?.artifacts?.[key];
    if (drilled?.version !== validated.version || drilled?.manifest_sha256 !== validated.manifest_sha256 || drilled?.signature !== "verified") {
      addTargetDrift(drifts, target, "drill_artifact_mismatch", `release-drill.json.artifacts.${key}`, drilled, {
        version: validated.version,
        manifest_sha256: validated.manifest_sha256,
        signature: "verified",
      });
    }
    if (reported?.version !== validated.version || reported?.manifest_sha256 !== validated.manifest_sha256) {
      addTargetDrift(drifts, target, "manifest_hash_mismatch", `release-evidence-report.json.artifacts.${role}`, reported, validated);
    }
    if (reported?.signature !== "verified" || validated.signature !== "verified") {
      addTargetDrift(drifts, target, "signature_unverified", `artifacts.${role}.signature`, { validation: validated.signature, report: reported?.signature }, "verified");
    }
    if (indexed?.version !== validated.version || indexed?.manifest_sha256 !== validated.manifest_sha256) {
      addTargetDrift(drifts, target, "index_manifest_mismatch", `portable-archive-index.json.artifacts.${role}`, indexed, validated);
    }
    const smoke = await readJson(path.join(root, `smoke-${validated.version}.json`));
    if (!smoke) {
      addTargetDrift(drifts, target, "missing_input", `smoke-${validated.version}.json`, null, "readable JSON");
    } else {
      if (smoke.schema !== "market-os.u6.4-artifact-smoke@v1" || smoke.status !== "passed" || smoke.target !== target || smoke.version !== validated.version) {
        addTargetDrift(drifts, target, "smoke_identity_mismatch", `smoke-${validated.version}.json`, { schema: smoke.schema, status: smoke.status, target: smoke.target, version: smoke.version }, { schema: "market-os.u6.4-artifact-smoke@v1", status: "passed", target, version: validated.version });
      }
      if (smoke.manifest_sha256 !== validated.manifest_sha256) addTargetDrift(drifts, target, "smoke_manifest_mismatch", `smoke-${validated.version}.json.manifest_sha256`, smoke.manifest_sha256, validated.manifest_sha256);
      for (const route of ROUTES) {
        if (smoke.checks?.[`${route}_status`] !== 200) addTargetDrift(drifts, target, "smoke_route_failed", `smoke-${validated.version}.json.checks.${route}_status`, smoke.checks?.[`${route}_status`], 200);
      }
      if (smoke.cleanup?.api_closed !== true || smoke.cleanup?.next_closed !== true) addTargetDrift(drifts, target, "smoke_cleanup_failed", `smoke-${validated.version}.json.cleanup`, smoke.cleanup, { api_closed: true, next_closed: true });
    }
  }
  if (summary.artifacts["known-good"].version === summary.artifacts.candidate.version) addTargetDrift(drifts, target, "role_versions_invalid", "artifacts", summary.artifacts, "known-good and candidate versions differ");
  for (const key of DRILL_CHECKS) if (drill?.checks?.[key] !== true) addTargetDrift(drifts, target, "promotion_rollback_failed", `release-drill.json.checks.${key}`, drill?.checks?.[key], true);
  if (!checkBoundaryChecks(drill?.checks?.boundary)) {
    addTargetDrift(drifts, target, "boundary_check_failed", "release-drill.json.checks.boundary", drill?.checks?.boundary, "all true");
  }
  for (const key of ["archive_hashes_match_reports", "manifests_match_validation", "signatures_verified", "mutable_sidecar_state_excluded"]) {
    if (index?.checks?.[key] !== true) addTargetDrift(drifts, target, "archive_index_check_failed", `portable-archive-index.json.checks.${key}`, index?.checks?.[key], true);
  }
  summary.checks = {
    bundle_present: required.every(([value]) => Boolean(value)),
    artifacts_valid: ROLES.every((role) => Boolean(summary.artifacts[role].version && summary.artifacts[role].manifest_sha256)),
    signatures_verified: ROLES.every((role) => summary.artifacts[role].signature === "verified"),
    manifest_hashes_match: !drifts.some((entry) => entry.target === target && ["manifest_hash_mismatch", "index_manifest_mismatch", "smoke_manifest_mismatch"].includes(entry.code)),
    smoke_routes_complete: !drifts.some((entry) => entry.target === target && ["smoke_route_failed", "smoke_identity_mismatch", "smoke_cleanup_failed", "smoke_manifest_mismatch"].includes(entry.code)),
    promotion_metadata_consistent: DRILL_CHECKS.every((key) => drill?.checks?.[key] === true),
    boundary_safe: checkBoundary(summary.boundary),
  };
  return summary;
}

function compareTargets(summaries, drifts) {
  const [windows, linux] = summaries;
  const checks = {
    windows_bundle_present: windows.checks.bundle_present,
    linux_bundle_present: linux.checks.bundle_present,
    release_versions_shared: true,
    candidate_current_roles_valid: windows.checks.artifacts_valid && linux.checks.artifacts_valid,
    manifest_hashes_match: windows.checks.manifest_hashes_match && linux.checks.manifest_hashes_match,
    signatures_verified: windows.checks.signatures_verified && linux.checks.signatures_verified,
    smoke_routes_complete: windows.checks.smoke_routes_complete && linux.checks.smoke_routes_complete,
    promotion_metadata_consistent: windows.checks.promotion_metadata_consistent && linux.checks.promotion_metadata_consistent,
    rollback_metadata_consistent: windows.checks.promotion_metadata_consistent && linux.checks.promotion_metadata_consistent,
    boundaries_consistent: stable(windows.boundary) === stable(linux.boundary) && checkBoundary(windows.boundary) && checkBoundary(linux.boundary),
  };
  for (const role of ROLES) {
    const left = windows.artifacts[role];
    const right = linux.artifacts[role];
    if (left.version !== right.version) {
      checks.release_versions_shared = false;
      addGlobalDrift(drifts, "release_version_mismatch", `artifacts.${role}.version`, left.version, right.version);
    }
  }
  if (!checks.boundaries_consistent) addGlobalDrift(drifts, "boundary_mismatch", "checks.boundary", windows.boundary, linux.boundary);
  if (!checks.manifest_hashes_match) checks.manifest_hashes_match = false;
  return checks;
}

function renderMarkdown(report) {
  const rows = report.targets.map((target) => {
    const summary = report.target_summaries[target];
    return `| ${target} | ${summary.artifacts["known-good"].version || "—"} | ${summary.artifacts.candidate.version || "—"} | ${summary.checks.signatures_verified ? "PASS" : "FAIL"} | ${summary.checks.smoke_routes_complete ? "PASS" : "FAIL"} | ${summary.checks.promotion_metadata_consistent ? "PASS" : "FAIL"} |`;
  });
  const checks = Object.entries(report.checks).map(([key, value]) => `| ${key} | ${value ? "PASS" : "FAIL"} |`);
  const drifts = report.drift.length === 0 ? "| — | — | — |\n" : report.drift.map((entry) => `| ${entry.code} | ${entry.path} | ${entry.target || "windows/linux"} |`).join("\n");
  return [
    "# U7-M Release Evidence Drift Audit",
    "",
    `- Status: **${report.status.toUpperCase()}**`,
    `- Drift count: **${report.drift_count}**`,
    "- Scope: same-run Windows/Linux CI evidence provenance and shared-boundary consistency",
    "- Target-specific manifest/archive hash differences are recorded as expected variance.",
    "",
    "## Target snapshots",
    "",
    "| Target | Known-good | Candidate | Signatures | Smoke | Promotion/rollback |",
    "| --- | --- | --- | --- | --- | --- |",
    rows.join("\n"),
    "",
    "## Checks",
    "",
    "| Check | Result |",
    "| --- | --- |",
    checks.join("\n"),
    "",
    "## Drift",
    "",
    "| Code | Path | Target |",
    "| --- | --- | --- |",
    drifts,
    "",
    "## Boundary",
    "",
    "| Boundary | Value |",
    "| --- | --- |",
    Object.entries(report.boundary || {}).map(([key, value]) => `| ${key} | ${value} |`).join("\n"),
    "",
    "Generated from U6.4-C/U7-A/U7-B/U7-D target evidence and the U7-E catalog.",
    "",
  ].join("\n");
}

async function auditDrift(options) {
  const drifts = [];
  const summaries = await Promise.all(TARGETS.map((target) => loadTarget(options[target.split("-")[0]], target, drifts)));
  const catalog = await readJson(options.catalog);
  if (!catalog) addGlobalDrift(drifts, "missing_input", "cross-target-release-catalog.json", null, "readable JSON");
  else {
    try { validateCatalog(catalog); } catch (error) { addGlobalDrift(drifts, "catalog_invalid", "cross-target-release-catalog.json", error.message, "validated U7-E catalog"); }
    for (const target of TARGETS) {
      const summary = summaries.find((entry) => entry.target === target);
      for (const role of ROLES) {
        const artifact = catalog.artifacts?.find((entry) => entry.target === target && entry.role === role);
        if (!artifact || artifact.version !== summary.artifacts[role].version || artifact.manifest_sha256 !== summary.artifacts[role].manifest_sha256) {
          addTargetDrift(drifts, target, "catalog_artifact_mismatch", `catalog.artifacts.${role}`, artifact, summary.artifacts[role]);
        }
      }
    }
  }
  const checks = compareTargets(summaries, drifts);
  const boundary = summaries[0].boundary || null;
  const report = {
    schema: "market-os.u7-m-release-evidence-drift@v1",
    milestone: "U7-M",
    status: drifts.length === 0 ? "passed" : "failed",
    targets: TARGETS,
    release_versions: ROLES.map((role) => summaries[0].artifacts[role].version).filter(Boolean),
    checks,
    boundary,
    target_summaries: Object.fromEntries(summaries.map((summary) => [summary.target, summary])),
    expected_target_variance: summaries.flatMap((summary) => ROLES.map((role) => ({ target: summary.target, role, manifest_sha256: summary.artifacts[role].manifest_sha256, archive_sha256: summary.artifacts[role].archive_sha256 }))),
    drift: drifts.sort((left, right) => `${left.code}:${left.path}:${left.target || ""}`.localeCompare(`${right.code}:${right.path}:${right.target || ""}`)),
    drift_count: drifts.length,
    implementation: "So sánh provenance raw-to-derived trong từng target và các invariant dùng chung giữa Windows/Linux.",
    deferred: ["U5.5 owner-VM promotion", "embedded Python/native installer", "mobile", "credentials/providers", "mutation routes", "live execution"],
    next_gate: "Selective local U7 evaluation or owner-VM U5.5 evidence when VM/access exists.",
  };
  if (options.markdown) {
    await fsp.mkdir(path.dirname(options.markdown), { recursive: true });
    await fsp.writeFile(options.markdown, renderMarkdown(report), "utf8");
  }
  if (options.json) {
    await fsp.mkdir(path.dirname(options.json), { recursive: true });
    await fsp.writeFile(options.json, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  }
  return report;
}

async function main() {
  const report = await auditDrift(parseArgs(process.argv.slice(2)));
  console.log(JSON.stringify({ schema: report.schema, status: report.status, drift_count: report.drift_count }, null, 2));
  if (report.status !== "passed") process.exitCode = 1;
}

if (require.main === module) main().catch((error) => { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; });

module.exports = { auditDrift, checkBoundary, parseArgs, renderMarkdown };
