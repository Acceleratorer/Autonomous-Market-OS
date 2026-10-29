import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { BoundaryBanner, InspectionTable, MetricCard, PageHeading, PanelHeading, ServiceState } from "@/components/ui";
import { getBtcHistoryDatasetCatalog, isBtcDatasetRevision, LocalApiError, type BtcHistoryDatasetPage } from "@/lib/market-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function pageHref(limit: number, cursor?: string): string {
  const query = new URLSearchParams({ limit: String(limit) });
  if (cursor) query.set("after_dataset_revision", cursor);
  return `/datasets?${query}`;
}

function formatUtc(timestampMs: number): string {
  return new Date(timestampMs).toISOString().replace(".000Z", "Z");
}

export default async function BtcDatasetRegistryPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  let catalog: BtcHistoryDatasetPage;
  try {
    const params = await searchParams;
    if (Object.keys(params).some((key) => key !== "limit" && key !== "after_dataset_revision")) {
      throw new LocalApiError("invalid");
    }
    const rawLimit = params.limit;
    const rawCursor = params.after_dataset_revision;
    if (Array.isArray(rawLimit) || Array.isArray(rawCursor)) throw new LocalApiError("invalid");
    if (rawLimit !== undefined && (!/^[0-9]{1,3}$/.test(rawLimit) || Number(rawLimit) < 1 || Number(rawLimit) > 100)) {
      throw new LocalApiError("invalid");
    }
    if (rawCursor !== undefined && !isBtcDatasetRevision(rawCursor)) throw new LocalApiError("invalid");
    catalog = await getBtcHistoryDatasetCatalog({
      limit: rawLimit === undefined ? 25 : Number(rawLimit),
      afterDatasetRevision: rawCursor,
    });
  } catch (error) {
    const kind = error instanceof LocalApiError ? error.kind : "unavailable";
    return (
      <AppShell current="datasets" gatewayStatus={kind === "unavailable" ? "unavailable" : "available"}>
        <div className="page-stack">
          <PageHeading
            eyebrow="B1 · local research data"
            title="BTC dataset registry"
            description="Inspect catalog metadata for BTC history already stored on this machine."
          />
          <BoundaryBanner>
            <strong>Local and read only.</strong>
            <span className="boundary-separator" aria-hidden="true">·</span>
            <span>This page does not acquire history, replay files, or request a provider connection.</span>
          </BoundaryBanner>
          <ServiceState kind={kind} resource="BTC dataset catalog" />
        </div>
      </AppShell>
    );
  }

  const { datasets, page } = catalog;
  const rows = datasets.map((dataset) => ({
    key: dataset.datasetRevision,
    values: [
      <Link prefetch={false} className="dataset-detail-link" href={`/datasets/${encodeURIComponent(dataset.datasetRevision)}`}>
        {dataset.datasetRevision}
      </Link>,
      dataset.symbol,
      dataset.venue,
      dataset.interval,
      new Intl.NumberFormat("en").format(dataset.candleCount),
      <span className="dataset-range">
        <span>{formatUtc(dataset.firstOpenTimeMs)}</span>
        <span aria-hidden="true">→</span>
        <span>{formatUtc(dataset.lastCloseTimeMs)}</span>
      </span>,
      <code className="dataset-fingerprint">{dataset.canonicalFingerprint}</code>,
    ],
  }));
  const refreshHref = pageHref(page.limit, page.afterDatasetRevision ?? undefined);

  return (
    <AppShell current="datasets" gatewayStatus="available">
      <div className="page-stack">
        <PageHeading
          eyebrow="B1 · local research data"
          title="BTC dataset registry"
          description="A bounded inventory of locally stored BTC history revisions and their recorded coverage."
          actions={<a className="action-link" href={refreshHref} aria-label="Refresh BTC dataset registry">Refresh registry</a>}
        />

        <BoundaryBanner>
          <strong>Local and read only.</strong>
          <span className="boundary-separator" aria-hidden="true">·</span>
          <span>Catalog metadata only; replay validates stored files. No history acquisition or provider calls occur here.</span>
        </BoundaryBanner>

        <section className="metric-grid" aria-label="BTC dataset registry summary">
          <MetricCard label="Datasets on page" value={datasets.length} />
          <MetricCard label="Catalog order" value="Revision" />
          <MetricCard label="Access" value="GET only" />
        </section>

        <section className="panel" aria-label="Local BTC history datasets">
          <PanelHeading kicker="B1 / canonical history" title="Stored revisions" meta={`${datasets.length} shown`} />
          {datasets.length ? (
            <InspectionTable
              caption="Locally stored BTC history dataset revisions"
              columns={["Dataset revision", "Symbol", "Venue", "Interval", "Candles", "Observed UTC range", "Canonical fingerprint"]}
              rows={rows}
              emptyMessage="No local BTC history datasets are available."
            />
          ) : (
            <div className="panel-body">
              <div className="empty-state">
                <h3>No local BTC history datasets</h3>
                <p>This registry reads existing HistoryStore metadata. It does not initialize an empty store or acquire new data.</p>
              </div>
            </div>
          )}
        </section>

        <nav className="pagination-actions" aria-label="BTC dataset pages">
          {page.afterDatasetRevision ? (
            <Link className="action-link" href={pageHref(page.limit)} aria-label="First BTC dataset page">First page</Link>
          ) : null}
          {page.hasMore && page.nextAfterDatasetRevision ? (
            <Link
              className="action-link"
              href={pageHref(page.limit, page.nextAfterDatasetRevision)}
              aria-label="Next BTC dataset page"
            >
              Next page
            </Link>
          ) : null}
          <p className="pagination-status" role="status">
            Showing {datasets.length} locally stored {datasets.length === 1 ? "dataset revision" : "dataset revisions"} on this page.
          </p>
        </nav>
      </div>
    </AppShell>
  );
}
