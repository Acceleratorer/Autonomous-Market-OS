import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { BoundaryBanner, InspectionTable, MetricCard, PageHeading, PanelHeading, ServiceState } from "@/components/ui";
import {
  getBtcHistoryCandlePage,
  isBtcDatasetRevision,
  LocalApiError,
  type BtcHistoryCandlePage,
} from "@/lib/market-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const DEFAULT_PAGE_LIMIT = 25;
const MAX_JS_DATE_TIME_MS = 8_640_000_000_000_000;

function pageHref(datasetRevision: string, limit: number, cursor?: number): string {
  const query = new URLSearchParams({ limit: String(limit) });
  if (cursor !== undefined) query.set("after_open_time_ms", String(cursor));
  return `/datasets/${encodeURIComponent(datasetRevision)}?${query}`;
}

function formatUtc(timestampMs: number): string {
  return new Date(timestampMs).toISOString().replace(".000Z", "Z");
}

function compareCandlePrices(left: string, right: string): number {
  const toScaledInteger = (value: string) => {
    const [significand, exponent = "0"] = value.toLowerCase().split("e");
    const [whole, fraction = ""] = significand.split(".");
    return {
      coefficient: BigInt(`${whole}${fraction}`),
      scale: BigInt(exponent) - BigInt(fraction.length),
    };
  };
  const leftDecimal = toScaledInteger(left);
  const rightDecimal = toScaledInteger(right);
  const commonScale = leftDecimal.scale < rightDecimal.scale ? leftDecimal.scale : rightDecimal.scale;
  const leftValue = leftDecimal.coefficient * BigInt(10) ** (leftDecimal.scale - commonScale);
  const rightValue = rightDecimal.coefficient * BigInt(10) ** (rightDecimal.scale - commonScale);
  return leftValue < rightValue ? -1 : leftValue > rightValue ? 1 : 0;
}

