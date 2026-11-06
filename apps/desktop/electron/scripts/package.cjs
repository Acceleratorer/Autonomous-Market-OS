"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const fsp = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");

const ELECTRON_ROOT = path.resolve(__dirname, "..");
const REPO_ROOT = path.resolve(ELECTRON_ROOT, "../../..");
const WEB_ROOT = path.join(REPO_ROOT, "apps", "web", "next-operator");
const PYTHON_ROOT = path.join(REPO_ROOT, "market_os");

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const options = {
    output: null,
    target: process.platform === "win32" ? "windows-x64" : "linux-x64",
    version: null,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--") {
      continue;
    } else if (value === "--output") {
      options.output = argv[++index];
    } else if (value === "--target") {
      options.target = argv[++index];
    } else if (value === "--version") {
      options.version = argv[++index];
    } else if (value === "--help" || value === "-h") {
      console.log("Usage: node scripts/package.cjs [--output <dir>] [--target windows-x64|linux-x64] [--version <version>]");
      process.exit(0);
    } else {
      fail(`unknown argument: ${value}`);
    }
  }
  if (!options.output) {
    options.output = path.join(REPO_ROOT, "output", "u6.4", `market-os-${options.target}`);
  }
  if (!["windows-x64", "linux-x64"].includes(options.target)) {
    fail(`unsupported target: ${options.target}`);
  }
  if (options.version !== null && (!options.version || !/^[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}$/.test(options.version))) {
    fail("version must be a bounded release identifier");
  }
  return { ...options, output: path.resolve(options.output) };
}

async function assertPath(candidate, label) {
  try {
    await fsp.access(candidate, fs.constants.R_OK);
  } catch {
    fail(`${label} is missing: ${candidate}`);
  }
}

async function readJson(file, label) {
  await assertPath(file, label);
  try {
    return JSON.parse(await fsp.readFile(file, "utf8"));
  } catch (error) {
    fail(`${label} is not valid JSON: ${error instanceof Error ? error.message : String(error)}`);
  }
}

async function copy(source, destination) {
  await fsp.mkdir(path.dirname(destination), { recursive: true });
  await fsp.cp(source, destination, {
    recursive: true,
    force: true,
    errorOnExist: false,
    verbatimSymlinks: true,
    filter: (candidate) => {
      const relative = path.relative(source, candidate);
      const parts = relative ? relative.split(path.sep) : [];
      if (parts.some((part) => part.startsWith(".ignored_"))) return false;
      if (parts.some((part) => [".modules.yaml", ".package-lock.json", ".package-map.json", ".pnpm-workspace-state-v1.json"].includes(part))) return false;
      return true;
    },
  });
}

function normalizePath(value) {
  return value.split(path.sep).join("/");
}

async function digestTree(root) {
  const entries = [];
  const stack = [root];
  let bytes = 0;
  while (stack.length) {
    const current = stack.pop();
    const stat = await fsp.lstat(current);
    const relative = normalizePath(path.relative(root, current));
    if (stat.isSymbolicLink()) {
      const target = await fsp.readlink(current);
      entries.push(`${relative}\0symlink\0${target}\n`);
      continue;
    }
    if (stat.isDirectory()) {
      const children = await fsp.readdir(current);
      for (const child of children.sort().reverse()) {
        stack.push(path.join(current, child));
      }
      continue;
    }
    const hash = crypto.createHash("sha256");
    const stream = fs.createReadStream(current);
    for await (const chunk of stream) hash.update(chunk);
    bytes += stat.size;
    entries.push(`${relative}\0file\0${stat.size}\0${hash.digest("hex")}\n`);
  }
  entries.sort();
  const treeHash = crypto.createHash("sha256").update(entries.join(""), "utf8").digest("hex");
  return { files: entries.length, bytes, sha256: treeHash };
}

async function fileHash(file) {
  const hash = crypto.createHash("sha256");
  const stream = fs.createReadStream(file);
  for await (const chunk of stream) hash.update(chunk);
  return hash.digest("hex");
}

