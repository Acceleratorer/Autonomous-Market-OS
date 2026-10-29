import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { BoundaryBanner, MetricCard, PageHeading, PanelHeading, ServiceState } from "@/components/ui";
import {
  getBtcHistoryDatasetCatalog,
  getBtcResearchRunPage,
  getPortfolioCatalog,
  LocalApiError,
  type LocalApiErrorKind,
} from "@/lib/market-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const OVERVIEW_PAGE_SIZE = 3;

type ResourceResult<T> =
  | { ok: true; value: T }
  | { ok: false; kind: LocalApiErrorKind };

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

export default async function OperatorOverviewPage() {
  const [portfolios, datasets, b2Runs, b3Runs] = await Promise.all([
    readResource(() => getPortfolioCatalog({ limit: OVERVIEW_PAGE_SIZE })),
    readResource(() => getBtcHistoryDatasetCatalog({ limit: OVERVIEW_PAGE_SIZE })),
    readResource(() => getBtcResearchRunPage("b2", { limit: OVERVIEW_PAGE_SIZE })),
    readResource(() => getBtcResearchRunPage("b3", { limit: OVERVIEW_PAGE_SIZE })),
  ]);
  const resources = [portfolios, datasets, b2Runs, b3Runs];
  const gatewayStatus = resources.some(gatewayIsAvailable) ? "available" : "unavailable";
  const researchRunCount = b2Runs.ok || b3Runs.ok
    ? (b2Runs.ok ? b2Runs.value.runs.length : 0) + (b3Runs.ok ? b3Runs.value.runs.length : 0)
    : null;
  const researchCatalogsComplete = b2Runs.ok && b3Runs.ok;
  const visiblePortfolioOpenOrders = portfolios.ok
    ? portfolios.value.portfolios.reduce((count, portfolio) => count + portfolio.openOrders, 0)
    : null;
  const researchRuns = [
    ...(b2Runs.ok ? b2Runs.value.runs : []),
    ...(b3Runs.ok ? b3Runs.value.runs : []),
  ];

  return (
    <AppShell current="overview" gatewayStatus={gatewayStatus}>
      <div className="page-stack overview-page">
        <PageHeading
          eyebrow="Local operator · overview"
          title="Your workspace, at a glance"
          description="A read-only view across paper portfolios, BTC market data, and offline research."
          actions={<Link className="action-link" href="/">Open portfolio registry</Link>}
        />

        <BoundaryBanner>
          <strong>Local and read only.</strong>
          <span className="boundary-separator" aria-hidden="true">·</span>
          <span>Synthetic research and paper portfolios only; this workspace has no live venue or order controls.</span>
        </BoundaryBanner>

        <section className="overview-metric-grid" aria-label="First-page resource summary">
          <MetricCard
            label="Portfolios · first page"
            value={portfolios.ok ? portfolios.value.portfolios.length : "—"}
            unit={portfolios.ok ? "shown" : "unavailable"}
          />
          <MetricCard
            label="BTC datasets · first page"
            value={datasets.ok ? datasets.value.datasets.length : "—"}
            unit={datasets.ok ? "shown" : "unavailable"}
          />
          <MetricCard
            label="B2 + B3 runs · first pages"
            value={researchRunCount ?? "—"}
            unit={researchRunCount === null ? "unavailable" : researchCatalogsComplete ? "shown" : "partial"}
          />
        </section>

        <section className="overview-resource-grid" aria-label="Local workspace resources">
          <article className="panel overview-panel" aria-label="Portfolio operations preview">
            <PanelHeading
              kicker="B4 · paper operations"
              title="Portfolios"
              meta={portfolios.ok ? `${portfolios.value.portfolios.length} shown` : "Unavailable"}
            />
            <div className="panel-body overview-panel-body">
              {portfolios.ok ? (
                portfolios.value.portfolios.length ? (
                  <>
                    <ul className="overview-list">
                      {portfolios.value.portfolios.map((portfolio) => (
                        <li key={portfolio.portfolioId}>
                          <Link
                            className="overview-list-link"
                            href={`/portfolios/${encodeURIComponent(portfolio.portfolioId)}`}
                            prefetch={false}
                          >
                            <span className="overview-list-copy">
                              <span className="overview-list-primary">{portfolio.portfolioId}</span>
                              <span className="overview-list-secondary">{portfolio.mode} · {portfolio.memberCount} {portfolio.memberCount === 1 ? "strategy" : "strategies"}</span>
                            </span>
                            <span className="overview-list-meta">{portfolio.openOrders} open</span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                    <p className="overview-note">
                      {visiblePortfolioOpenOrders} open {visiblePortfolioOpenOrders === 1 ? "order" : "orders"} across the portfolios shown.
                    </p>
                  </>
                ) : (
                  <p className="overview-empty">No validated local paper portfolios are available.</p>
                )
              ) : (
                <ServiceState kind={portfolios.kind} resource="portfolio" title="Portfolio preview unavailable" />
              )}
              <Link className="action-link overview-panel-action" href="/">View portfolio registry</Link>
            </div>
          </article>

          <article className="panel overview-panel" aria-label="BTC market data preview">
            <PanelHeading
              kicker="B1 · historical data"
              title="BTC datasets"
              meta={datasets.ok ? `${datasets.value.datasets.length} shown` : "Unavailable"}
            />
            <div className="panel-body overview-panel-body">
              {datasets.ok ? (
                datasets.value.datasets.length ? (
                  <ul className="overview-list">
                    {datasets.value.datasets.map((dataset) => (
                      <li key={dataset.datasetRevision}>
                        <Link
                          className="overview-list-link"
                          href={`/datasets/${encodeURIComponent(dataset.datasetRevision)}`}
                          prefetch={false}
                        >
                          <span className="overview-list-copy">
                            <span className="overview-list-primary">{dataset.symbol} · {dataset.interval}</span>
                            <span className="overview-list-secondary">{dataset.venue} · {dataset.candleCount.toLocaleString("en-US")} candles</span>
                          </span>
                          <span className="overview-list-meta">Inspect</span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="overview-empty">No validated BTC history datasets are available.</p>
                )
              ) : (
                <ServiceState kind={datasets.kind} resource="BTC dataset catalog" title="Dataset preview unavailable" />
              )}
              <Link className="action-link overview-panel-action" href="/datasets">Browse BTC datasets</Link>
            </div>
          </article>

          <article className="panel overview-panel" aria-label="BTC offline research preview">
            <PanelHeading
              kicker="B2–B3 · offline research"
              title="BTC research"
              meta={researchRunCount === null ? "Unavailable" : `${researchRunCount} shown${researchCatalogsComplete ? "" : " · partial"}`}
            />
            <div className="panel-body overview-panel-body">
              {!b2Runs.ok ? <ServiceState kind={b2Runs.kind} resource="BTC research runs" title="B2 catalog unavailable" /> : null}
              {!b3Runs.ok ? <ServiceState kind={b3Runs.kind} resource="BTC research runs" title="B3 catalog unavailable" /> : null}
              {researchRuns.length ? (
                <ul className="overview-list">
                  {researchRuns.map((run) => (
                    <li key={`${run.engine}-${run.runId}`}>
                      <Link
                        className="overview-list-link"
                        href={`/experiments/${run.engine}/${encodeURIComponent(run.runId)}`}
                        prefetch={false}
                      >
                        <span className="overview-list-copy">
                          <span className="overview-list-primary">{run.engine.toUpperCase()} · {run.runId}</span>
                          <span className="overview-list-secondary">{run.datasetRevision}</span>
                        </span>
                        {run.engine === "b3" ? <span className="overview-status">Not promoted</span> : <span className="overview-list-meta">Inspect</span>}
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : null}
              {researchCatalogsComplete && !researchRuns.length ? (
                <p className="overview-empty">No validated offline research runs are available.</p>
              ) : null}
              <p className="overview-note">B3 remains offline and not promoted. Run details show the validated report state.</p>
              <Link className="action-link overview-panel-action" href="/experiments">Browse BTC research</Link>
            </div>
          </article>
        </section>

        <p className="overview-footnote">Previews show at most {OVERVIEW_PAGE_SIZE} records per catalog; open a resource to continue through its validated pages.</p>
      </div>
    </AppShell>
  );
}