function CandleChart({ dataset, candles }: Pick<BtcHistoryCandlePage, "dataset" | "candles">) {
  if (!candles.length) return null;

  const numericCandles = candles.map((candle) => ({
    open: Number(candle.open),
    high: Number(candle.high),
    low: Number(candle.low),
    close: Number(candle.close),
  }));
  const lowestCandle = candles.reduce((lowest, candle) =>
    compareCandlePrices(candle.low, lowest.low) < 0 ? candle : lowest,
  );
  const highestCandle = candles.reduce((highest, candle) =>
    compareCandlePrices(candle.high, highest.high) > 0 ? candle : highest,
  );
  const rawLow = Number(lowestCandle.low);
  const rawHigh = Number(highestCandle.high);
  const rawRange = rawHigh - rawLow;
  const padding = rawRange > 0 ? rawRange * 0.05 : Math.abs(rawHigh) * 0.02;
  const minPrice = Math.max(0, rawLow - padding);
  const maxPrice = Math.min(Number.MAX_VALUE, rawHigh + padding);
  if (
    numericCandles.some((candle) =>
      !Number.isFinite(candle.open)
      || !Number.isFinite(candle.high)
      || !Number.isFinite(candle.low)
      || !Number.isFinite(candle.close)
    )
    || !Number.isFinite(rawRange)
    || maxPrice <= minPrice
  ) {
    return null;
  }

  const width = 1000;
  const plotLeft = 24;
  const plotRight = 976;
  const plotTop = 18;
  const plotBottom = 284;
  const plotHeight = plotBottom - plotTop;
  const candleStep = (plotRight - plotLeft) / candles.length;
  const candleWidth = Math.max(3, Math.min(18, candleStep * 0.56));
  const yFor = (price: number) => plotTop + ((maxPrice - price) / (maxPrice - minPrice)) * plotHeight;
  const first = candles[0];
  const last = candles[candles.length - 1];
  const description = `${candles.length} ${dataset.interval} candles for ${dataset.symbol}, from ${formatUtc(first.openTimeMs)} to ${formatUtc(last.openTimeMs)}. Filled candles close above their open; hollow candles close below their open; flat candles have a neutral outline. The chart shows only this bounded page. Exact OHLC and volume values remain in the table.`;

  return (
    <section className="panel candle-chart-panel" aria-label="Bounded BTC candle chart">
      <PanelHeading
        kicker={`${dataset.symbol} / ${dataset.interval} · current page`}
        title="Price movement"
        meta={`${candles.length} candles`}
      />
      <figure className="candle-chart-figure">
        <figcaption className="candle-chart-caption">
          Prices are in USDT. Each wick spans low to high; each body spans open to close. The chart covers only the loaded page.
        </figcaption>
        <dl className="candle-chart-extremes">
          <div>
            <dt>Page high</dt>
            <dd><code>{highestCandle.high}</code></dd>
          </div>
          <div>
            <dt>Page low</dt>
            <dd><code>{lowestCandle.low}</code></dd>
          </div>
        </dl>
        <svg
          className="candle-chart-svg"
          viewBox={`0 0 ${width} 320`}
          preserveAspectRatio="none"
          role="img"
          aria-labelledby="btc-candle-chart-title btc-candle-chart-description"
        >
          <title id="btc-candle-chart-title">{`${dataset.symbol} ${dataset.interval} candles on this page`}</title>
          <desc id="btc-candle-chart-description">{description}</desc>
          {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
            const y = plotTop + fraction * plotHeight;
            return <line key={fraction} className="candle-chart-gridline" x1={plotLeft} x2={plotRight} y1={y} y2={y} />;
          })}
          <line className="candle-chart-axis" x1={plotLeft} x2={plotRight} y1={plotBottom} y2={plotBottom} />
          {numericCandles.map((candle, index) => {
            const x = plotLeft + candleStep * (index + 0.5);
            const openY = yFor(candle.open);
            const closeY = yFor(candle.close);
            const directionComparison = compareCandlePrices(candles[index].close, candles[index].open);
            const direction = directionComparison > 0 ? "up" : directionComparison < 0 ? "down" : "flat";
            return (
              <g key={candles[index].openTimeMs}>
                <line
                  className={`candle-chart-wick candle-chart-wick-${direction}`}
                  x1={x}
                  x2={x}
                  y1={yFor(candle.high)}
                  y2={yFor(candle.low)}
                />
                <rect
                  className={`candle-chart-body candle-chart-body-${direction}`}
                  x={x - candleWidth / 2}
                  y={Math.min(openY, closeY)}
                  width={candleWidth}
                  height={Math.max(2.5, Math.abs(openY - closeY))}
                />
              </g>
            );
          })}
        </svg>
        <div className="candle-chart-times" aria-label="Chart time range">
          <time dateTime={new Date(first.openTimeMs).toISOString()}>{formatUtc(first.openTimeMs)}</time>
          <time dateTime={new Date(last.openTimeMs).toISOString()}>{formatUtc(last.openTimeMs)}</time>
        </div>
        <ul className="candle-chart-legend" aria-label="Candle encodings">
          <li><span className="candle-chart-swatch candle-chart-swatch-up" aria-hidden="true" />Rising · filled body</li>
          <li><span className="candle-chart-swatch candle-chart-swatch-down" aria-hidden="true" />Falling · hollow, dashed wick</li>
          <li><span className="candle-chart-swatch candle-chart-swatch-flat" aria-hidden="true" />Flat · neutral outline</li>
        </ul>
        <p className="candle-chart-note">Use the table below for exact OHLC and volume values.</p>
      </figure>
    </section>
  );
}

