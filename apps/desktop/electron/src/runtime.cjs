"use strict";

const { spawn } = require("node:child_process");
const fs = require("node:fs");
const net = require("node:net");
const path = require("node:path");
const { readReleaseState } = require("./release.cjs");

const LOOPBACK_HOST = "127.0.0.1";
const DEFAULT_API_PORT = 8787;
const DEFAULT_NEXT_PORT = 3000;
const DEFAULT_READY_TIMEOUT_MS = 15_000;

function parsePort(value, fallback) {
  const port = Number(value ?? fallback);
  if (!Number.isInteger(port) || port < 1024 || port > 65535) {
    throw new Error("local port must be an integer between 1024 and 65535");
  }
  return port;
}

function localUrl(port, pathname) {
  return `http://${LOOPBACK_HOST}:${port}${pathname}`;
}

function detectArtifactRoot() {
  const explicit = process.env.MARKET_OS_ARTIFACT_ROOT;
  if (explicit) return path.resolve(explicit);
  const candidate = path.resolve(__dirname, "../..");
  return fs.existsSync(path.join(candidate, "artifact-manifest.json")) ? candidate : null;
}

function readArtifactManifest(artifactRoot) {
  if (!artifactRoot) return null;
  try {
    const payload = JSON.parse(fs.readFileSync(path.join(artifactRoot, "artifact-manifest.json"), "utf8"));
    return payload && typeof payload === "object" ? payload : null;
  } catch {
    return null;
  }
}

function isPortAvailable(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.listen(port, LOOPBACK_HOST, () => {
      server.close(() => resolve(true));
    });
  });
}

function findAvailablePort(excludedPorts = []) {
  const excluded = new Set(excludedPorts);
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, LOOPBACK_HOST, () => {
      const address = server.address();
      const port = address && typeof address === "object" ? address.port : null;
      server.close((error) => {
        if (error) {
          reject(error);
        } else if (!port || excluded.has(port)) {
          findAvailablePort(excluded).then(resolve, reject);
        } else {
          resolve(port);
        }
      });
    });
  });
}

function isAllowedLoopbackUrl(value, port) {
  try {
    const url = new URL(value);
    return url.protocol === "http:"
      && url.hostname === LOOPBACK_HOST
      && url.port === String(port);
  } catch {
    return false;
  }
}

async function waitForHttp(url, { timeoutMs = DEFAULT_READY_TIMEOUT_MS, intervalMs = 100 } = {}) {
  const deadline = Date.now() + timeoutMs;
  let lastError = "not ready";
  while (Date.now() < deadline) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), Math.min(intervalMs * 4, 1000));
    try {
      const response = await fetch(url, {
        method: "GET",
        redirect: "error",
        signal: controller.signal,
      });
      if (response.ok) return;
      lastError = `HTTP ${response.status}`;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    } finally {
      clearTimeout(timer);
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error(`local service readiness timed out for ${url}: ${lastError}`);
}

function defaultSpecs({ repoRoot, pythonRoot, webRoot, apiPort, nextPort, pythonCommand }) {
  const python = process.env.MARKET_OS_PYTHON || pythonCommand || (process.platform === "win32" ? "python" : "python3");
  const nextNode = process.env.MARKET_OS_NEXT_NODE || (process.versions.electron ? "node" : process.execPath);
  const nextCommand = process.env.MARKET_OS_NEXT_COMMAND || nextNode;
  const nextCli = path.join(webRoot, "node_modules", "next", "dist", "bin", "next");
  const nextArgs = process.env.MARKET_OS_NEXT_COMMAND
    ? ["start", "--hostname", LOOPBACK_HOST, "--port", String(nextPort)]
    : [nextCli, "start", "--hostname", LOOPBACK_HOST, "--port", String(nextPort)];
  return {
    gateway: {
      command: python,
      args: ["-m", "apps.gateway", "--host", LOOPBACK_HOST, "--port", String(apiPort)],
      cwd: pythonRoot || repoRoot,
    },
    next: {
      command: nextCommand,
      args: nextArgs,
      cwd: webRoot,
    },
    cwd: repoRoot,
  };
}