async function writeJson(file, value) {
  await fsp.mkdir(path.dirname(file), { recursive: true });
  await fsp.writeFile(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const webPackage = await readJson(path.join(WEB_ROOT, "package.json"), "web package manifest");
  const electronPackage = await readJson(path.join(ELECTRON_ROOT, "package.json"), "Electron package manifest");
  const version = options.version || electronPackage.version;
  const nativeTarget = options.target === "windows-x64" ? "windows" : "linux";
  const nativePython = nativeTarget === "windows" ? "python" : "python3";
  const electronBinary = path.join(
    ELECTRON_ROOT,
    "node_modules",
    "electron",
    "dist",
    nativeTarget === "windows" ? "electron.exe" : "electron",
  );
  const required = [
    [path.join(WEB_ROOT, ".next"), "Next.js production build"],
    [path.join(WEB_ROOT, "node_modules"), "Next.js dependencies"],
    [path.join(ELECTRON_ROOT, "node_modules"), "Electron dependencies"],
    [
      electronBinary,
      `target-native Electron runtime (run "pnpm exec electron --version" after install)`,
    ],
    [path.join(REPO_ROOT, "market_os"), "Python domain package"],
    [path.join(REPO_ROOT, "apps", "gateway"), "Python gateway package"],
    [path.join(REPO_ROOT, "pyproject.toml"), "Python dependency manifest"],
  ];
  for (const [candidate, label] of required) await assertPath(candidate, label);

  await fsp.rm(options.output, { recursive: true, force: true });
  const shellRoot = path.join(options.output, "shell");
  const webRoot = path.join(options.output, "web");
  const pythonRoot = path.join(options.output, "python");

  await copy(path.join(ELECTRON_ROOT, "src"), path.join(shellRoot, "src"));
  await copy(path.join(ELECTRON_ROOT, "package.json"), path.join(shellRoot, "package.json"));
  await copy(path.join(ELECTRON_ROOT, "node_modules"), path.join(shellRoot, "node_modules"));
  await copy(path.join(WEB_ROOT, ".next"), path.join(webRoot, ".next"));
  if (fs.existsSync(path.join(WEB_ROOT, "public"))) {
    await copy(path.join(WEB_ROOT, "public"), path.join(webRoot, "public"));
  }
  await copy(path.join(WEB_ROOT, "package.json"), path.join(webRoot, "package.json"));
  await copy(path.join(WEB_ROOT, "node_modules"), path.join(webRoot, "node_modules"));
  await copy(path.join(REPO_ROOT, "market_os"), path.join(pythonRoot, "market_os"));
  await copy(path.join(REPO_ROOT, "apps", "__init__.py"), path.join(pythonRoot, "apps", "__init__.py"));
  await copy(path.join(REPO_ROOT, "apps", "gateway"), path.join(pythonRoot, "apps", "gateway"));
  await copy(path.join(REPO_ROOT, "pyproject.toml"), path.join(pythonRoot, "pyproject.toml"));

  const currentSlot = {
    schema: "market-os.u6.4-slot@v1",
    slot: "unsigned",
    version,
    status: "current-unverified",
    signature: "unsigned",
    artifact_root: ".",
    manifest_sha256: null,
  };
  const knownGoodSlot = {
    schema: "market-os.u6.4-slot@v1",
    slot: "u6.3-local-shell",
    version: "u6.3",
    status: "verified-local",
    signature: "not-packaged",
    artifact_root: null,
    manifest_sha256: null,
  };
  await writeJson(path.join(options.output, "slots", "current.json"), currentSlot);
  await writeJson(path.join(options.output, "slots", "known-good.json"), knownGoodSlot);

  const components = {};
  for (const [name, root] of [["shell", shellRoot], ["web", webRoot], ["python", pythonRoot]]) {
    components[name] = {
      path: name,
      ...(await digestTree(root)),
    };
  }
  const lockfiles = {
    web: await fileHash(path.join(WEB_ROOT, "pnpm-lock.yaml")),
    electron: await fileHash(path.join(ELECTRON_ROOT, "pnpm-lock.yaml")),
  };
  const manifest = {
    schema: "market-os.u6.4-artifact@v1",
    status: "unsigned-reproducible",
    version,
    target: options.target,
    platform: {
      os: options.target.split("-")[0],
      arch: options.target.split("-")[1],
      node: ">=20.9.0",
      electron: electronPackage.devDependencies?.electron || null,
    },
    renderer: {
      framework: "nextjs",
      version: webPackage.dependencies?.next || null,
      root: "web",
      route: "/overview",
    },
    sidecar: {
      type: "python-source",
      distribution: "target-native-source",
      root: "python",
      command: [nativePython, "-m", "apps.gateway"],
      interpreter: nativePython,
      requires_python: ">=3.11",
      dependencies: ["duckdb>=1.4,<3", "pyarrow>=18,<27"],
      host: "127.0.0.1",
    },
    storage: {
      root: "python/.market_os",
      scope: "artifact-local",
      shared_host_root: false,
    },
    dependencies: {
      package_manager: "pnpm@11.25.0",
      lockfiles,
    },
    entrypoints: {
      shell: "shell/src/main.cjs",
      electron_windows: "shell/node_modules/electron/dist/electron.exe",
      electron_linux: "shell/node_modules/electron/dist/electron",
      next_cli: "web/node_modules/next/dist/bin/next",
      gateway: "python/apps/gateway/__main__.py",
    },
    components,
    release_state: {
      signature: "unsigned",
      current_slot: "unsigned",
      known_good_slot: "u6.3-local-shell",
      rollback_available: false,
    },
    runtime_boundary: {
      loopback_only: true,
      synthetic: true,
      paper_only: true,
      read_only: true,
      credentials: false,
      provider_requests: 0,
      mutation_routes: false,
      live_trading: false,
    },
  };
  const manifestPath = path.join(options.output, "artifact-manifest.json");
  await writeJson(manifestPath, manifest);
  const manifestSha256 = await fileHash(manifestPath);
  await fsp.writeFile(`${manifestPath}.sha256`, `${manifestSha256}  artifact-manifest.json\n`, "utf8");
  currentSlot.manifest_sha256 = manifestSha256;
  await writeJson(path.join(options.output, "slots", "current.json"), currentSlot);
  console.log(JSON.stringify({
    output: options.output,
    target: options.target,
    version: manifest.version,
    manifest: manifestPath,
    components,
    host: os.platform(),
  }, null, 2));
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