export default async function BtcDatasetDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ datasetRevision: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  let datasetRevision = "";
  let catalog: BtcHistoryCandlePage;
  try {
    ({ datasetRevision } = await params);
    if (!isBtcDatasetRevision(datasetRevision)) throw new LocalApiError("missing");

    const query = await searchParams;
    if (Object.keys(query).some((key) => key !== "limit" && key !== "after_open_time_ms")) {
      throw new LocalApiError("invalid");
    }
    const rawLimit = query.limit;
    const rawCursor = query.after_open_time_ms;
    if (Array.isArray(rawLimit) || Array.isArray(rawCursor)) throw new LocalApiError("invalid");
    if (rawLimit !== undefined && (!/^[0-9]{1,3}$/.test(rawLimit) || Number(rawLimit) < 1 || Number(rawLimit) > 100)) {
      throw new LocalApiError("invalid");
    }
    if (
      rawCursor !== undefined
      && (!/^[0-9]{1,16}$/.test(rawCursor) || Number(rawCursor) > MAX_JS_DATE_TIME_MS)
    ) {
      throw new LocalApiError("invalid");
    }
    catalog = await getBtcHistoryCandlePage(datasetRevision, {
      limit: rawLimit === undefined ? DEFAULT_PAGE_LIMIT : Number(rawLimit),
      afterOpenTimeMs: rawCursor === undefined ? undefined : Number(rawCursor),
    });
  } catch (error) {
    const kind = error instanceof LocalApiError ? error.kind : "unavailable";
    return (
      <AppShell current="datasetDetail" gatewayStatus={kind === "unavailable" ? "unavailable" : "available"}>
        <div className="page-stack">
          <PageHeading
            eyebrow="B1 · canonical candles"
            title="BTC dataset detail"
            description="Inspect a bounded chart and exact-value table of locally stored canonical candles."
            actions={<Link prefetch={false} className="action-link" href="/datasets">Back to registry</Link>}
          />
          <BoundaryBanner>
            <strong>Local and read only.</strong>
            <span className="boundary-separator" aria-hidden="true">·</span>
            <span>This page verifies the stored Parquet hash for each page. Replay is still required to validate canonical contents.</span>
          </BoundaryBanner>
          <ServiceState kind={kind} resource="BTC dataset candles" />
        </div>
      </AppShell>
    );
  }

  const { dataset, candles, page } = catalog;
  const rows = candles.map((candle) => ({
    key: String(candle.openTimeMs),
    values: [
      formatUtc(candle.openTimeMs),
      <code className="dataset-price">{candle.open}</code>,
      <code className="dataset-price">{candle.high}</code>,
      <code className="dataset-price">{candle.low}</code>,
      <code className="dataset-price">{candle.close}</code>,
      <code className="dataset-price">{candle.volume}</code>,
      formatUtc(candle.closeTimeMs),
    ],
  }));
  const currentPageHref = pageHref(dataset.datasetRevision, page.limit, page.afterOpenTimeMs ?? undefined);

  return (
    <AppShell current="datasetDetail" gatewayStatus="available">
      <div className="page-stack">
        <PageHeading
          eyebrow="B1 · canonical candles"
          title={`${dataset.symbol} ${dataset.interval}`}
          description={`Stored candle coverage for ${dataset.datasetRevision}.`}
          actions={
            <>
              <Link prefetch={false} className="action-link" href="/datasets">Back to registry</Link>
              <Link prefetch={false} className="action-link" href={`/datasets/${encodeURIComponent(dataset.datasetRevision)}/manifests`}>Ingestion runs</Link>
              <a className="action-link" href={currentPageHref}>Refresh page</a>
            </>
          }
        />

        <BoundaryBanner>
          <strong>Local and read only.</strong>
          <span className="boundary-separator" aria-hidden="true">·</span>
          <span>Each bounded page verifies the stored Parquet hash. Replay is still required to validate canonical contents.</span>
        </BoundaryBanner>

        <section className="metric-grid" aria-label="BTC dataset summary">
          <MetricCard label="Total candles" value={new Intl.NumberFormat("en").format(dataset.candleCount)} />
          <MetricCard label="Interval" value={dataset.interval} />
          <MetricCard label="Page access" value="GET only" />
        </section>

        <CandleChart dataset={dataset} candles={candles} />

        <section className="panel" aria-label="Canonical BTC candles">
          <PanelHeading
            kicker={`${dataset.venue} / ${dataset.symbol}`}
            title="Stored candles"
            meta={`${candles.length} of ${new Intl.NumberFormat("en").format(dataset.candleCount)} shown`}
          />
          <div className="dataset-detail-meta">
            <span>Observed range</span>
            <strong>{formatUtc(dataset.firstOpenTimeMs)} → {formatUtc(dataset.lastCloseTimeMs)}</strong>
            <span>Canonical fingerprint</span>
            <code className="dataset-fingerprint">{dataset.canonicalFingerprint}</code>
          </div>
          {candles.length ? (
            <InspectionTable
              caption="Bounded page of locally stored BTC canonical candles"
              columns={["Open time UTC", "Open", "High", "Low", "Close", "Volume", "Close time UTC"]}
              rows={rows}
              emptyMessage="No canonical candles are present on this page."
            />
          ) : (
            <div className="panel-body">
              <div className="empty-state">
                <h3>No candles on this page</h3>
                <p>The requested cursor is valid, but no later canonical candles are available.</p>
              </div>
            </div>
          )}
        </section>

        <nav className="pagination-actions" aria-label="BTC candle pages">
          {page.afterOpenTimeMs !== null ? (
            <Link prefetch={false} className="action-link" href={pageHref(dataset.datasetRevision, page.limit)} aria-label="First BTC candle page">
              First page
            </Link>
          ) : null}
          {page.hasMore && page.nextAfterOpenTimeMs !== null ? (
            <Link
              prefetch={false}
              className="action-link"
              href={pageHref(dataset.datasetRevision, page.limit, page.nextAfterOpenTimeMs)}
              aria-label="Next BTC candle page"
            >
              Next page
            </Link>
          ) : null}
          <p className="pagination-status" role="status">
            Showing {candles.length} of {new Intl.NumberFormat("en").format(dataset.candleCount)} locally stored candles.
          </p>
        </nav>
      </div>
    </AppShell>
  );
}
