"use strict";

const fs = require("node:fs");
const path = require("node:path");

const DEFAULT_FILE = path.resolve(__dirname, "../../../../docs/evidence/u6-4-f-installation-contract.json");
const REQUIRED_BOUNDARY = {
  synthetic: true,
  paper_only: true,
  read_only: true,
  loopback_only: true,
  credentials: false,
  provider_requests: 0,
  mutation_routes: false,
  live_trading: false,
  connected_runtime: false,
};

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  let file = DEFAULT_FILE;
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--") continue;
    if (value === "--file") {
      file = path.resolve(argv[++index] || "");
    } else if (value === "--help" || value === "-h") {
      console.log("Usage: node scripts/validate-installation-contract.cjs [--file <json>]");
      process.exit(0);
    } else {
      fail(`unknown argument: ${value}`);
    }
  }
  return file;
}

function readContract(file) {
  let raw;
  try {
    raw = fs.readFileSync(file, "utf8");
  } catch (error) {
    fail(`contract is unreadable: ${error instanceof Error ? error.message : String(error)}`);
  }
  try {
    return JSON.parse(raw);
  } catch (error) {
    fail(`contract is not valid JSON: ${error instanceof Error ? error.message : String(error)}`);
  }
}

function validateContract(contract) {
  if (contract?.schema !== "market-os.u6.4-installation-contract@v1") {
    fail("unexpected installation contract schema");
  }
  if (!contract?.status || !["planning", "accepted"].includes(contract.status)) {
    fail("status must be planning or accepted");
  }
  if (!Array.isArray(contract.decisions) || contract.decisions.length === 0) {
    fail("decisions must be a non-empty array");
  }
  const openDecisions = contract.decisions.filter((decision) =>
    typeof decision?.status !== "string" ||
    decision.status === "open" ||
    decision.status.includes("open") ||
    decision.status.includes("proposed"),
  );
  if (contract.implementation_authorized === true && openDecisions.length > 0) {
    fail("implementation cannot be authorized while decisions remain open or proposed");
  }
  if (contract.implementation_authorized === true && contract.status !== "accepted") {
    fail("implementation cannot be authorized while the contract is not accepted");
  }
  for (const [key, expected] of Object.entries(REQUIRED_BOUNDARY)) {
    if (contract.boundary?.[key] !== expected) fail(`unsafe boundary: ${key}`);
  }
  const targets = contract.baseline?.targets;
  if (!Array.isArray(targets) || !targets.includes("windows-x64") || !targets.includes("linux-x64")) {
    fail("baseline targets must include windows-x64 and linux-x64");
  }
  for (const key of ["artifact_contract", "preflight_contract", "simulation_contract", "python_distribution", "python_requirement", "storage_root"]) {
    if (typeof contract.baseline?.[key] !== "string" || contract.baseline[key].length === 0) {
      fail(`baseline.${key} is required`);
    }
  }
  if (!Array.isArray(contract.required_evidence) || contract.required_evidence.length === 0) {
    fail("required_evidence must be a non-empty array");
  }
  if (typeof contract.next_gate !== "string" || contract.next_gate.length === 0) {
    fail("next_gate is required");
  }
  if (contract.implementation_authorized === true) {
    const accepted = contract.accepted || {};
    for (const key of [
      "package_formats",
      "install_scope",
      "elevation",
      "python_provenance",
      "runtime_root",
      "runtime_manifest",
      "launch_model",
      "service_registration",
      "rollback_strategy",
      "uninstall_policy",
    ]) {
      if (typeof accepted[key] !== "string" || accepted[key].length === 0) fail(`accepted.${key} is required`);
    }
  }
  return {
    schema: contract.schema,
    status: contract.status,
    implementation_authorized: contract.implementation_authorized === true,
    open_decisions: openDecisions.length,
    required_evidence: contract.required_evidence.length,
    targets,
    boundary: contract.boundary,
  };
}

function main() {
  const file = parseArgs(process.argv.slice(2));
  const result = validateContract(readContract(file));
  console.log(JSON.stringify({ status: "passed", file: path.relative(process.cwd(), file), ...result }, null, 2));
}

if (require.main === module) {
  try {
    main();
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}

module.exports = { parseArgs, validateContract };
