import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { BoundaryBanner, InspectionTable, MetricCard, PageHeading, PanelHeading, ServiceState, type TableRow } from "@/components/ui";
import {
  getBtcIngestionGapsPage,
  getBtcIngestionOutcomesPage,
  getBtcIngestionProvenancePage,
  LocalApiError,
} from "@/lib/market-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const DEFAULT_PAGE_LIMIT = 25;
const MAX_JS_DATE_TIME_MS = 8_640_000_000_000_000;
type RecordType = "outcomes" | "gaps" | "provenance";
type RecordCursor = number | { rawPageSha256: string; rowIndex: number } | null;

function formatUtc(timestampMs: number): string {
  return new Date(timestampMs).toISOString().replace(".000Z", "Z");
}

function recordHref(datasetRevision: string, manifestId: string, type: RecordType, limit: number, cursor: RecordCursor): string {
  const query = new URLSearchParams({ limit: String(limit) });
  if (type === "outcomes" && typeof cursor === "number") query.set("after_outcome_index", String(cursor));
  if (type === "gaps" && typeof cursor === "number") query.set("after_start_time_ms", String(cursor));
  if (type === "provenance" && cursor !== null && typeof cursor === "object") {
    query.set("after_raw_page_sha256", cursor.rawPageSha256);
    query.set("after_row_index", String(cursor.rowIndex));
  }
  return `/datasets/${encodeURIComponent(datasetRevision)}/manifests/${encodeURIComponent(manifestId)}/${type}?${query}`;
}

function readSingle(query: Record<string, string | string[] | undefined>, name: string): string | undefined {
  const value = query[name];
  if (Array.isArray(value)) throw new LocalApiError("invalid");
  return value;
}

