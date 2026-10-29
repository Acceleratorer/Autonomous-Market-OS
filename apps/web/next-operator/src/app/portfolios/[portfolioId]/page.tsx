import Link from "next/link";
import { notFound } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { BoundaryBanner, InspectionTable, MetricCard, PageHeading, PanelHeading, ServiceState } from "@/components/ui";
import { getPortfolioDetail, isPortfolioId, LocalApiError, type PortfolioEquityHistory } from "@/lib/market-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type PortfolioPageProps = {
  params: Promise<{ portfolioId: string }>;
  searchParams: Promise<{
    beforeRiskSequence?: string | string[];
    beforeOrderId?: string | string[];
    afterStrategyId?: string | string[];
    beforeReservationOrderId?: string | string[];
  }>;
};

type InspectionCursors = {
  beforeSequence?: string;
  beforeOrderId?: string;
  afterStrategyId?: string;
  beforeReservationOrderId?: string;
};

function formatEquityTime(timestampMs: number): string {
  const date = new Date(timestampMs);
  return Number.isNaN(date.getTime()) ? `${timestampMs} ms` : date.toISOString().replace(".000Z", "Z");
}

function PortfolioEquityChart({ history }: { history: PortfolioEquityHistory }) {
  const { points, minimumEquityUsdt, maximumEquityUsdt } = history;
  if (points.length < 2 || minimumEquityUsdt === null || maximumEquityUsdt === null) return null;

  const values = points.map((point) => Number(point.equityUsdt));
  const minimum = Number(minimumEquityUsdt);
  const maximum = Number(maximumEquityUsdt);
  const range = maximum - minimum;
  const padding = range > 0 ? range * 0.08 : Math.max(Math.abs(maximum) * 0.02, 1);
  const plotMinimum = Math.max(0, minimum - padding);
  const plotMaximum = maximum + padding;
  if (
    values.some((value) => !Number.isFinite(value))
    || !Number.isFinite(plotMinimum)
    || !Number.isFinite(plotMaximum)
    || plotMaximum <= plotMinimum
  ) {
    return <p className="equity-chart-note">Chart scale is unavailable for these values. Exact broker values remain in the table.</p>;
  }

  const width = 1000;
  const plotLeft = 36;
  const plotRight = 964;
  const plotTop = 18;
  const plotBottom = 278;
  const plotHeight = plotBottom - plotTop;
  const firstTime = points[0].eventTimeMs;
  const timeRange = points.at(-1)!.eventTimeMs - firstTime;
  const xFor = (index: number) => timeRange > 0
    ? plotLeft + ((points[index].eventTimeMs - firstTime) / timeRange) * (plotRight - plotLeft)
    : (plotLeft + plotRight) / 2;
  const yFor = (value: number) => plotTop + ((plotMaximum - value) / (plotMaximum - plotMinimum)) * plotHeight;
  const path = values.map((value, index) => `${index === 0 ? "M" : "L"} ${xFor(index)} ${yFor(value)}`).join(" ");
  const description = `Latest ${points.length} retained equity observations, from ${formatEquityTime(firstTime)} to ${formatEquityTime(points.at(-1)!.eventTimeMs)} UTC. The line connects broker-recorded observations. Exact USDT values and timestamps are listed below.`;

  return (
    <figure className="equity-chart-figure">
      <figcaption className="equity-chart-caption">
        Broker-recorded equity in USDT. The line covers the latest returned observations in the retained risk window.
      </figcaption>
      <dl className="equity-chart-range">
        <div><dt>Page high</dt><dd><code>{maximumEquityUsdt}</code> USDT</dd></div>
        <div><dt>Page low</dt><dd><code>{minimumEquityUsdt}</code> USDT</dd></div>
      </dl>
      <svg
        className="equity-chart-svg"
        viewBox={`0 0 ${width} 306`}
        preserveAspectRatio="none"
        role="img"
        aria-labelledby="portfolio-equity-chart-title portfolio-equity-chart-description"
      >
        <title id="portfolio-equity-chart-title">Portfolio equity history</title>
        <desc id="portfolio-equity-chart-description">{description}</desc>
        {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
          const y = plotTop + fraction * plotHeight;
          return <line key={fraction} className="equity-chart-gridline" x1={plotLeft} x2={plotRight} y1={y} y2={y} />;
        })}
        <line className="equity-chart-axis" x1={plotLeft} x2={plotRight} y1={plotBottom} y2={plotBottom} />
        <path className="equity-chart-line" d={path} />
        {values.map((value, index) => (
          <circle key={`${points[index].eventTimeMs}-${index}`} className="equity-chart-point" cx={xFor(index)} cy={yFor(value)} r="3.2" />
        ))}
      </svg>
      <div className="equity-chart-times" aria-label="Chart time range in UTC">
        <span>{formatEquityTime(firstTime)}</span>
        <span>{formatEquityTime(points.at(-1)!.eventTimeMs)}</span>
      </div>
      <p className="equity-chart-note">Use the table below for exact decimal values. Equal event timestamps are preserved; chart coordinates are approximate.</p>
    </figure>
  );
}

