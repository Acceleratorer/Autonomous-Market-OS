import "server-only";

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";

export type ReleaseMetadata = {
  version: string;
  sidecar: string;
  signature: string;
  currentSlot: string;
  knownGoodSlot: string;
  rollback: string;
};

const FALLBACK_RELEASE: ReleaseMetadata = {
  version: "0.1.0 · U6.3 local shell",
  sidecar: "Python gateway · loopback only",
  signature: "Not packaged · U6.4 pending",
  currentSlot: "Working tree",
  knownGoodSlot: "U6.3 verified local shell",
  rollback: "Pending signed release",
};

function stringValue(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function readJsonFile(file: string | undefined): Record<string, unknown> | null {
  if (!file) return null;
  try {
    const payload = JSON.parse(readFileSync(file, "utf8")) as unknown;
    return payload && typeof payload === "object" ? payload as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

export function getReleaseMetadata(): ReleaseMetadata {
  const manifestPath = process.env.MARKET_OS_RELEASE_MANIFEST;
  if (!manifestPath) return FALLBACK_RELEASE;

  try {
    const payload = JSON.parse(readFileSync(manifestPath, "utf8")) as Record<string, unknown>;
    const platform = payload.platform as Record<string, unknown> | undefined;
    const sidecar = payload.sidecar as Record<string, unknown> | undefined;
    const releaseState = payload.release_state as Record<string, unknown> | undefined;
    const slotRoot = process.env.MARKET_OS_RELEASE_SLOT_ROOT;
    const currentSlotState = readJsonFile(slotRoot ? join(slotRoot, "current.json") : undefined);
    const knownGoodSlotState = readJsonFile(slotRoot ? join(slotRoot, "known-good.json") : undefined);
    const signatureState = readJsonFile(
      process.env.MARKET_OS_RELEASE_SIGNATURE_FILE || join(dirname(manifestPath), "release-signature.json"),
    );
    const target = stringValue(payload.target, "local");
    const version = stringValue(payload.version, process.env.MARKET_OS_RELEASE_VERSION ?? "unknown");
    const signatureVerifiedByRuntime = process.env.MARKET_OS_RELEASE_SIGNATURE === "verified";
    const signature = signatureVerifiedByRuntime && signatureState?.schema === "market-os.u6.4-signature@v1"
      ? `Verified · Ed25519 · ${stringValue(signatureState.key_id, "external key")}`
      : stringValue(releaseState?.signature, process.env.MARKET_OS_RELEASE_SIGNATURE ?? "unknown");
    const currentSlot = stringValue(currentSlotState?.slot, stringValue(releaseState?.current_slot, process.env.MARKET_OS_RELEASE_CURRENT_SLOT ?? "unknown"));
    const knownGoodSlot = stringValue(knownGoodSlotState?.slot, stringValue(releaseState?.known_good_slot, process.env.MARKET_OS_RELEASE_KNOWN_GOOD_SLOT ?? "unknown"));
    const rollbackAvailable = currentSlotState?.manifest_sha256 && knownGoodSlotState?.manifest_sha256
      ? currentSlotState.manifest_sha256 !== knownGoodSlotState.manifest_sha256
      : process.env.MARKET_OS_RELEASE_ROLLBACK === "true" || releaseState?.rollback_available === true;
    const pythonRequirement = stringValue(sidecar?.requires_python, ">=3.11");
    const runtime = stringValue(platform?.os, "local");

    return {
      version: `${version} · ${target}`,
      sidecar: `Python source sidecar · ${pythonRequirement} · ${runtime}`,
      signature: signature === "unsigned" ? "Unsigned · U6.4-A artifact" : signature,
      currentSlot,
      knownGoodSlot,
      rollback: rollbackAvailable ? "Available" : "Not available · rollback gate pending",
    };
  } catch {
    return FALLBACK_RELEASE;
  }
}
