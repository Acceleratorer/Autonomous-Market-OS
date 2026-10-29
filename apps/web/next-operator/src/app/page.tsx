import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { BoundaryBanner, InspectionTable, MetricCard, PageHeading, PanelHeading, ServiceState } from "@/components/ui";
import { getPortfolioCatalog, LocalApiError, type PortfolioCatalogPage } from "@/lib/market-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function PortfolioRegistryPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  let catalog: PortfolioCatalogPage;
  try {
    const params = await searchParams;
    if (Object.keys(params).some((key) => key !== "limit" && key !== "after_portfolio_id")) {
      throw new LocalApiError("invalid");
    }
    const rawLimit = params.limit;
    const rawCursor = params.after_portfolio_id;
    if (Array.isArray(rawLimit) || Array.isArray(rawCursor)) throw new LocalApiError("invalid");
    if (rawLimit !== undefined && (!/^[0-9]{1,3}$/.test(rawLimit) || Number(rawLimit) < 1 || Number(rawLimit) > 100)) {
      throw new LocalApiError("invalid");
    }
    if (rawCursor !== undefined && !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(rawCursor)) {
      throw new LocalApiError("invalid");
    }
    catalog = await getPortfolioCatalog({
      limit: rawLimit === undefined ? 25 : Number(rawLimit),
      afterPortfolioId: rawCursor,
    });
  } catch (error) {
    const kind = error instanceof LocalApiError ? error.kind : "unavailable";
    return (
      <AppShell current="registry" gatewayStatus={kind === "unavailable" ? "unavailable" : "available"}>
        <div className="page-stack">
          <PageHeading
            eyebrow="B4 · portfolio operations"
            title="Portfolio overview"
            description="Inspect validated local paper portfolios and their current broker state."
          />
          <BoundaryBanner>
            <strong>Local and read only.</strong>
            <span className="boundary-separator" aria-hidden="true">·</span>
            <span>This workspace reads the loopback gateway and has no order controls.</span>
          </BoundaryBanner>
          <ServiceState kind={kind} />
        </div>
      </AppShell>
    );
  }

  const { portfolios, page } = catalog;
  const refreshQuery = new URLSearchParams({ limit: String(page.limit) });
  if (page.afterPortfolioId) refreshQuery.set("after_portfolio_id", page.afterPortfolioId);
  const rows = portfolios.map((portfolio) => ({
    key: portfolio.portfolioId,
    values: [
      portfolio.portfolioId,
      portfolio.mode,
      String(portfolio.memberCount),
      String(portfolio.openOrders),
      <Link
        className="table-link"
        href={`/portfolios/${portfolio.portfolioId}`}
        prefetch={false}
        aria-label={`Inspect portfolio ${portfolio.portfolioId}`}
      >
        Open portfolio
      </Link>,
    ],
  }));

  return (
    <AppShell current="registry" gatewayStatus="available">
      <div className="page-stack">
        <PageHeading
          eyebrow="B4 · portfolio operations"
          title="Portfolio overview"
          description="A validated view of the synthetic paper portfolios stored on this machine."
          actions={<a className="action-link" href={`/?${refreshQuery}`} aria-label="Refresh portfolio registry">Refresh registry</a>}
        />

        <BoundaryBanner>
          <strong>Local and read only.</strong>
          <span className="boundary-separator" aria-hidden="true">·</span>
          <span>Portfolio accounting, risk, and recovery remain owned by the Python broker.</span>
        </BoundaryBanner>

        <section className="metric-grid" aria-label="Registry summary">
          <MetricCard label="Portfolios on page" value={portfolios.length} />
          <MetricCard label="Access" value="GET only" />
          <MetricCard label="Network boundary" value="Loopback" />
        </section>

        <section className="panel" aria-label="Local portfolio registry">
          <PanelHeading
            kicker="Local registry"
            title="Validated portfolios"
            meta={`${portfolios.length} shown`}
          />
          {portfolios.length ? (
            <InspectionTable
              caption="Validated local paper portfolios"
              columns={["Portfolio ID", "Mode", "Strategies", "Open orders", "Inspect"]}
              rows={rows}
              emptyMessage="No validated portfolios are available."
            />
          ) : (
            <div className="panel-body">
              <div className="empty-state">
                <h3>No validated portfolios yet</h3>
                <p>Portfolio records will appear here when the local gateway finds a recoverable B4 paper store.</p>
              </div>
            </div>
          )}
        </section>

        <nav className="pagination-actions" aria-label="Portfolio pages">
          {page.afterPortfolioId ? (
            <Link className="action-link" href={`/?limit=${page.limit}`} aria-label="First portfolio page">First page</Link>
          ) : null}
          {page.hasMore && page.nextAfterPortfolioId ? (
            <Link
              className="action-link"
              href={`/?limit=${page.limit}&after_portfolio_id=${encodeURIComponent(page.nextAfterPortfolioId)}`}
              aria-label="Next portfolio page"
            >
              Next page
            </Link>
          ) : null}
          <p className="pagination-status" role="status">
            Showing {portfolios.length} validated {portfolios.length === 1 ? "portfolio" : "portfolios"} on this page.
            {page.skippedCount > 0 ? ` Skipped ${page.skippedCount} unreadable portfolio ${page.skippedCount === 1 ? "candidate" : "candidates"} while filling this page.` : null}
          </p>
        </nav>

      </div>
    </AppShell>
  );
}
