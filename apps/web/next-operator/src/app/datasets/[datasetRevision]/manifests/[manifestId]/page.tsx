import Link from "next/link";
import type { ReactNode } from "react";
import { AppShell } from "@/components/app-shell";
import { BoundaryBanner, MetricCard, PageHeading, PanelHeading, ServiceState } from "@/components/ui";
import {
  getBtcHistoryManifest,
  LocalApiError,
  type BtcIngestionManifest,
} from "@/lib/market-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_JS_DATE_TIME_MS = 8_640_000_000_000_000;

function formatUtc(timestampMs: number): string {
  return new Date(timestampMs).toISOString().replace(".000Z", "Z");
}

function formatTimestamp(value: string | null): string {
  if (value === null) return "Not recorded";
  return new Date(value).toISOString().replace(".000Z", "Z");
}

function range(start: number | null, end: number | null): string {
  if (start === null || end === null || start > MAX_JS_DATE_TIME_MS || end > MAX_JS_DATE_TIME_MS) {
    return "Not observed";
  }
  return `${formatUtc(start)} → ${formatUtc(end)} (end exclusive)`;
}

function MetaRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <span>{label}</span>
      <strong>{children}</strong>
    </>
  );
}

export default async function BtcManifestDetailPage({
  params,
}: {
  params: Promise<{ datasetRevision: string; manifestId: string }>;
}) {
  let datasetRevision = "";
  let manifestId = "";
  let manifest: BtcIngestionManifest;
  try {
    ({ datasetRevision, manifestId } = await params);
    manifest = await getBtcHistoryManifest(datasetRevision, manifestId);
  } catch (error) {
    const kind = error instanceof LocalApiError ? error.kind : "unavailable";
    return (
      <AppShell current="datasetDetail" gatewayStatus={kind === "unavailable" ? "unavailable" : "available"}>
        <div className="page-stack">
          <PageHeading
            eyebrow="B1 · ingestion run"
            title="BTC ingestion manifest"
            description="Inspect hash-verified metadata for one local ingestion run."
            actions={<Link prefetch={false} className="action-link" href="/datasets">Back to registry</Link>}
          />
          <BoundaryBanner>
            <strong>Local and read only.</strong>
            <span className="boundary-separator" aria-hidden="true">·</span>
            <span>Only fixed summary fields and collection counts are shown; paths and raw provenance remain local.</span>
          </BoundaryBanner>
          <ServiceState kind={kind} resource="BTC ingestion manifest" />
        </div>
      </AppShell>
    );
  }

  const manifestsHref = `/datasets/${encodeURIComponent(datasetRevision)}/manifests`;
  const datasetHref = `/datasets/${encodeURIComponent(datasetRevision)}`;
  const sortedOutcomes = Object.entries(manifest.outcomeCounts).sort(([left], [right]) => left.localeCompare(right));

  return (
    <AppShell current="datasetDetail" gatewayStatus="available">
      <div className="page-stack">
        <PageHeading
          eyebrow="B1 · ingestion run"
          title="BTC ingestion manifest"
          description={`${manifest.symbol} ${manifest.interval} · ${manifest.manifestId}`}
          actions={
            <>
              <Link prefetch={false} className="action-link" href={manifestsHref}>Back to ingestion runs</Link>
              <Link prefetch={false} className="action-link" href={datasetHref}>Dataset detail</Link>
            </>
          }
        />

        <BoundaryBanner>
          <strong>Local and read only.</strong>
          <span className="boundary-separator" aria-hidden="true">·</span>
          <span>The manifest file is hash-checked before display. Gap, parent, and raw-page arrays are reduced to counts; canonical replay remains the integrity check.</span>
        </BoundaryBanner>

        <section className="metric-grid" aria-label="Ingestion run counts">
          <MetricCard label="Canonical candles" value={new Intl.NumberFormat("en").format(manifest.canonicalCandleCount)} />
          <MetricCard label="Raw records" value={new Intl.NumberFormat("en").format(manifest.rawRecordCount)} />
          <MetricCard label="Network requests" value={manifest.networkRequests} />
          <MetricCard label="Gaps" value={manifest.gapCount} />
        </section>

        <section className="panel" aria-label="Ingestion run metadata">
          <PanelHeading kicker={manifest.endpointClass} title="Run metadata" meta={manifest.endpointHost ?? "Local fixture"} />
          <div className="dataset-detail-meta">
            <MetaRow label="Dataset revision"><Link prefetch={false} href={datasetHref}>{manifest.datasetRevision}</Link></MetaRow>
            <MetaRow label="Run ID"><code className="dataset-fingerprint">{manifest.runId}</code></MetaRow>
            <MetaRow label="Source identity">{manifest.sourceIdentity}</MetaRow>
            <MetaRow label="Requested UTC range">{range(manifest.requestedStartMs, manifest.requestedEndMsExclusive)}</MetaRow>
            <MetaRow label="Observed UTC range">{range(manifest.observedStartMs, manifest.observedEndMsExclusive)}</MetaRow>
            <MetaRow label="Source timestamps">{formatTimestamp(manifest.sourceTimestampMin)} → {formatTimestamp(manifest.sourceTimestampMax)}</MetaRow>
            <MetaRow label="Receipt timestamps">{formatTimestamp(manifest.receiptTimestampMin)} → {formatTimestamp(manifest.receiptTimestampMax)}</MetaRow>
            <MetaRow label="Latest availability">{formatTimestamp(manifest.availabilityTimestampMax)}</MetaRow>
            <MetaRow label="Canonicalized at">{formatTimestamp(manifest.canonicalizationTimestamp)}</MetaRow>
            <MetaRow label="Raw records / pages">{manifest.rawRecordCount} / {manifest.rawPageCount}</MetaRow>
            <MetaRow label="Gap / parent counts">{manifest.gapCount} / {manifest.parentRevisionCount}</MetaRow>
            <MetaRow label="Runtime">Python {manifest.pythonVersion} · DuckDB {manifest.packageVersions.duckdb} · PyArrow {manifest.packageVersions.pyarrow}</MetaRow>
          </div>
        </section>

        <section className="panel" aria-label="Ingestion integrity fingerprints">
          <PanelHeading kicker={manifest.schema} title="Integrity fingerprints" />
          <div className="dataset-detail-meta">
            <MetaRow label="Manifest SHA-256"><code className="dataset-fingerprint">{manifest.manifestSha256}</code></MetaRow>
            <MetaRow label="Raw fingerprint"><code className="dataset-fingerprint">{manifest.rawFingerprint}</code></MetaRow>
            <MetaRow label="Canonical fingerprint"><code className="dataset-fingerprint">{manifest.canonicalFingerprint}</code></MetaRow>
            <MetaRow label="Outcome fingerprint"><code className="dataset-fingerprint">{manifest.outcomeFingerprint}</code></MetaRow>
            <MetaRow label="Parquet SHA-256"><code className="dataset-fingerprint">{manifest.parquetSha256}</code></MetaRow>
            <MetaRow label="Contract version">{manifest.contractVersion} · {manifest.apiVersion}</MetaRow>
          </div>
        </section>

        <section className="panel" aria-label="Ingestion outcome counts">
          <PanelHeading kicker="bounded counts" title="Record outcomes" meta={`${sortedOutcomes.length} categories`} />
          <div className="dataset-detail-meta">
            {sortedOutcomes.length ? sortedOutcomes.map(([name, count]) => (
              <MetaRow key={name} label={name}>{new Intl.NumberFormat("en").format(count)}</MetaRow>
            )) : <MetaRow label="Outcomes">No outcome counts recorded</MetaRow>}
          </div>
        </section>

        <section className="panel" aria-label="Ingestion record detail pages">
          <PanelHeading kicker="bounded record pages" title="Inspect run records" meta="Read only" />
          <nav className="pagination-actions panel-body" aria-label="Ingestion record types">
            <Link prefetch={false} className="action-link" href={`${manifestsHref}/${encodeURIComponent(manifestId)}/outcomes`}>Outcomes</Link>
            <Link prefetch={false} className="action-link" href={`${manifestsHref}/${encodeURIComponent(manifestId)}/gaps`}>Gaps</Link>
            <Link prefetch={false} className="action-link" href={`${manifestsHref}/${encodeURIComponent(manifestId)}/provenance`}>Raw provenance</Link>
          </nav>
        </section>
      </div>
    </AppShell>
  );
}
