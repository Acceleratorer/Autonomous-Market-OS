"use strict";

const fs = require("node:fs");
const fsp = require("node:fs/promises");
const crypto = require("node:crypto");
const net = require("node:net");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = { artifact: null, report: null, timeoutMs: 30_000, expectSigned: false };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--") continue;
    if (value === "--artifact") options.artifact = argv[++index];
    else if (value === "--report") options.report = argv[++index];
    else if (value === "--timeout-ms") options.timeoutMs = Number(argv[++index]);
    else if (value === "--expect-signed") options.expectSigned = true;
    else if (value === "--help" || value === "-h") {
      console.log("Usage: node scripts/smoke-artifact.cjs --artifact <dir> [--report <file>] [--expect-signed]");
      process.exit(0);
    } else fail(`unknown argument: ${value}`);
  }
  if (!options.artifact) fail("--artifact is required");
  if (!Number.isInteger(options.timeoutMs) || options.timeoutMs < 1000) fail("--timeout-ms must be at least 1000");
  return { ...options, artifact: path.resolve(options.artifact), report: options.report ? path.resolve(options.report) : null };
}

async function readJson(file) {
  return JSON.parse(await fsp.readFile(file, "utf8"));
}

async function sha256File(file) {
  const hash = crypto.createHash("sha256");
  const stream = fs.createReadStream(file);
  for await (const chunk of stream) hash.update(chunk);
  return hash.digest("hex");
}

function portAvailable(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.listen(port, "127.0.0.1", () => server.close(() => resolve(true)));
  });
}

async function freePort(excluded = []) {
  const excludedSet = new Set(excluded);
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = address && typeof address === "object" ? address.port : null;
      server.close((error) => {
        if (error) reject(error);
        else if (!port || excludedSet.has(port)) freePort(excluded).then(resolve, reject);
        else resolve(port);
      });
    });
  });
}

async function waitFor(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let lastError = "not ready";
  while (Date.now() < deadline) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 1500);
    try {
      const response = await fetch(url, { redirect: "error", signal: controller.signal });
      const body = await response.text();
      if (response.ok) return { status: response.status, body };
      lastError = `HTTP ${response.status}`;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    } finally {
      clearTimeout(timer);
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`${url} did not become ready: ${lastError}`);
}

async function waitForExit(child, timeoutMs) {
  if (child.exitCode !== null) return;
  await Promise.race([
    new Promise((resolve) => child.once("exit", resolve)),
    new Promise((resolve) => setTimeout(resolve, timeoutMs)),
  ]);
}

