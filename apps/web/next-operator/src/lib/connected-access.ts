import "server-only";

import { createHmac, randomUUID } from "node:crypto";
import { headers } from "next/headers";

const CONNECTED_MODE = new Set(["1", "true"]);
const OWNER_SUBJECT_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._@:+-]{0,191}$/;
const ALLOWED_PORTFOLIO_ID = "paper-main";
const PRINCIPAL_VERSION = "market-os.u5-5.principal@v1";
const PRINCIPAL_ISSUER = "tailscale-serve";
const PRINCIPAL_AUDIENCE = "market-os-python";
const PRINCIPAL_METHOD = "tailscale-serve-v1";
const SESSION_TTL_SECONDS = 15 * 60;

export class ConnectedAccessError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConnectedAccessError";
  }
}

export type ConnectedAccessConfig = {
  ownerSubject: string;
  tailnetHostname: string;
  assertionSecret: string;
};

export function isConnectedMode(): boolean {
  return CONNECTED_MODE.has((process.env.MARKET_OS_U55_MODE ?? "").trim().toLowerCase());
}

export function getAllowedPortfolioId(): string {
  return ALLOWED_PORTFOLIO_ID;
}

export function getConnectedConfig(): ConnectedAccessConfig {
  if (!isConnectedMode()) {
    throw new ConnectedAccessError("connected access is disabled");
  }
  const ownerSubject = process.env.MARKET_OS_TAILSCALE_OWNER_LOGIN ?? "";
  const tailnetHostname = process.env.MARKET_OS_TAILSCALE_HOSTNAME ?? "";
  const assertionSecret = process.env.MARKET_OS_INTERNAL_ASSERTION_SECRET ?? "";
  if (!OWNER_SUBJECT_PATTERN.test(ownerSubject)) {
    throw new ConnectedAccessError("connected owner identity is not configured");
  }
  if (!/^[A-Za-z0-9][A-Za-z0-9.-]{0,253}$/.test(tailnetHostname)) {
    throw new ConnectedAccessError("connected tailnet hostname is not configured");
  }
  if (assertionSecret.length < 32) {
    throw new ConnectedAccessError("connected assertion secret is not configured");
  }
  if ((process.env.MARKET_OS_ALLOWED_PORTFOLIO_ID ?? ALLOWED_PORTFOLIO_ID) !== ALLOWED_PORTFOLIO_ID) {
    throw new ConnectedAccessError("connected portfolio allowlist is invalid");
  }
  return { ownerSubject, tailnetHostname, assertionSecret };
}

function base64Url(value: string): string {
  return Buffer.from(value, "utf8").toString("base64url");
}

export async function getInternalPrincipalHeaders(): Promise<Record<string, string>> {
  if (!isConnectedMode()) return {};

  const config = getConnectedConfig();
  const requestHeaders = await headers();
  const subject = requestHeaders.get("x-market-os-verified-subject");
  if (subject !== config.ownerSubject) {
    throw new ConnectedAccessError("connected subject is not verified");
  }

  const issuedAt = Math.floor(Date.now() / 1000);
  const payload = {
    assertion_method: PRINCIPAL_METHOD,
    audience: PRINCIPAL_AUDIENCE,
    expires_at: issuedAt + SESSION_TTL_SECONDS,
    issued_at: issuedAt,
    issuer: PRINCIPAL_ISSUER,
    jti: randomUUID().replaceAll("-", ""),
    subject,
    version: PRINCIPAL_VERSION,
  };
  const encoded = base64Url(JSON.stringify(payload));
  const signature = createHmac("sha256", config.assertionSecret)
    .update(encoded, "ascii")
    .digest("hex");
  return {
    "X-Market-OS-Principal": encoded,
    "X-Market-OS-Principal-Signature": signature,
  };
}