function inspectionHref(portfolioId: string, cursors: InspectionCursors = {}, anchor?: string) {
  const query = new URLSearchParams();
  if (cursors.beforeSequence) query.set("beforeRiskSequence", cursors.beforeSequence);
  if (cursors.beforeOrderId) query.set("beforeOrderId", cursors.beforeOrderId);
  if (cursors.afterStrategyId) query.set("afterStrategyId", cursors.afterStrategyId);
  if (cursors.beforeReservationOrderId) query.set("beforeReservationOrderId", cursors.beforeReservationOrderId);
  const serialized = query.toString();
  return `/portfolios/${encodeURIComponent(portfolioId)}${serialized ? `?${serialized}` : ""}${anchor ?? ""}`;
}

export default async function PortfolioDetailPage({ params, searchParams }: PortfolioPageProps) {
  const [{ portfolioId }, search] = await Promise.all([params, searchParams]);
  const beforeSequence = search.beforeRiskSequence;
  const beforeOrderId = search.beforeOrderId;
  const afterStrategyId = search.afterStrategyId;
  const beforeReservationOrderId = search.beforeReservationOrderId;
  if (!isPortfolioId(portfolioId)) notFound();
  if (Array.isArray(beforeSequence) || beforeSequence !== undefined && !/^[1-9]\d{0,63}$/.test(beforeSequence)) notFound();
  if (Array.isArray(beforeOrderId) || beforeOrderId !== undefined && (beforeOrderId.length === 0 || beforeOrderId.length > 160 || /[\u0000-\u001f]/.test(beforeOrderId))) notFound();
  if (Array.isArray(afterStrategyId) || afterStrategyId !== undefined && !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(afterStrategyId)) notFound();
  if (Array.isArray(beforeReservationOrderId) || beforeReservationOrderId !== undefined && (beforeReservationOrderId.length === 0 || beforeReservationOrderId.length > 160 || /[\u0000-\u001f]/.test(beforeReservationOrderId))) notFound();

  let portfolio;
  try {
    portfolio = await getPortfolioDetail(portfolioId, {
      beforeSequence,
      beforeOrderId,
      afterStrategyId,
      beforeReservationOrderId,
    });
  } catch (error) {
    const kind = error instanceof LocalApiError ? error.kind : "unavailable";
    return (
      <AppShell current="portfolio" gatewayStatus={kind === "unavailable" ? "unavailable" : "available"}>
        <div className="page-stack">
          <PageHeading
            eyebrow="B4 · portfolio inspection"
            title="Portfolio detail"
            description="The local broker did not return a complete, validated snapshot."
            actions={<Link className="action-link" href="/">Back to portfolios</Link>}
          />
          <ServiceState kind={kind} />
        </div>
      </AppShell>
    );
  }

  const orderRows = portfolio.orders.map((order) => ({
    key: order.orderId,
    values: [order.orderId, order.strategyId, order.side, order.orderType, order.quantity, order.limitPrice, order.state],
  }));
  const reservationRows = portfolio.reservations.rows.map((reservation) => ({
    key: reservation.orderId,
    values: [reservation.orderId, reservation.strategyId, reservation.cashUsdt, reservation.btcQuantity, reservation.buyQuantity],
  }));
  const riskRows = portfolio.riskRecords;

  return (
    <AppShell current="portfolio" gatewayStatus="available">
      <div className="page-stack">
        <PageHeading
          eyebrow={`${portfolio.symbol} · local paper portfolio`}
          title="Portfolio detail"
          description="A fresh, read-only inspection of balances, reservations, orders, and risk audit records."
          actions={<a className="action-link" href={`/portfolios/${portfolio.portfolioId}`}>Refresh snapshot</a>}
        />

        <BoundaryBanner>
          <strong>Synthetic · paper only.</strong>
          <span className="boundary-separator" aria-hidden="true">·</span>
          <span>This screen cannot submit, cancel, or modify orders.</span>
        </BoundaryBanner>

        <section className="metric-grid" aria-label="Portfolio summary">
          <MetricCard label="Cash balance" value={portfolio.summary.cashUsdt} unit="USDT" />
          <MetricCard label="BTC inventory" value={portfolio.summary.btcQuantity} unit="BTC" />
          <MetricCard label="Mark price" value={portfolio.summary.markPrice} unit="USDT" />
          <MetricCard label="Realized P/L" value={portfolio.summary.realizedPnlUsdt} unit="USDT" />
          <MetricCard label="Total fees" value={portfolio.summary.totalFeesUsdt} unit="USDT" />
          <MetricCard label="Market events" value={portfolio.summary.marketEventCount} />
          <MetricCard label="Open orders" value={portfolio.summary.openOrders} />
        </section>

        <section className="panel" id="portfolio-equity-history" aria-label="Portfolio equity history">
          <PanelHeading
            kicker="Retained risk window"
            title="Equity history"
            meta={`${portfolio.equityHistory.page.returnedCount} of ${portfolio.equityHistory.page.totalCount} samples`}
          />
          {portfolio.equityHistory.points.length ? (
            <>
              {portfolio.equityHistory.points.length > 1 ? (
                <PortfolioEquityChart history={portfolio.equityHistory} />
              ) : (
                <div className="panel-body"><p className="empty-state">One equity sample is available; a curve needs at least two observations.</p></div>
              )}
              <InspectionTable
                caption="Exact broker equity observations in the latest returned page"
                columns={["Event time (UTC)", "Equity (USDT)"]}
                rows={portfolio.equityHistory.points.map((point, index) => ({
                  key: `${point.eventTimeMs}-${index}`,
                  values: [formatEquityTime(point.eventTimeMs), point.equityUsdt],
                }))}
                emptyMessage="No equity observations are available."
              />
              <div className="panel-body">
                <p className="pagination-status">
                  {portfolio.equityHistory.page.hasMore
                    ? `Showing the latest ${portfolio.equityHistory.page.returnedCount} of ${portfolio.equityHistory.page.totalCount} observations retained by the risk window.`
                    : `Showing all ${portfolio.equityHistory.page.totalCount} observations currently retained by the risk window.`}
                </p>
              </div>
            </>
          ) : (
            <div className="panel-body"><p className="empty-state">No market events have recorded equity history yet.</p></div>
          )}
        </section>

        <div className="context-grid">
          <section className="panel" id="portfolio-members" aria-label="Portfolio identity context">
            <PanelHeading kicker="Portfolio identity" title="Context" meta={portfolio.mode} />
            <div className="panel-body">
              <dl className="detail-list">
                <dt>Portfolio ID</dt><dd className="fingerprint">{portfolio.portfolioId}</dd>
                <dt>Symbol</dt><dd>{portfolio.symbol}</dd>
                <dt>Strategy members</dt><dd>{portfolio.strategyIds.join(", ") || "No members on this page."}</dd>
                <dt>Fixture lineage</dt><dd>{portfolio.fixtureLineage}</dd>
                <dt>Policy fingerprint</dt><dd className="fingerprint">{portfolio.policyFingerprint}</dd>
                <dt>Genesis schema</dt><dd>{portfolio.schema}</dd>
              </dl>
            </div>
            <nav className="panel-body pagination-actions" aria-label="Strategy member pages">
              <p className="pagination-status">
                Showing {portfolio.strategyIds.length} of {portfolio.memberPage.totalCount} strategy members
                {afterStrategyId ? ` after ${afterStrategyId}` : " from the first members"}.
              </p>
              {afterStrategyId ? (
                <Link
                  className="action-link"
                  href={inspectionHref(portfolio.portfolioId, { beforeSequence, beforeOrderId, beforeReservationOrderId }, "#portfolio-members")}
                  prefetch={false}
                >
                  First members
                </Link>
              ) : null}
              {portfolio.memberPage.hasMore && portfolio.memberPage.nextAfterStrategyId ? (
                <Link
                  className="action-link"
                  href={inspectionHref(portfolio.portfolioId, {
                    beforeSequence,
                    beforeOrderId,
                    afterStrategyId: portfolio.memberPage.nextAfterStrategyId,
                    beforeReservationOrderId,
                  }, "#portfolio-members")}
                  prefetch={false}
                >
                  Next members
                </Link>
              ) : null}
            </nav>
          </section>

          <section className="panel" id="portfolio-reservations" aria-label="Portfolio reservations">
            <PanelHeading kicker="Shared capacity" title="Reservations" meta="PORTFOLIO WIDE" />
            <div className="panel-body">
              <dl className="detail-list">
                <dt>Cash reserved</dt><dd>{portfolio.reservations.cashUsdt} USDT</dd>
                <dt>BTC reserved</dt><dd>{portfolio.reservations.btcQuantity} BTC</dd>
                <dt>Buy quantity reserved</dt><dd>{portfolio.reservations.buyQuantity} BTC</dd>
              </dl>
            </div>
            {reservationRows.length ? (
              <InspectionTable
                caption="Portfolio-wide reservation detail"
                columns={["Order ID", "Strategy", "Cash USDT", "BTC", "Buy quantity"]}
                rows={reservationRows}
                emptyMessage="No reservations recorded."
              />
            ) : null}
            <nav className="panel-body pagination-actions" aria-label="Reservation pages">
              <p className="pagination-status">
                Showing {reservationRows.length} of {portfolio.reservations.page.totalCount} open reservations
                {beforeReservationOrderId ? ` before ${beforeReservationOrderId}` : " from the latest reservations"}.
              </p>
              {beforeReservationOrderId ? (
                <Link
                  className="action-link"
                  href={inspectionHref(portfolio.portfolioId, { beforeSequence, beforeOrderId, afterStrategyId }, "#portfolio-reservations")}
                  prefetch={false}
                >
                  Latest reservations
                </Link>
              ) : null}
              {portfolio.reservations.page.hasMore && portfolio.reservations.page.nextBeforeOrderId ? (
                <Link
                  className="action-link"
                  href={inspectionHref(portfolio.portfolioId, {
                    beforeSequence,
                    beforeOrderId,
                    afterStrategyId,
                    beforeReservationOrderId: portfolio.reservations.page.nextBeforeOrderId,
                  }, "#portfolio-reservations")}
                  prefetch={false}
                >
                  Older reservations
                </Link>
              ) : null}
            </nav>
          </section>
        </div>

        <section className="panel" id="portfolio-orders" aria-label="Portfolio orders">
          <PanelHeading kicker="Execution state" title="Orders" meta="READ ONLY" />
          <InspectionTable
            caption="Portfolio orders"
            columns={["Order ID", "Strategy", "Side", "Type", "Quantity", "Limit price", "State"]}
            rows={orderRows}
            emptyMessage="No orders have been recorded for this portfolio."
          />
          <div className="panel-body pagination-actions">
            <p className="pagination-status">
              Showing {portfolio.orders.length} {portfolio.orders.length === 1 ? "order" : "orders"}
              {beforeOrderId ? " before this order" : " from the latest orders"}.
            </p>
            {beforeOrderId ? (
              <Link
                className="action-link"
                href={inspectionHref(portfolio.portfolioId, { beforeSequence, afterStrategyId, beforeReservationOrderId }, "#portfolio-orders")}
                prefetch={false}
              >
                Latest orders
              </Link>
            ) : null}
            {portfolio.orderPage.hasMore && portfolio.orderPage.nextBeforeOrderId ? (
              <Link
                className="action-link"
                href={inspectionHref(portfolio.portfolioId, { beforeSequence, beforeOrderId: portfolio.orderPage.nextBeforeOrderId, afterStrategyId, beforeReservationOrderId }, "#portfolio-orders")}
                prefetch={false}
              >
                Older orders
              </Link>
            ) : null}
          </div>
        </section>

        <section className="panel" id="risk-audit" aria-label="Portfolio risk audit">
          <PanelHeading kicker="Control evidence" title="Risk audit" meta="APPEND ONLY" />
          {riskRows.length ? (
            <ul className="audit-list">
              {riskRows.map((record, index) => (
                <li className="audit-row" key={`${record.sequence}-${record.kind}-${index}`}>
                  <span className="audit-kind">{record.kind}</span>
                  <span className="audit-reason">{record.reasonCode}</span>
                  <span className="audit-sequence">#{record.sequence}</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="panel-body"><p className="empty-state">No risk or rejection outcomes are recorded.</p></div>
          )}
          <div className="panel-body pagination-actions">
            <p className="pagination-status">
              Showing {riskRows.length} {riskRows.length === 1 ? "outcome" : "outcomes"}
              {beforeSequence ? ` before sequence ${beforeSequence}` : " from the latest records"}.
            </p>
            {beforeSequence ? (
              <Link
                className="action-link"
                href={inspectionHref(portfolio.portfolioId, { beforeOrderId, afterStrategyId, beforeReservationOrderId }, "#risk-audit")}
                prefetch={false}
              >
                Latest outcomes
              </Link>
            ) : null}
            {portfolio.riskPage.hasMore && portfolio.riskPage.nextBeforeSequence ? (
              <Link
                className="action-link"
                href={inspectionHref(portfolio.portfolioId, { beforeSequence: portfolio.riskPage.nextBeforeSequence, beforeOrderId, afterStrategyId, beforeReservationOrderId }, "#risk-audit")}
                prefetch={false}
              >
                Older outcomes
              </Link>
            ) : null}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