function stopChild(child, graceMs = 1500) {
  if (!child || child.exitCode !== null) return Promise.resolve();
  const exited = new Promise((resolve) => child.once("exit", resolve));
  try {
    child.kill("SIGTERM");
  } catch {
    return Promise.resolve();
  }
  return Promise.race([
    exited,
    new Promise((resolve) => setTimeout(resolve, graceMs)),
  ]).then(() => {
    if (child.exitCode !== null) return;
    if (process.platform === "win32" && child.pid) {
      const killer = spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
        stdio: "ignore",
        windowsHide: true,
        shell: false,
      });
      killer.unref();
    } else if (child.pid) {
      try {
        process.kill(-child.pid, "SIGKILL");
      } catch {
        try { child.kill("SIGKILL"); } catch { /* already exited */ }
      }
    }
  });
}

class LocalRuntime {
  constructor(options = {}) {
    this.artifactRoot = options.artifactRoot || detectArtifactRoot();
    this.artifactManifest = options.artifactManifest || readArtifactManifest(this.artifactRoot);
    this.releaseState = options.releaseState || null;
    this.isPackaged = Boolean(this.artifactRoot && this.artifactManifest);
    this.repoRoot = options.repoRoot || (this.isPackaged ? this.artifactRoot : path.resolve(__dirname, "../../../.."));
    this.pythonRoot = options.pythonRoot || (this.isPackaged ? path.join(this.artifactRoot, "python") : this.repoRoot);
    this.webRoot = options.webRoot || (this.isPackaged
      ? path.join(this.artifactRoot, "web")
      : path.join(this.repoRoot, "apps", "web", "next-operator"));
    this.apiPort = parsePort(options.apiPort ?? process.env.MARKET_OS_API_PORT, DEFAULT_API_PORT);
    this.nextPort = parsePort(options.nextPort ?? process.env.MARKET_OS_NEXT_PORT, DEFAULT_NEXT_PORT);
    this.apiPortExplicit = options.apiPort !== undefined || process.env.MARKET_OS_API_PORT !== undefined;
    this.nextPortExplicit = options.nextPort !== undefined || process.env.MARKET_OS_NEXT_PORT !== undefined;
    this.readyTimeoutMs = options.readyTimeoutMs || DEFAULT_READY_TIMEOUT_MS;
    if (this.apiPort === this.nextPort) {
      throw new Error("gateway and Next.js ports must be different");
    }
    this.usesDefaultGateway = !options.gatewaySpec;
    this.usesDefaultNext = !options.nextSpec;
    const defaults = defaultSpecs({
      repoRoot: this.repoRoot,
      pythonRoot: this.pythonRoot,
      webRoot: this.webRoot,
      apiPort: this.apiPort,
      nextPort: this.nextPort,
      pythonCommand: this.artifactManifest?.sidecar?.interpreter,
    });
    this.specs = {
      gateway: options.gatewaySpec || defaults.gateway,
      next: options.nextSpec || defaults.next,
      cwd: options.cwd || defaults.cwd,
    };
    if (!this.releaseState && this.artifactRoot) {
      this.releaseStatePromise = readReleaseState(this.artifactRoot, this.artifactManifest);
    } else {
      this.releaseStatePromise = Promise.resolve(this.releaseState);
    }
    this.children = [];
    this.stopPromise = null;
  }

  start() {
    if (this.children.length) throw new Error("local runtime already started");
    return this.preparePorts().then(() => {
      this.refreshDefaultSpecs();
      return this.startChildren();
    });
  }

  async preparePorts() {
    if (!this.apiPortExplicit && !(await isPortAvailable(this.apiPort))) {
      this.apiPort = await findAvailablePort([this.nextPort]);
    }
    if (!this.nextPortExplicit && (this.apiPort === this.nextPort || !(await isPortAvailable(this.nextPort)))) {
      this.nextPort = await findAvailablePort([this.apiPort]);
    }
    if (this.apiPort === this.nextPort) {
      throw new Error("gateway and Next.js ports must be different");
    }
  }

  refreshDefaultSpecs() {
    const defaults = defaultSpecs({
      repoRoot: this.repoRoot,
      pythonRoot: this.pythonRoot,
      webRoot: this.webRoot,
      apiPort: this.apiPort,
      nextPort: this.nextPort,
      pythonCommand: this.artifactManifest?.sidecar?.interpreter,
    });
    if (this.usesDefaultGateway) this.specs.gateway = defaults.gateway;
    if (this.usesDefaultNext) this.specs.next = defaults.next;
  }

