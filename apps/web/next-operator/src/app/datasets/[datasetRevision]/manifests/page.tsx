import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { BoundaryBanner, InspectionTable, PageHeading, PanelHeading, ServiceState } from "@/components/ui";
import {
  getBtcHistoryManifestPage,
  LocalApiError,
  type BtcIngestionManifestPage,
} from "@/lib/market-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const DEFAULT_PAGE_LIMIT = 25;

function pageHref(datasetRevision: string, limit: number, cursor?: string): string {
  const query = new URLSearchParams({ limit: String(limit) });
  if (cursor !== undefined) query.set("after_manifest_id", cursor);
  return `/datasets/${encodeURIComponent(datasetRevision)}/manifests?${query}`;
}

function formatUtc(timestampMs: number): string {
  return new Date(timestampMs).toISOString().replace(".000Z", "Z");
}

export default async function BtcManifestRegistryPage({
  params,
  searchParams,
}: {
  params: Promise<{ datasetRevision: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  let datasetRevision = "";
  let catalog: BtcIngestionManifestPage;
  try {
    ({ datasetRevision } = await params);
    const query = await searchParams;
    if (Object.keys(query).some((key) => key !== "limit" && key !== "after_manifest_id")) {
      throw new LocalApiError("invalid");
    }
    const rawLimit = query.limit;
    const rawCursor = query.after_manifest_id;
    if (Array.isArray(rawLimit) || Array.isArray(rawCursor)) throw new LocalApiError("invalid");
    if (rawLimit !== undefined && (!/^[0-9]{1,3}$/.test(rawLimit) || Number(rawLimit) < 1 || Number(rawLimit) > 100)) {
      throw new LocalApiError("invalid");
    }
    if (rawCursor !== undefined && !/^btc-history-manifest-[0-9a-f]{20}$/.test(rawCursor)) {
      throw new LocalApiError("invalid");
    }
    catalog = await getBtcHistoryManifestPage(datasetRevision, {
      limit: rawLimit === undefined ? DEFAULT_PAGE_LIMIT : Number(rawLimit),
      afterManifestId: rawCursor,
    });
  } catch (error) {
    const kind = error instanceof LocalApiError ? error.kind : "unavailable";
    return (
      <AppShell current="datasetDetail" gatewayStatus={kind === "unavailable" ? "unavailable" : "available"}>
        <div className="page-stack">
          <PageHeading
            eyebrow="B1 · ingestion runs"
            title="BTC ingestion manifests"
            description="Inspect hash-verified run metadata attached to this canonical dataset."
            actions={<Link prefetch={false} className="action-link" href="/datasets">Back to registry</Link>}
          />
          <BoundaryBanner>
            <strong>Local and read only.</strong>
            <span className="boundary-separator" aria-hidden="true">·</span>
            <span>Manifest pages are bounded. Raw rows, file paths, gap records, and provenance payloads are not returned here.</span>
          </BoundaryBanner>
          <ServiceState kind={kind} resource="BTC ingestion manifests" />
        </div>
      </AppShell>
    );
  }

  const rows = catalog.manifests.map((manifest) => ({
    key: manifest.manifestId,
    values: [
      <Link
        prefetch={false}
        className="dataset-detail-link"
        href={`/datasets/${encodeURIComponent(datasetRevision)}/manifests/${encodeURIComponent(manifest.manifestId)}`}
      >
        {manifest.manifestId}
      </Link>,
      `${formatUtc(manifest.requestedStartMs)} → ${formatUtc(manifest.requestedEndMsExclusive)} (end exclusive)`,
      String(manifest.networkRequests),
      <code className="dataset-fingerprint">{manifest.manifestSha256}</code>,
    ],
  }));
  const currentPageHref = pageHref(datasetRevision, catalog.page.limit, catalog.page.afterManifestId ?? undefined);

  return (
    <AppShell current="datasetDetail" gatewayStatus="available">
      <div className="page-stack">
        <PageHeading
          eyebrow="B1 · ingestion runs"
          title="BTC ingestion manifests"
          description={`Bounded run history for ${datasetRevision}.`}
          actions={
            <>
              <Link prefetch={false} className="action-link" href={`/datasets/${encodeURIComponent(datasetRevision)}`}>Back to dataset</Link>
              <a className="action-link" href={currentPageHref}>Refresh page</a>
            </>
          }
        />

        <BoundaryBanner>
          <strong>Local and read only.</strong>
          <span className="boundary-separator" aria-hidden="true">·</span>
            <span>This page lists bounded catalog metadata. Opening a detail verifies its manifest file; detail files above 8 MiB fail closed.</span>
        </BoundaryBanner>

        <section className="panel" aria-label="BTC ingestion runs">
          <PanelHeading
            kicker={datasetRevision}
            title="Ingestion runs"
            meta={`${catalog.manifests.length} shown · limit ${catalog.page.limit}`}
          />
          <InspectionTable
            caption="Bounded page of BTC ingestion manifest records"
            columns={["Manifest", "Requested UTC range", "Network requests", "Manifest SHA-256"]}
            rows={rows}
            emptyMessage="No ingestion manifests are attached to this dataset."
          />
        </section>

        <nav className="pagination-actions" aria-label="BTC ingestion manifest pages">
          {catalog.page.afterManifestId !== null ? (
            <Link
              prefetch={false}
              className="action-link"
              href={pageHref(datasetRevision, catalog.page.limit)}
              aria-label="First ingestion manifest page"
            >
              First page
            </Link>
          ) : null}
          {catalog.page.hasMore && catalog.page.nextAfterManifestId !== null ? (
            <Link
              prefetch={false}
              className="action-link"
              href={pageHref(datasetRevision, catalog.page.limit, catalog.page.nextAfterManifestId)}
              aria-label="Next ingestion manifest page"
            >
              Next page
            </Link>
          ) : null}
          <p className="pagination-status" role="status">
            Showing {catalog.manifests.length} manifest{catalog.manifests.length === 1 ? "" : "s"} on this page.
          </p>
        </nav>
      </div>
    </AppShell>
  );
}
