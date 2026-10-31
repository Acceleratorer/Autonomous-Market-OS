import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { MarketCandleChart, MarketContextStrip, SyntheticFixturePreview } from "@/components/market-desk";
import { PanelHeading, ServiceState } from "@/components/ui";
import {
  getBtcHistoryCandlePage,
  getBtcHistoryDatasetCatalog,
  getBtcResearchRunPage,
  getPortfolioCatalog,
  getPortfolioDetail,
  LocalApiError,
  type BtcHistoryCandlePage,
  type BtcHistoryDatasetPage,
  type BtcResearchRunPage,
  type PortfolioDetail,
  type PortfolioCatalogPage,
} from "@/lib/market-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type ResourceResult<T> =
  | { ok: true; value: T }
  | { ok: false; kind: "unavailable" | "missing" | "rejected" | "invalid" };

async function readResource<T>(read: () => Promise<T>): Promise<ResourceResult<T>> {
  try {
    return { ok: true, value: await read() };
  } catch (error) {
    return {
      ok: false,
      kind: error instanceof LocalApiError ? error.kind : "unavailable",
    };
  }
}

function gatewayIsAvailable(resource: ResourceResult<unknown>): boolean {
  return resource.ok || resource.kind !== "unavailable";
}

function datasetHref(datasetRevision: string): string {
  return `/datasets/${encodeURIComponent(datasetRevision)}`;
}