export default async function BtcManifestRecordsPage({
  params,
  searchParams,
}: {
  params: Promise<{ datasetRevision: string; manifestId: string; recordType: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  let datasetRevision = "";
  let manifestId = "";
  let recordType: RecordType = "outcomes";
  let kind: "unavailable" | "missing" | "rejected" | "invalid" = "unavailable";
  let loaded = false;
  let title = "BTC ingestion records";
  let description = "Inspect bounded outcomes, data gaps, or raw provenance for one local ingestion run.";
  let limit = DEFAULT_PAGE_LIMIT;
  let after: RecordCursor = null;
  let next: RecordCursor = null;
  let hasMore = false;
  let totalCount = 0;
  let rows: TableRow[] = [];
  let columns: string[] = [];
  let emptyMessage = "No records are present for this view.";

  try {
    const route = await params;
    datasetRevision = route.datasetRevision;
    manifestId = route.manifestId;
    if (!["outcomes", "gaps", "provenance"].includes(route.recordType)) throw new LocalApiError("missing");
    recordType = route.recordType as RecordType;
    const query = await searchParams;
    const allowed = recordType === "outcomes" ? ["limit", "after_outcome_index"]
      : recordType === "gaps" ? ["limit", "after_start_time_ms"]
        : ["limit", "after_raw_page_sha256", "after_row_index"];
    if (Object.keys(query).some((name) => !allowed.includes(name))) throw new LocalApiError("invalid");
    const rawLimit = readSingle(query, "limit");
    if (rawLimit !== undefined) {
      if (!/^[0-9]{1,3}$/.test(rawLimit) || Number(rawLimit) < 1 || Number(rawLimit) > 100) throw new LocalApiError("invalid");
      limit = Number(rawLimit);
    }

    if (recordType === "outcomes") {
      title = "BTC ingestion outcomes";
      description = `Bounded classification results for ${manifestId}.`;
      emptyMessage = "This ingestion run recorded no raw-row outcomes.";
      const rawCursor = readSingle(query, "after_outcome_index");
      if (rawCursor !== undefined) {
        if (!/^[0-9]{1,6}$/.test(rawCursor) || Number(rawCursor) > 200_000) throw new LocalApiError("invalid");
        after = Number(rawCursor);
      }
      const page = await getBtcIngestionOutcomesPage(datasetRevision, manifestId, {
        limit,
        afterOutcomeIndex: typeof after === "number" ? after : undefined,
      });
      totalCount = page.totalCount;
      hasMore = page.page.hasMore;
      next = page.page.nextAfter;
      columns = ["Outcome", "Status", "Open time (UTC)", "Canonical", "Raw page / row", "Record SHA-256", "Reason"];
      rows = page.records.map((row) => ({
        key: String(row.outcomeIndex),
        values: [
          String(row.outcomeIndex),
          row.status,
          row.openTimeMs === null ? "—" : formatUtc(row.openTimeMs),
          row.acceptedCanonical ? "Yes" : "No",
          <span key="source">{row.rawPageSha256.slice(0, 12)}… / {row.rowIndex}</span>,
          <code key="fingerprint" className="dataset-fingerprint">{row.sourceRecordFingerprint}</code>,
          row.reason === null ? "—" : <span key="reason">{row.reason}{row.reasonTruncated ? " …" : ""}</span>,
        ],
      }));
    } else if (recordType === "gaps") {
      title = "BTC ingestion gaps";
      description = `Missing one minute or more in ${manifestId}'s canonical candle sequence.`;
      emptyMessage = "No missing candle intervals were recorded for this run.";
      const rawCursor = readSingle(query, "after_start_time_ms");
      if (rawCursor !== undefined) {
        if (!/^[0-9]{1,16}$/.test(rawCursor) || Number(rawCursor) > MAX_JS_DATE_TIME_MS) throw new LocalApiError("invalid");
        after = Number(rawCursor);
      }
      const page = await getBtcIngestionGapsPage(datasetRevision, manifestId, {
        limit,
        afterStartTimeMs: typeof after === "number" ? after : undefined,
      });
      totalCount = page.totalCount;
      hasMore = page.page.hasMore;
      next = page.page.nextAfter;
      columns = ["Start (UTC)", "End (UTC, exclusive)", "Missing minutes"];
      rows = page.records.map((row) => ({
        key: String(row.startTimeMs),
        values: [formatUtc(row.startTimeMs), formatUtc(row.endTimeMs), String((row.endTimeMs - row.startTimeMs) / 60_000)],
      }));
    } else {
      title = "BTC raw provenance";
      description = `Hash-verified raw-row previews associated with ${manifestId}.`;
      emptyMessage = "No raw-row provenance records are present for this run.";
      const rawHash = readSingle(query, "after_raw_page_sha256");
      const rawRowIndex = readSingle(query, "after_row_index");
      if ((rawHash === undefined) !== (rawRowIndex === undefined)) throw new LocalApiError("invalid");
      if (rawHash !== undefined && rawRowIndex !== undefined) {
        if (!/^[0-9a-f]{64}$/.test(rawHash) || !/^[0-9]{1,3}$/.test(rawRowIndex) || Number(rawRowIndex) >= 1000) {
          throw new LocalApiError("invalid");
        }
        after = { rawPageSha256: rawHash, rowIndex: Number(rawRowIndex) };
      }
      const page = await getBtcIngestionProvenancePage(datasetRevision, manifestId, {
        limit,
        afterRawPageSha256: after && typeof after === "object" ? after.rawPageSha256 : undefined,
        afterRowIndex: after && typeof after === "object" ? after.rowIndex : undefined,
      });
      totalCount = page.totalCount;
      hasMore = page.page.hasMore;
      next = page.page.nextAfter;
      columns = ["Raw page SHA-256", "Row", "Record SHA-256", "Payload bytes", "Raw JSON preview"];
      rows = page.records.map((row) => ({
        key: `${row.rawPageSha256}-${row.rowIndex}`,
        values: [
          <code key="page" className="dataset-fingerprint">{row.rawPageSha256}</code>,
          String(row.rowIndex),
          <code key="fingerprint" className="dataset-fingerprint">{row.sourceRecordFingerprint}</code>,
          String(row.payloadBytes),
          <code key="preview" className="btc-payload-preview">{row.payloadPreview}{row.payloadTruncated ? " … [truncated]" : ""}</code>,
        ],
      }));
    }
    loaded = true;
  } catch (error) {
    kind = error instanceof LocalApiError ? error.kind : "unavailable";
  }

  const manifestHref = `/datasets/${encodeURIComponent(datasetRevision)}/manifests/${encodeURIComponent(manifestId)}`;
  const currentHref = recordHref(datasetRevision, manifestId, recordType, limit, after);
  const firstHref = recordHref(datasetRevision, manifestId, recordType, limit, null);
  const recordTypes: RecordType[] = ["outcomes", "gaps", "provenance"];
  const typeLabels: Record<RecordType, string> = { outcomes: "Outcomes", gaps: "Gaps", provenance: "Raw provenance" };

  return (
    <AppShell current="datasetDetail" gatewayStatus={!loaded && kind === "unavailable" ? "unavailable" : "available"}>
      <div className="page-stack">
        <PageHeading
          eyebrow="B1 · ingestion run details"
          title={title}
          description={description}
          actions={
            <>
              <Link prefetch={false} className="action-link" href={manifestHref}>Manifest</Link>
              <Link prefetch={false} className="action-link" href="/datasets">Dataset registry</Link>
              {loaded ? <a className="action-link" href={currentHref}>Refresh page</a> : null}
            </>
          }
        />
        <BoundaryBanner>
          <strong>Local and read only.</strong>
          <span className="boundary-separator" aria-hidden="true">·</span>
          <span>Pages contain at most 100 rows. Provenance verifies full-row fingerprints and shows a 512-character preview.</span>
        </BoundaryBanner>
        {!loaded ? <ServiceState kind={kind} resource="BTC ingestion records" /> : null}
        {loaded ? (
          <>
            <nav className="pagination-actions" aria-label="BTC ingestion record types">
              {recordTypes.map((type) => (
                <Link key={type} prefetch={false} className="action-link" href={recordHref(datasetRevision, manifestId, type, DEFAULT_PAGE_LIMIT, null)} aria-current={type === recordType ? "page" : undefined}>
                  {typeLabels[type]}
                </Link>
              ))}
            </nav>
            <section className="metric-grid" aria-label="Current record page">
              <MetricCard label="Records in run" value={new Intl.NumberFormat("en").format(totalCount)} />
              <MetricCard label="Rows shown" value={rows.length} />
              <MetricCard label="Page limit" value={limit} />
            </section>
            <section className="panel" aria-label={title}>
              <PanelHeading kicker={manifestId} title={title} meta={`${rows.length} shown · ${totalCount} total`} />
              <InspectionTable caption={`Bounded ${recordType} from one BTC ingestion run`} columns={columns} rows={rows} emptyMessage={emptyMessage} />
            </section>
            <nav className="pagination-actions" aria-label={`${title} pages`}>
              {after !== null ? <Link prefetch={false} className="action-link" href={firstHref}>First page</Link> : null}
              {hasMore && next !== null ? <Link prefetch={false} className="action-link" href={recordHref(datasetRevision, manifestId, recordType, limit, next)}>Next page</Link> : null}
              <p className="pagination-status" role="status">Showing {rows.length} {recordType} record{rows.length === 1 ? "" : "s"} · {totalCount} total.</p>
            </nav>
          </>
        ) : null}
      </div>
    </AppShell>
  );
}
