import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { BoundaryBanner, InspectionTable, MetricCard, PageHeading, PanelHeading, ServiceState } from "@/components/ui";
import {
  getBtcResearchRun,
  LocalApiError,
  type BtcB2Metrics,
  type BtcB3Report,
  type BtcResearchRunDetail,
} from "@/lib/market-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function formatMetric(value: number | null): string {
  return value === null ? "—" : value.toFixed(6);
}

function FingerprintRow({ label, value }: { label: string; value: string }) {
  return (
    <>
      <span>{label}</span>
      <strong><code className="dataset-fingerprint">{value}</code></strong>
    </>
  );
}

function B2Results({ detail }: { detail: BtcResearchRunDetail }) {
  const run = detail.run;
  if (run.engine !== "b2") return null;
  const metrics = detail.result as BtcB2Metrics;
  const models = ["naive_0_5", "empirical_rate", "conditional_rate"] as const;
  const rows = models.map((model) => {
    const raw = metrics[model].raw;
    const calibrated = metrics[model].calibrated;
    return {
      key: model,
      values: [
        model,
        raw.status,
        String(raw.n),
        formatMetric(raw.logLoss),
        formatMetric(raw.brier),
        formatMetric(raw.accuracy),
        calibrated.status,
        String(calibrated.n),
        formatMetric(calibrated.logLoss),
        formatMetric(calibrated.brier),
        formatMetric(calibrated.accuracy),
      ],
    };
  });
  return (
    <>
      <section className="panel" aria-label="B2 baseline metrics">
        <PanelHeading kicker="frozen numerical baselines" title="Held-out test metrics" meta="Raw and calibrated" />
        {run.sampleCount === 0 ? (
          <div className="panel-body">
            <div className="empty-state">
              <h3>No leakage-safe test samples</h3>
              <p>The persisted evaluation has no eligible labels after gap, purge, and embargo rules. Metric values are unavailable.</p>
            </div>
          </div>
        ) : null}
        <InspectionTable
          caption="B2 baseline raw and calibrated metrics"
          columns={["Baseline", "Raw status", "Raw n", "Raw log loss", "Raw Brier", "Raw accuracy", "Calibrated status", "Calibrated n", "Calibrated log loss", "Calibrated Brier", "Calibrated accuracy"]}
          rows={rows}
          emptyMessage="No B2 baseline metrics are available."
        />
      </section>
      <section className="panel" aria-label="B2 run lineage">
        <PanelHeading kicker="B2 dataset lineage" title="Run fingerprints" />
        <div className="dataset-detail-meta">
          <FingerprintRow label="Dataset revision" value={run.datasetRevision} />
          <FingerprintRow label="Feature fingerprint" value={run.featureFingerprint} />
          <FingerprintRow label="Label fingerprint" value={run.labelFingerprint} />
          <FingerprintRow label="Replay fingerprint" value={run.replayFingerprint} />
        </div>
      </section>
    </>
  );
}