  async startChildren() {
    const releaseState = await this.releaseStatePromise;
    const storageRoot = this.artifactRoot ? path.join(this.pythonRoot, ".market_os") : null;
    const childEnv = {
      ...process.env,
      MARKET_OS_API_PORT: String(this.apiPort),
      MARKET_OS_PORT: String(this.apiPort),
      MARKET_OS_NEXT_PORT: String(this.nextPort),
      MARKET_OS_HOST: LOOPBACK_HOST,
      MARKET_OS_ARTIFACT_ROOT: this.artifactRoot || "",
      MARKET_OS_RELEASE_MANIFEST: this.artifactRoot
        ? path.join(this.artifactRoot, "artifact-manifest.json")
        : "",
      MARKET_OS_RELEASE_VERSION: this.artifactManifest?.version || "u6.3",
      MARKET_OS_RELEASE_SLOT_ROOT: this.artifactRoot ? path.join(this.artifactRoot, "slots") : "",
      MARKET_OS_RELEASE_SIGNATURE_FILE: this.artifactRoot ? path.join(this.artifactRoot, "release-signature.json") : "",
      MARKET_OS_RELEASE_SIGNATURE: releaseState?.signature || this.artifactManifest?.release_state?.signature || "not-packaged",
      MARKET_OS_RELEASE_CURRENT_SLOT: releaseState?.currentSlot || this.artifactManifest?.release_state?.current_slot || "working-tree",
      MARKET_OS_RELEASE_KNOWN_GOOD_SLOT: releaseState?.knownGoodSlot || this.artifactManifest?.release_state?.known_good_slot || "u6.3-local-shell",
      MARKET_OS_RELEASE_ROLLBACK: String(releaseState?.rollbackAvailable ?? this.artifactManifest?.release_state?.rollback_available ?? false),
      PYTHONPATH: [this.pythonRoot, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter),
    };
    if (storageRoot) childEnv.MARKET_OS_STORE_ROOT = storageRoot;
    try {
      this.children = [this.spawn(this.specs.gateway, childEnv), this.spawn(this.specs.next, childEnv)];
    } catch (error) {
      void this.stop();
      throw error;
    }
    return this.waitForReady();
  }

  spawn(spec, env) {
    if (!spec || typeof spec.command !== "string" || !Array.isArray(spec.args)) {
      throw new Error("invalid local child process specification");
    }
    const child = spawn(spec.command, spec.args, {
      cwd: spec.cwd || this.specs.cwd,
      env: { ...env, ...(spec.env || {}) },
      shell: false,
      windowsHide: true,
      detached: process.platform !== "win32",
      stdio: ["ignore", "pipe", "pipe"],
    });
    child.on("error", (error) => { child.startupError = error; });
    child.stderr?.setEncoding("utf8");
    child.stderr?.on("data", (chunk) => {
      child.stderrTail = `${child.stderrTail || ""}${chunk}`.slice(-4000);
    });
    child.stdout?.setEncoding("utf8");
    child.stdout?.on("data", (chunk) => {
      child.stdoutTail = `${child.stdoutTail || ""}${chunk}`.slice(-4000);
    });
    return child;
  }

  async waitForReady() {
    try {
      await Promise.all([
        waitForHttp(localUrl(this.apiPort, "/readyz"), { timeoutMs: this.readyTimeoutMs }),
        waitForHttp(`http://${LOOPBACK_HOST}:${this.nextPort}/healthz`, { timeoutMs: this.readyTimeoutMs }),
      ]);
    } catch (error) {
      const failures = this.children
        .filter((child) => child.startupError || child.exitCode !== null || child.signalCode)
        .map((child) => {
          const command = [child.spawnargs?.[0], ...(child.spawnargs || []).slice(1)].filter(Boolean).join(" ");
          const detail = child.startupError?.message || child.stderrTail?.trim() || `exit=${child.exitCode ?? "?"}`;
          return `${command}: ${detail}`;
        });
      if (failures.length) {
        const message = error instanceof Error ? error.message : String(error);
        throw new Error(`${message}; child failure: ${failures.join(" | ")}`);
      }
      throw error;
    }
    return { apiPort: this.apiPort, nextPort: this.nextPort };
  }

  async stop() {
    if (this.stopPromise) return this.stopPromise;
    const children = this.children;
    this.children = [];
    this.stopPromise = Promise.all(children.reverse().map((child) => stopChild(child))).then(() => undefined);
    return this.stopPromise;
  }
}

module.exports = {
  DEFAULT_API_PORT,
  DEFAULT_NEXT_PORT,
  LOOPBACK_HOST,
  LocalRuntime,
  findAvailablePort,
  isPortAvailable,
  isAllowedLoopbackUrl,
  detectArtifactRoot,
  readArtifactManifest,
  localUrl,
  parsePort,
  waitForHttp,
};
