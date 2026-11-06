import { readFile } from "node:fs/promises";
import { test } from "node:test";
import assert from "node:assert/strict";
import { resolve } from "node:path";

const root = resolve(process.cwd());

async function source(relativePath: string): Promise<string> {
  return readFile(resolve(root, relativePath), "utf8");
}

test("U6.2 selects Electron without creating a native runtime", async () => {
  const [adr, contract, evidenceText] = await Promise.all([
    source("docs/decisions/ADR-0053-u6-native-platform-selection.md"),
    source("docs/U6-READ-ONLY-APP-SHELL-CONTRACT.md"),
    source("docs/evidence/u6-native-platform-selection.json"),
  ]);
  const evidence = JSON.parse(evidenceText) as Record<string, any>;

  assert.match(adr, /Select \*\*Electron\*/);
  assert.match(adr, /implementation deferred to U6\.3/);
  assert.match(adr, /disable Node\s+integration in renderers/);
  assert.match(contract, /Electron/);
  assert.match(contract, /U6\.3/);
  assert.equal(evidence.schema, "market-os.u6-native-platform-selection@v1");
  assert.equal(evidence.status, "selected-platform-implementation-deferred");
  assert.equal(evidence.decision.platform, "electron");
  assert.equal(evidence.verification.electron_dependency, false);
  assert.equal(evidence.verification.native_scaffold, false);
});

test("U6.2 keeps the native boundary local, read-only, and credential-free", async () => {
  const [adr, evidenceText] = await Promise.all([
    source("docs/decisions/ADR-0053-u6-native-platform-selection.md"),
    source("docs/evidence/u6-native-platform-selection.json"),
  ]);
  const evidence = JSON.parse(evidenceText) as Record<string, any>;

  assert.match(adr, /Python `market_os` remains authoritative/);
  assert.match(adr, /No mobile shell, provider access, credentials/);
  assert.deepEqual(evidence.boundary, {
    local_only: true,
    synthetic: true,
    paper_only: true,
    get_only: true,
    provider_requests: 0,
    credentials: false,
    mutation_routes: false,
    live_trading: false,
    connected_runtime: false,
    public_listener: false,
  });
  assert.equal(evidence.decision.transport, "loopback-http-only");
  assert.match(evidence.next_gate, /U6\.4/);
});

test("U6.2 records lifecycle, capability, packaging, and parity gates", async () => {
  const evidence = JSON.parse(
    await source("docs/evidence/u6-native-platform-selection.json"),
  ) as Record<string, any>;
  const gates = evidence.required_gates as string[];

  for (const marker of [
    "loopback-only gateway and Next.js child-process lifecycle",
    "bounded readiness handshake and descendant cleanup",
    "sandbox, context isolation, validated IPC senders",
    "same Python/API/CLI envelopes",
    "signed reproducible Windows/Linux artifacts with explicit rollback",
    "responsive and accessibility parity",
  ]) {
    assert.ok(gates.some((gate) => gate.includes(marker)), marker);
  }
});
