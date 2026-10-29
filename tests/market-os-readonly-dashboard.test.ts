import { readFile } from "node:fs/promises";
import { test } from "node:test";
import assert from "node:assert/strict";
import { resolve } from "node:path";

const dashboardPath = resolve(process.cwd(), "apps/web/public/index.html");

test("hosted Market OS preview keeps the paper-only read-only boundary", async () => {
  const html = await readFile(dashboardPath, "utf8");

  assert.match(html, /Market OS/);
  assert.match(html, /SYNTHETIC · PAPER ONLY · READ ONLY/);
  assert.match(html, /no portfolio data, API connection, sign-in, order controls/);
  assert.doesNotMatch(html, /<form\b/i);
  assert.doesNotMatch(html, /<script\b/i);
  assert.doesNotMatch(html, /fetch\s*\(|XMLHttpRequest|WebSocket/i);
  assert.doesNotMatch(html, /password|api[_-]?key|secret|credential/i);
});