export default async function MarketDeskPage() {
  const [datasets, portfolios, b2Runs, b3Runs] = await Promise.all([
    readResource<BtcHistoryDatasetPage>(() => getBtcHistoryDatasetCatalog({ limit: 5 })),
    readResource<PortfolioCatalogPage>(() => getPortfolioCatalog({ limit: 5 })),
    readResource<BtcResearchRunPage>(() => getBtcResearchRunPage("b2", { limit: 3 })),
    readResource<BtcResearchRunPage>(() => getBtcResearchRunPage("b3", { limit: 3 })),
  ]);

  let candles: ResourceResult<BtcHistoryCandlePage> | null = null;
  const firstDataset = datasets.ok ? datasets.value.datasets[0] : undefined;
  if (firstDataset) {
    candles = await readResource(() => getBtcHistoryCandlePage(firstDataset.datasetRevision, { limit: 32 }));
  }

  let portfolioDetail: ResourceResult<PortfolioDetail> | null = null;
  const firstPortfolio = portfolios.ok ? portfolios.value.portfolios[0] : undefined;
  if (firstPortfolio) {
    portfolioDetail = await readResource(() => getPortfolioDetail(firstPortfolio.portfolioId));
  }

  const resources = [datasets, portfolios, b2Runs, b3Runs, ...(candles ? [candles] : []), ...(portfolioDetail ? [portfolioDetail] : [])];
  const gatewayStatus = resources.some(gatewayIsAvailable) ? "available" : "unavailable";
  const researchCount = (b2Runs.ok ? b2Runs.value.runs.length : 0) + (b3Runs.ok ? b3Runs.value.runs.length : 0);
  const hasStoredData = Boolean(firstDataset && candles?.ok);

  return (
    <AppShell current="desk" gatewayStatus={gatewayStatus}>
      <div className="page-stack market-desk-page">
        <section className="desk-instrument-header" aria-labelledby="desk-instrument-title">
          <div className="desk-instrument-identity">
            <p className="desk-kicker">MARKET DESK / BTCUSDT SPOT</p>
            <h1 id="desk-instrument-title">{firstDataset?.symbol ?? "BTCUSDT"}</h1>
            <p>Bitcoin / Tether <span>Local synthetic observation surface</span></p>
          </div>
          <div className="desk-instrument-badges" role="group" aria-label="Desk mode">
            <span className="desk-badge desk-badge-cyan">Synthetic fixture</span>
            <span className="desk-badge desk-badge-green">Paper</span>
            <span className="desk-badge desk-badge-neutral">Read only</span>
            <span className="desk-badge desk-badge-amber">Execution off</span>
          </div>
        </section>

        <section className="desk-status-ribbon" role="status" aria-label="Market desk status">
          <div><span>Gateway</span><strong>{gatewayStatus === "available" ? "Available" : "Unavailable"}</strong></div>
          <div><span>Data</span><strong>{hasStoredData ? "Validated page" : "Fixture preview"}</strong></div>
          <div><span>Authority</span><strong>Python broker</strong></div>
          <div><span>Venue</span><strong>None</strong></div>
        </section>

        <MarketContextStrip dataset={firstDataset} candles={candles?.ok ? candles.value.candles : undefined} />

        <div className="desk-workspace-grid">
          <section className="panel desk-chart-panel" aria-label="Primary market chart">
            <PanelHeading
              kicker={firstDataset ? `${firstDataset.symbol} / ${firstDataset.interval}` : "BTCUSDT / SPOT"}
              title="Price structure"
              meta={hasStoredData ? "OHLCV" : "FIXTURE PREVIEW"}
            />
            {candles?.ok && firstDataset ? (
              <MarketCandleChart dataset={firstDataset} candles={candles.value.candles} />
            ) : datasets.ok ? (
              <SyntheticFixturePreview symbol={firstDataset?.symbol ?? "BTCUSDT"} />
            ) : candles && !candles.ok ? (
              <div className="panel-body"><ServiceState kind={candles.kind} resource="BTC dataset candles" title="Market chart unavailable" /></div>
            ) : !datasets.ok ? (
              <div className="panel-body"><ServiceState kind={datasets.kind} resource="BTC dataset catalog" title="Market data unavailable" /></div>
            ) : (
              <div className="panel-body"><ServiceState kind="invalid" resource="BTC dataset catalog" title="Market data unavailable" /></div>
            )}
          </section>

          <aside className="desk-right-rail" aria-label="Portfolio and execution context">
            <section className="panel desk-rail-panel" aria-label="Portfolio and risk context">
              <PanelHeading
                kicker="Book context"
                title="Portfolio state"
                meta={portfolioDetail?.ok ? portfolioDetail.value.portfolioId : "NO BOOK"}
              />
              {portfolioDetail?.ok ? (
                <div className="panel-body">
                  <dl className="desk-book-grid">
                    <div><dt>Mark price</dt><dd>{portfolioDetail.value.summary.markPrice} USDT</dd></div>
                    <div><dt>Realized P/L</dt><dd>{portfolioDetail.value.summary.realizedPnlUsdt} USDT</dd></div>
                    <div><dt>BTC inventory</dt><dd>{portfolioDetail.value.summary.btcQuantity} BTC</dd></div>
                    <div><dt>Open orders</dt><dd>{portfolioDetail.value.summary.openOrders}</dd></div>
                    <div><dt>Risk outcomes shown</dt><dd>{portfolioDetail.value.riskRecords.length}</dd></div>
                  </dl>
                  <Link className="action-link" href={`/portfolios/${encodeURIComponent(portfolioDetail.value.portfolioId)}`} prefetch={false}>
                    Open book detail
                  </Link>
                </div>
              ) : portfolioDetail && !portfolioDetail.ok ? (
                <div className="panel-body"><ServiceState kind={portfolioDetail.kind} resource="portfolio" title="Portfolio state unavailable" /></div>
              ) : portfolios.ok ? (
                <div className="panel-body"><p className="empty-state">No validated paper book is available for this desk.</p></div>
              ) : (
                <div className="panel-body"><ServiceState kind={portfolios.kind} resource="portfolio" title="Portfolio state unavailable" /></div>
              )}
            </section>

            <section className="panel desk-rail-panel" aria-label="Paper execution state">
              <PanelHeading kicker="Paper execution" title="Order ticket" meta="LOCKED" />
              <div className="panel-body">
                <div className="execution-lock">
                  <span className="execution-lock-mark" aria-hidden="true">OFF</span>
                  <div>
                    <strong>Execution disabled</strong>
                    <p>This operator can inspect recorded orders and reservations, but cannot submit, cancel, or amend.</p>
                  </div>
                </div>
                <dl className="execution-facts">
                  <div><dt>Authority</dt><dd>Python broker</dd></div>
                  <div><dt>Venue</dt><dd>None</dd></div>
                  <div><dt>Access</dt><dd>GET only</dd></div>
                </dl>
                <Link className="action-link" href="/">Review portfolios</Link>
              </div>
            </section>
          </aside>
        </div>

        <div className="desk-evidence-grid">
          <section className="panel" aria-label="Market watchlist">
            <PanelHeading kicker="Stored revisions" title="Watchlist" meta={datasets.ok ? `${datasets.value.datasets.length} shown` : "Unavailable"} />
            <div className="desk-list">
              {datasets.ok && datasets.value.datasets.length ? datasets.value.datasets.map((dataset) => (
                <Link className="desk-list-row" href={datasetHref(dataset.datasetRevision)} key={dataset.datasetRevision} prefetch={false}>
                  <span>
                    <strong>{dataset.symbol}</strong>
                    <small>{dataset.interval} · {dataset.venue}</small>
                  </span>
                  <span className="desk-list-value">{dataset.candleCount.toLocaleString("en-US")} candles</span>
                </Link>
              )) : datasets.ok ? (
                <p className="empty-state">No stored revisions are available for this watchlist.</p>
              ) : (
                <div className="panel-body"><ServiceState kind={datasets.kind} resource="BTC dataset catalog" title="Watchlist unavailable" /></div>
              )}
            </div>
          </section>

          <section className="panel" aria-label="Evidence and research lineage">
            <PanelHeading kicker="Evidence chain" title="Lineage" meta={`${researchCount} shown`} />
            <div className="panel-body desk-evidence-list">
              <div><span>Dataset revision</span><strong>{firstDataset?.datasetRevision ?? "n/a"}</strong></div>
              <div><span>Canonical fingerprint</span><code>{firstDataset?.canonicalFingerprint ?? "n/a"}</code></div>
              <div><span>B2 baselines</span><strong>{b2Runs.ok ? b2Runs.value.runs.length : "n/a"}</strong></div>
              <div><span>B3 comparisons</span><strong>{b3Runs.ok ? b3Runs.value.runs.length : "n/a"}</strong></div>
              <Link className="action-link" href="/experiments">Open evidence</Link>
            </div>
          </section>

          <section className="panel" aria-label="Portfolio and risk context">
            <PanelHeading kicker="Paper portfolios" title="Open order context" meta={portfolios.ok ? `${portfolios.value.portfolios.length} shown` : "Unavailable"} />
            <div className="desk-list">
              {portfolios.ok && portfolios.value.portfolios.length ? portfolios.value.portfolios.map((portfolio) => (
                <Link className="desk-list-row" href={`/portfolios/${encodeURIComponent(portfolio.portfolioId)}`} key={portfolio.portfolioId} prefetch={false}>
                  <span>
                    <strong>{portfolio.portfolioId}</strong>
                    <small>{portfolio.mode} · {portfolio.memberCount} {portfolio.memberCount === 1 ? "strategy" : "strategies"}</small>
                  </span>
                  <span className="desk-list-value">{portfolio.openOrders} open</span>
                </Link>
              )) : portfolios.ok ? (
                <p className="empty-state">No validated paper portfolios are available.</p>
              ) : (
                <div className="panel-body"><ServiceState kind={portfolios.kind} resource="portfolio" title="Portfolio context unavailable" /></div>
              )}
            </div>
          </section>
        </div>
      </div>
    </AppShell>
  );
}
