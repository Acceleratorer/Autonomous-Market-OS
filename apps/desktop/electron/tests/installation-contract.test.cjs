"use strict";

const assert = require("node:assert/strict");
const fsp = require("node:fs/promises");
const path = require("node:path");
const test = require("node:test");

const contractPath = path.resolve(__dirname, "../../../../docs/evidence/u6-4-f-installation-contract.json");
const { parseArgs, validateContract } = require("../scripts/validate-installation-contract.cjs");

test("installation contract validator accepts the approved fixture", async () => {
  const contract = JSON.parse(await fsp.readFile(contractPath, "utf8"));
  const result = validateContract(contract);
  assert.equal(result.status, "accepted");
  assert.equal(result.implementation_authorized, true);
  assert.equal(result.open_decisions, 0);
  assert.deepEqual(result.targets, ["windows-x64", "linux-x64"]);
});

test("installation contract validator rejects authorization with a reopened decision", async () => {
  const contract = JSON.parse(await fsp.readFile(contractPath, "utf8"));
  contract.decisions[1].status = "open";
  assert.throws(
    () => validateContract(contract),
    /implementation cannot be authorized while decisions remain open or proposed/,
  );
});

test("installation contract validator rejects authorization before acceptance", async () => {
  const contract = JSON.parse(await fsp.readFile(contractPath, "utf8"));
  contract.status = "planning";
  assert.throws(
    () => validateContract(contract),
    /implementation cannot be authorized while the contract is not accepted/,
  );
});

test("installation contract validator rejects an unsafe boundary", async () => {
  const contract = JSON.parse(await fsp.readFile(contractPath, "utf8"));
  contract.boundary.live_trading = true;
  assert.throws(() => validateContract(contract), /unsafe boundary: live_trading/);
});

test("installation contract validator resolves the repository fixture by default", () => {
  assert.equal(
    parseArgs([]),
    contractPath,
  );
});
