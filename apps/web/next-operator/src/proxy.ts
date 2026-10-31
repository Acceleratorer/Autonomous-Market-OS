import { randomUUID } from "node:crypto";
import { NextResponse, type NextRequest } from "next/server";

const CONNECTED_MODE = new Set(["1", "true"]);
const ALLOWED_PORTFOLIO_ID = "paper-main";
const OWNER_SUBJECT_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._@:+-]{0,191}$/;

function isConnectedMode(): boolean {
  return CONNECTED_MODE.has((process.env.MARKET_OS_U55_MODE ?? "").trim().toLowerCase());
}

function connectedDenied(status: number): NextResponse {
  return new NextResponse("connected access denied", {
    status,
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": "text/plain; charset=utf-8",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

function connectedRouteAllowed(pathname: string): boolean {
  if (pathname.startsWith("/_next/") || pathname === "/favicon.ico") return true;
  if (pathname === "/" || pathname === `/portfolios/${ALLOWED_PORTFOLIO_ID}`) return true;
  return pathname.startsWith(`/portfolios/${ALLOWED_PORTFOLIO_ID}/`);
}

export function proxy(request: NextRequest) {
  if (isConnectedMode()) {
    if (request.nextUrl.pathname === "/healthz" && request.method === "GET") {
      return NextResponse.next();
    }
    const configuredSubject = process.env.MARKET_OS_TAILSCALE_OWNER_LOGIN ?? "";
    const configuredHostname = process.env.MARKET_OS_TAILSCALE_HOSTNAME ?? "";
    const requestHostname = (request.headers.get("host") ?? "").split(":")[0].toLowerCase();
    const tailscaleSubject = request.headers.get("tailscale-user-login") ?? "";
    if (
      request.method !== "GET"
      && request.method !== "HEAD"
    ) {
      return connectedDenied(405);
    }
    if (
      !OWNER_SUBJECT_PATTERN.test(configuredSubject)
      || !/^[A-Za-z0-9][A-Za-z0-9.-]{0,253}$/.test(configuredHostname)
      || requestHostname !== configuredHostname.toLowerCase()
      || tailscaleSubject !== configuredSubject
      || !connectedRouteAllowed(request.nextUrl.pathname)
    ) {
      return connectedDenied(403);
    }
  }

  const nonce = Buffer.from(randomUUID()).toString("base64");
  const isDevelopment = process.env.NODE_ENV === "development";
  const contentSecurityPolicy = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDevelopment ? " 'unsafe-eval'" : ""}`,
    `style-src 'self' 'nonce-${nonce}'`,
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");

  const requestHeaders = new Headers();
  for (const name of [
    "accept",
    "accept-language",
    "user-agent",
    "referer",
    "rsc",
    "next-router-prefetch",
    "purpose",
  ]) {
    const value = request.headers.get(name);
    if (value !== null) requestHeaders.set(name, value);
  }
  requestHeaders.set("x-nonce", nonce);
  if (isConnectedMode()) {
    requestHeaders.set(
      "x-market-os-verified-subject",
      process.env.MARKET_OS_TAILSCALE_OWNER_LOGIN ?? "",
    );
  }
  requestHeaders.set("Content-Security-Policy", contentSecurityPolicy);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", contentSecurityPolicy);
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("Referrer-Policy", "no-referrer");
  response.headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  if (isConnectedMode()) response.headers.set("Cache-Control", "no-store");
  return response;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico).*)",
    "/_next/static/:path*",
    "/_next/image",
    "/favicon.ico",
  ],
};