async function waitForPortClosed(port, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await portAvailable(port)) return true;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return false;
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const manifestPath = path.join(options.artifact, "artifact-manifest.json");
  const manifest = await readJson(manifestPath);
  const manifestDigest = await sha256File(manifestPath);
  const digestRecord = await fsp.readFile(`${manifestPath}.sha256`, "utf8");
  if (!digestRecord.startsWith(`${manifestDigest}  artifact-manifest.json`)) {
    fail("artifact manifest SHA-256 record does not match");
  }
  if (manifest.schema !== "market-os.u6.4-artifact@v1") fail("unexpected artifact manifest schema");
  if (manifest.status !== "unsigned-reproducible") fail("artifact is not marked unsigned-reproducible");
  if (manifest.runtime_boundary?.read_only !== true || manifest.runtime_boundary?.live_trading !== false) {
    fail("artifact boundary is not read-only and live-trading disabled");
  }
  const targetPlatform = manifest.target?.split("-")[0];
  const expectedPlatform = process.platform === "win32" ? "windows" : process.platform === "linux" ? "linux" : null;
  if (targetPlatform !== expectedPlatform) fail(`artifact target ${manifest.target} does not match host ${process.platform}`);

  const electronBinary = process.platform === "win32"
    ? path.join(options.artifact, "shell", "node_modules", "electron", "dist", "electron.exe")
    : path.join(options.artifact, "shell", "node_modules", "electron", "dist", "electron");
  if (!fs.existsSync(electronBinary)) fail(`Electron binary is missing: ${electronBinary}`);
  const apiPort = await freePort();
  const nextPort = await freePort([apiPort]);
  const child = spawn(electronBinary, [path.join(options.artifact, "shell"), "--disable-gpu", "--no-sandbox"], {
    cwd: options.artifact,
    env: {
      ...process.env,
      MARKET_OS_ARTIFACT_ROOT: options.artifact,
      MARKET_OS_API_PORT: String(apiPort),
      MARKET_OS_NEXT_PORT: String(nextPort),
      MARKET_OS_PYTHON: process.env.MARKET_OS_PYTHON || (process.platform === "win32" ? "python" : "python3"),
    },
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  let stderr = "";
  child.stderr?.setEncoding("utf8");
  child.stderr?.on("data", (chunk) => { stderr = `${stderr}${chunk}`.slice(-8000); });

  let checks;
  try {
    const api = await waitFor(`http://127.0.0.1:${apiPort}/readyz`, options.timeoutMs);
    const health = await waitFor(`http://127.0.0.1:${nextPort}/healthz`, options.timeoutMs);
    const overview = await waitFor(`http://127.0.0.1:${nextPort}/overview`, options.timeoutMs);
    const runtime = await waitFor(`http://127.0.0.1:${nextPort}/runtime`, options.timeoutMs);
    const boundary = {
      identity: runtime.body.includes("Release identity") && runtime.body.includes("Connected access"),
      audit: runtime.body.includes("Event stream") && runtime.body.includes("append-only local observations"),
      read_only_paper_only: overview.body.includes("paper-only")
        && overview.body.includes("no live venue or order controls")
        && runtime.body.includes("execution disabled"),
      private_loopback: runtime.body.includes("127.0.0.1"),
      storage_isolation: path.resolve(options.artifact, "python", ".market_os").startsWith(`${path.resolve(options.artifact)}${path.sep}`)
        && fs.existsSync(path.resolve(options.artifact, "python", ".market_os")),
    };
    if (!Object.values(boundary).every(Boolean)) fail("artifact boundary markers are incomplete");
    if (options.expectSigned) {
      if (!runtime.body.includes("Verified · Ed25519")) fail("runtime page did not expose verified release state");
    } else if (!runtime.body.includes("U6.4-A artifact")) {
      fail("runtime page did not expose unsigned artifact state");
    }
    checks = {
      readyz_status: api.status,
      healthz_status: health.status,
      overview_status: overview.status,
      runtime_status: runtime.status,
      boundary,
      runtime_exposes_unsigned_state: !options.expectSigned,
      runtime_exposes_signed_state: options.expectSigned,
    };
  } finally {
    child.kill("SIGINT");
    await waitForExit(child, 5_000);
    if (child.exitCode === null && child.pid) {
      if (process.platform === "win32") {
        const killer = spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], { windowsHide: true, stdio: "ignore" });
        await new Promise((resolve) => killer.once("exit", resolve));
      } else {
        child.kill("SIGKILL");
      }
      await waitForExit(child, 5_000);
    }
  }

  const cleanup = {
    api_closed: await waitForPortClosed(apiPort, 5_000),
    next_closed: await waitForPortClosed(nextPort, 5_000),
  };
  if (!cleanup.api_closed || !cleanup.next_closed) fail("packaged runtime left a loopback port open");
  const report = {
    schema: "market-os.u6.4-artifact-smoke@v1",
    status: "passed",
    artifact: options.artifact,
    target: manifest.target,
    version: manifest.version,
    host: { platform: os.platform(), arch: os.arch(), node: process.version },
    checks,
    manifest_sha256: manifestDigest,
    cleanup,
    stderr_tail: stderr.trim() || null,
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
