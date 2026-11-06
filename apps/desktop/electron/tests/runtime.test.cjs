"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const { test } = require("node:test");
const { once } = require("node:events");
const { spawn } = require("node:child_process");
const {
  findAvailablePort,
  LocalRuntime,
  isPortAvailable,
  isAllowedLoopbackUrl,
  parsePort,
  waitForHttp,
} = require("../src/runtime.cjs");

test("loopback URL policy rejects remote and non-HTTP navigation", () => {
  assert.equal(isAllowedLoopbackUrl("http://127.0.0.1:3000/overview", 3000), true);
  assert.equal(isAllowedLoopbackUrl("http://localhost:3000/overview", 3000), false);
  assert.equal(isAllowedLoopbackUrl("https://127.0.0.1:3000/overview", 3000), false);
  assert.equal(isAllowedLoopbackUrl("http://127.0.0.1:3001/overview", 3000), false);
  assert.throws(() => parsePort(80), /between 1024 and 65535/);
});

test("readiness polling waits for a healthy loopback response", async () => {
  const server = http.createServer((_request, response) => {
    response.writeHead(200, { "content-type": "application/json" });
    response.end("{}");
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const port = server.address().port;
  await waitForHttp(`http://127.0.0.1:${port}/readyz`, { timeoutMs: 1000, intervalMs: 10 });
  await new Promise((resolve) => server.close(resolve));
});

test("port selection avoids an occupied preferred port", async () => {
  const server = http.createServer((_request, response) => response.end("busy"));
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const occupiedPort = server.address().port;

  assert.equal(await isPortAvailable(occupiedPort), false);
  const selectedPort = await findAvailablePort([occupiedPort]);
  assert.notEqual(selectedPort, occupiedPort);
  assert.equal(await isPortAvailable(selectedPort), true);

  await new Promise((resolve) => server.close(resolve));
});

test("runtime starts both loopback children and cleans them up", async () => {
  const script = [
    "const http=require('node:http');",
    "const port=Number(process.env[process.env.TEST_PORT_ENV]);",
    "const path=process.env.TEST_READY_PATH;",
    "http.createServer((req,res)=>{res.statusCode=req.url===path?200:404;res.end('{}')}).listen(port,'127.0.0.1');",
  ].join("");
  const runtime = new LocalRuntime({
    apiPort: 38787,
    nextPort: 38788,
    readyTimeoutMs: 3000,
    gatewaySpec: {
      command: process.execPath,
      args: ["-e", script],
      env: { TEST_PORT_ENV: "MARKET_OS_API_PORT", TEST_READY_PATH: "/readyz" },
    },
    nextSpec: {
      command: process.execPath,
      args: ["-e", script],
      env: { TEST_PORT_ENV: "MARKET_OS_NEXT_PORT", TEST_READY_PATH: "/healthz" },
    },
  });
  await runtime.start();
  assert.deepEqual({ apiPort: runtime.apiPort, nextPort: runtime.nextPort }, { apiPort: 38787, nextPort: 38788 });
  await runtime.stop();
  await runtime.stop();
  await assert.rejects(fetch("http://127.0.0.1:38787/readyz"));
});

test("runtime reports child startup failures instead of a generic timeout", async () => {
  const runtime = new LocalRuntime({
    apiPort: 38901,
    nextPort: 38902,
    readyTimeoutMs: 500,
    gatewaySpec: {
      command: process.execPath,
      args: ["-e", "process.stderr.write('gateway exploded'); process.exit(1)"],
    },
    nextSpec: {
      command: process.execPath,
      args: ["-e", "setTimeout(() => {}, 1000)"],
    },
  });
  await assert.rejects(runtime.start(), /child failure:.*gateway exploded/);
  await runtime.stop();
});

test("main process keeps Electron privilege and navigation controls explicit", async () => {
  const main = fs.readFileSync(require.resolve("../src/main.cjs"), "utf8");
  assert.match(main, /contextIsolation:\s*true/);
  assert.match(main, /nodeIntegration:\s*false/);
  assert.match(main, /sandbox:\s*true/);
  assert.match(main, /setWindowOpenHandler\(\(\) => \(\{ action: "deny" \}\)\)/);
  assert.match(main, /will-navigate/);
  assert.match(main, /Close any conflicting local ports/);
});
