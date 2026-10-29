import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { BoundaryBanner, InspectionTable, PageHeading, PanelHeading, ServiceState } from "@/components/ui";
import {
  getBtcResearchRunPage,
  LocalApiError,
  type BtcResearchRunPage,
  type BtcResearchRunSummary,
} from "@/lib/market-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const DEFAULT_PAGE_LIMIT = 25;

function pageHref(engine: "b2" | "b3", limit: number, cursor?: string): string {
  const query = new URLSearchParams({ engine, limit: String(limit) });
  if (cursor !== undefined) query.set("after_run_id", cursor);
  return `/experiments?${query}`;
}

function runValues(run: BtcResearchRunSummary) {
  if (run.engine === "b2") {
    return [
      <Link prefetch={false} className="dataset-detail-link" href={`/experiments/b2/${encodeURIComponent(run.runId)}`}>
        {run.runId}
      </Link>,
      run.datasetRevision,
      new Intl.NumberFormat("en").format(run.sampleCount),
      run.baselines.join(" · "),
      <code className="dataset-fingerprint">{run.replayFingerprint}</code>,
    ];
  }
  return [
    <Link prefetch={false} className="dataset-detail-link" href={`/experiments/b3/${encodeURIComponent(run.runId)}`}>
      {run.runId}
    </Link>,
    run.datasetRevision,
    new Intl.NumberFormat("en").format(run.sampleCount),
    run.promotionDecision,
    <code className="dataset-fingerprint">{run.replayFingerprint}</code>,
  ];
}

export default async function BtcResearchRunsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  let engine: "b2" | "b3" = "b2";
  let catalog: BtcResearchRunPage;
  try {
    const query = await searchParams;
    if (Object.keys(query).some((key) => key !== "engine" && key !== "limit" && key !== "after_run_id")) {
      throw new LocalApiError("invalid");
    }
    const rawEngine = query.engine;
    const rawLimit = query.limit;
    const rawCursor = query.after_run_id;
    if (
      Array.isArray(rawEngine)
      || Array.isArray(rawLimit)
      || Array.isArray(rawCursor)
    ) {
      throw new LocalApiError("invalid");
    }
    if (rawEngine !== undefined && rawEngine !== "b2" && rawEngine !== "b3") throw new LocalApiError("invalid");
    engine = rawEngine ?? "b2";
    if (rawLimit !== undefined && (!/^[0-9]{1,3}$/.test(rawLimit) || Number(rawLimit) < 1 || Number(rawLimit) > 100)) {
      throw new LocalApiError("invalid");
    }
    if (rawCursor !== undefined && !new RegExp(`^btc-${engine}-[0-9a-f]{20}$`).test(rawCursor)) {
      throw new LocalApiError("invalid");
    }
    catalog = await getBtcResearchRunPage(engine, {
      limit: rawLimit === undefined ? DEFAULT_PAGE_LIMIT : Number(rawLimit),
      afterRunId: rawCursor,
    });
  } catch (error) {
    const kind = error instanceof LocalApiError ? error.kind : "unavailable";
    return (
      <AppShell current="experiments" gatewayStatus={kind === "unavailable" ? "unavailable" : "available"}>
        <div className="page-stack">
          <PageHeading
            eyebrow="B2 / B3 · offline research"
            title="BTC research runs"
            description="Inspect persisted numerical baselines and recorded-response reports."
          />
          <BoundaryBanner>
            <strong>Local and read only.</strong>
            <span className="boundary-separator" aria-hidden="true">·</span>
            <span>This page never starts or reruns an experiment. Run resources are read from the configured local artifact stores.</span>
          </BoundaryBanner>
          <ServiceState kind={kind} resource="BTC research runs" />
        </div>
      </AppShell>
    );
  }

  const rows = catalog.runs.map((run) => ({ key: run.runId, values: runValues(run) }));
  const currentPageHref = pageHref(engine, catalog.page.limit, catalog.page.afterRunId ?? undefined);
  const columns = engine === "b2"
    ? ["Run", "Dataset", "Evaluation samples", "Baselines", "Replay fingerprint"]
    : ["Run", "Dataset", "Evaluation samples", "Promotion", "Replay fingerprint"];

  return (
    <AppShell current="experiments" gatewayStatus="available">
      <div className="page-stack">
        <PageHeading
          eyebrow="B2 / B3 · offline research"
          title="BTC research runs"
          description="Persisted evaluation output from the configured local research store."
          actions={<a className="action-link" href={currentPageHref}>Refresh page</a>}
        />

        <BoundaryBanner>
          <strong>Local and read only.</strong>
          <span className="boundary-separator" aria-hidden="true">·</span>
          <span>Only existing runs are listed. Opening a result verifies its bounded metrics/report file; full replay remains a separate integrity check.</span>
        </BoundaryBanner>

        <nav className="pagination-actions" aria-label="BTC research engine">
          <Link prefetch={false} className="action-link" href="/experiments?engine=b2" aria-current={engine === "b2" ? "page" : undefined}>B2 baselines</Link>
          <Link prefetch={false} className="action-link" href="/experiments?engine=b3" aria-current={engine === "b3" ? "page" : undefined}>B3 comparison</Link>
        </nav>

        <section className="panel" aria-label={`${engine.toUpperCase()} run catalog`}>
          <PanelHeading
            kicker={engine === "b2" ? "deterministic baselines" : "recorded-response benchmark"}
            title={engine === "b2" ? "B2 numerical runs" : "B3 Jev-shaped comparisons"}
            meta={`${catalog.runs.length} shown · limit ${catalog.page.limit}`}
          />
          <InspectionTable
            caption={`Bounded page of ${engine.toUpperCase()} research runs`}
            columns={columns}
            rows={rows}
            emptyMessage={`No ${engine.toUpperCase()} runs are present in the configured local store.`}
          />
        </section>

        <nav className="pagination-actions" aria-label="BTC research run pages">
          {catalog.page.afterRunId !== null ? (
            <Link
              prefetch={false}
              className="action-link"
              href={pageHref(engine, catalog.page.limit)}
              aria-label="First research run page"
            >
              First page
            </Link>
          ) : null}
          {catalog.page.hasMore && catalog.page.nextAfterRunId !== null ? (
            <Link
              prefetch={false}
              className="action-link"
              href={pageHref(engine, catalog.page.limit, catalog.page.nextAfterRunId)}
              aria-label="Next research run page"
            >
              Next page
            </Link>
          ) : null}
          <p className="pagination-status" role="status">
            Showing {catalog.runs.length} {engine.toUpperCase()} run{catalog.runs.length === 1 ? "" : "s"} on this page.
          </p>
        </nav>
      </div>
    </AppShell>
  );
}