function B3Results({ detail }: { detail: BtcResearchRunDetail }) {
  const run = detail.run;
  if (run.engine !== "b3") return null;
  const report = detail.result as BtcB3Report;
  const arms = [
    ["E1 numerical only", report.coverage.E1_numerical_only],
    ["E2 numerical + Jev", report.coverage.E2_numerical_plus_jev],
  ] as const;
  const coverageRows = arms.map(([name, coverage]) => ({
    key: name,
    values: [
      name,
      coverage.status,
      String(coverage.candidateN),
      String(coverage.predictedN),
      String(coverage.abstentionN),
      formatMetric(coverage.coverage),
      Object.entries(coverage.outcomes).map(([outcome, count]) => `${outcome}: ${count}`).join(" · ") || "—",
    ],
  }));
  const matched = report.matchedControls;
  const scoreRows = [
    { key: "control", label: matched.control, score: matched.controlMetrics },
    { key: "candidate", label: matched.candidate, score: matched.candidateMetrics },
  ].map(({ key, label, score }) => ({
    key,
    values: [label, score.status, String(score.n), formatMetric(score.logLoss), formatMetric(score.brier), formatMetric(score.accuracy)],
  }));
  return (
    <>
      <section className="panel" aria-label="B3 test coverage">
        <PanelHeading kicker="same held-out split" title="Test coverage" meta={report.status} />
        <InspectionTable
          caption="B3 numerical and recorded-response test coverage"
          columns={["Experiment arm", "Status", "Candidates", "Predicted", "Abstained", "Coverage", "Observed outcomes"]}
          rows={coverageRows}
          emptyMessage="No B3 coverage rows are available."
        />
      </section>
      <section className="panel" aria-label="B3 matched-control metrics">
        <PanelHeading kicker={`${matched.n} identical test inputs`} title="Matched-control evaluation" meta={matched.status} />
        <div className="panel-body">
          <p className="panel-description">Candidate-minus-control deltas: log loss {formatMetric(matched.deltasCandidateMinusControl.log_loss ?? null)}, Brier {formatMetric(matched.deltasCandidateMinusControl.brier ?? null)}, accuracy {formatMetric(matched.deltasCandidateMinusControl.accuracy ?? null)}. Uncertainty: {matched.uncertainty.status}.</p>
        </div>
        <InspectionTable
          caption="B3 matched-control metrics on the identical input set"
          columns={["Arm", "Status", "n", "Log loss", "Brier", "Accuracy"]}
          rows={scoreRows}
          emptyMessage="Matched-control metrics are unavailable."
        />
      </section>
      <section className="panel" aria-label="B3 experiment definition and promotion boundary">
        <PanelHeading kicker={report.experiment.version} title="Experiment definition" />
        <div className="dataset-detail-meta">
          <FingerprintRow label="Dataset revision" value={run.datasetRevision} />
          <FingerprintRow label="Feature fingerprint" value={run.featureFingerprint} />
          <FingerprintRow label="Fixture fingerprint" value={run.fixtureFingerprint} />
          <FingerprintRow label="Request fingerprint" value={run.requestFingerprint} />
          <FingerprintRow label="Response fingerprint" value={run.responseFingerprint} />
          <FingerprintRow label="Replay fingerprint" value={run.replayFingerprint} />
          <span>Question</span><strong>{report.experiment.decisionQuestion}</strong>
          <span>Fixture cases</span><strong>{Object.entries(report.fixtureCaseKinds).map(([kind, count]) => `${kind}: ${count}`).join(" · ")}</strong>
          <span>Failures</span><strong>{Object.entries(report.failureCounts).map(([kind, count]) => `${kind}: ${count}`).join(" · ") || "None"}</strong>
          <span>Offline usage</span><strong>{report.latencyUsageCost.latency} · {report.latencyUsageCost.usage} · {report.latencyUsageCost.cost}</strong>
          <span>Source requests</span><strong>Network {report.sourceBoundary.networkRequests} · Provider {report.sourceBoundary.providerRequests}</strong>
        </div>
        <div className="panel-body">
          <h3 className="panel-subheading">Promotion: {report.promotion.decision}</h3>
          <p className="panel-description">{report.promotion.reason}</p>
          <p className="panel-description">{report.scientificBoundary}</p>
          <ul className="compact-list">
            {report.promotion.requiredNextEvidence.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
      </section>
    </>
  );
}

export default async function BtcResearchRunDetailPage({
  params,
}: {
  params: Promise<{ engine: string; runId: string }>;
}) {
  let engine: "b2" | "b3" = "b2";
  let runId = "";
  let detail: BtcResearchRunDetail;
  try {
    const values = await params;
    if (values.engine !== "b2" && values.engine !== "b3") throw new LocalApiError("missing");
    engine = values.engine;
    runId = values.runId;
    detail = await getBtcResearchRun(engine, runId);
  } catch (error) {
    const kind = error instanceof LocalApiError ? error.kind : "unavailable";
    return (
      <AppShell current="experimentDetail" gatewayStatus={kind === "unavailable" ? "unavailable" : "available"}>
        <div className="page-stack">
          <PageHeading
            eyebrow="B2 / B3 · offline research"
            title="BTC research run"
            description="Inspect persisted local evaluation results."
            actions={<Link prefetch={false} className="action-link" href="/experiments">Back to runs</Link>}
          />
          <BoundaryBanner>
            <strong>Local and read only.</strong>
            <span className="boundary-separator" aria-hidden="true">·</span>
            <span>Metrics/report artifacts are hash-checked before display; the page never re-runs research.</span>
          </BoundaryBanner>
          <ServiceState kind={kind} resource="BTC research run" />
        </div>
      </AppShell>
    );
  }

  const summary = detail.run;
  const datasetHref = `/datasets/${encodeURIComponent(summary.datasetRevision)}`;

  return (
    <AppShell current="experimentDetail" gatewayStatus="available">
      <div className="page-stack">
        <PageHeading
          eyebrow={`${engine.toUpperCase()} · persisted research`}
          title={engine === "b2" ? "BTC numerical baseline run" : "BTC recorded-response comparison"}
          description={summary.runId}
          actions={
            <>
              <Link prefetch={false} className="action-link" href={`/experiments?engine=${engine}`}>Back to runs</Link>
              <Link prefetch={false} className="action-link" href={datasetHref}>Source dataset</Link>
            </>
          }
        />

        <BoundaryBanner>
          <strong>Local and read only.</strong>
          <span className="boundary-separator" aria-hidden="true">·</span>
          <span>The displayed metrics/report file passed its stored SHA-256 check. Full artifact replay remains the complete run-integrity check.</span>
        </BoundaryBanner>

        <section className="metric-grid" aria-label="Research run summary">
          <MetricCard label="Evaluation samples" value={new Intl.NumberFormat("en").format(summary.sampleCount)} />
          <MetricCard label="Persisted artifacts" value={summary.artifactCount} />
          <MetricCard label="Run access" value="GET only" />
          {summary.engine === "b3" ? <MetricCard label="Promotion" value={summary.promotionDecision} /> : null}
        </section>

        {summary.engine === "b2" ? <B2Results detail={detail} /> : <B3Results detail={detail} />}
      </div>
    </AppShell>
  );
}
