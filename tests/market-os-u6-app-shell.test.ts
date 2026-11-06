import { readFile } from "node:fs/promises";
import { test } from "node:test";
import assert from "node:assert/strict";
import { resolve } from "node:path";

const root = resolve(process.cwd());

async function source(relativePath: string): Promise<string> {
  return readFile(resolve(root, relativePath), "utf8");
}

test("U6.1 shell keeps the gateway status, overview, and dataset catalog surfaces", async () => {
  const [shell, overview, datasets, ui] = await Promise.all([
    source("apps/web/next-operator/src/components/app-shell.tsx"),
    source("apps/web/next-operator/src/app/overview/page.tsx"),
    source("apps/web/next-operator/src/app/datasets/page.tsx"),
    source("apps/web/next-operator/src/components/ui.tsx"),
  ]);

  assert.match(shell, /gatewayStatus/);
  assert.match(shell, /Gateway available/);
  assert.match(overview, /getGatewayStatus/);
  assert.match(overview, /getPortfolioCatalog/);
  assert.match(overview, /getBtcHistoryDatasetCatalog/);
  assert.match(ui, /aria-label="Operator system status"/);
  assert.match(datasets, /getBtcHistoryDatasetCatalog/);
  assert.match(datasets, /after_dataset_revision/);
});

test("U6.1 market adapter validates the shared envelope, bounds, cursor, and ordering", async () => {
  const api = await source("apps/web/next-operator/src/lib/market-api.ts");

  assert.match(api, /market-os\.v1/);
  assert.match(api, /market-os\.btc-history-catalog@v1/);
  assert.match(api, /limit < 1 \|\| limit > 100/);
  assert.match(api, /entries\.length > limit/);
  assert.match(api, /afterDatasetRevision/);
  assert.match(api, /datasets\[index - 1\]\.datasetRevision >= dataset\.datasetRevision/);
  assert.match(api, /throw new LocalApiError\("invalid"\)/);
  assert.doesNotMatch(api, /method:\s*["'](?:POST|PUT|PATCH|DELETE)["']/);
});

test("U6.1 responsive contract preserves labelled table scrolling and target widths", async () => {
  const css = await source("apps/web/next-operator/src/app/globals.css");

  assert.match(css, /\.table-scroll[\s\S]*overflow-x:\s*auto/);
  assert.match(css, /:focus-visible/);
  for (const width of ["900px", "560px"]) {
    assert.match(css, new RegExp(`@media \\(max-width: ${width.replace("px", "\\px")}\\)`));
  }
  assert.match(css, /min-height:\s*44px/);
});
