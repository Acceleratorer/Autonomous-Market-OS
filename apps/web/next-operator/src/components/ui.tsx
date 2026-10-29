import type { ReactNode } from "react";

const LOCAL_GATEWAY_ADDRESS = `127.0.0.1:${process.env.MARKET_OS_API_PORT ?? "8787"}`;

type PageHeadingProps = {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
};

export function PageHeading({ eyebrow, title, description, actions }: PageHeadingProps) {
  return (
    <div className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="page-title">{title}</h1>
        <p className="page-description">{description}</p>
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </div>
  );
}

type MetricCardProps = {
  label: string;
  value: string | number;
  unit?: string;
};

export function MetricCard({ label, value, unit }: MetricCardProps) {
  return (
    <article className="metric-card">
      <div className="metric-label"><span className="metric-label-mark" aria-hidden="true" />{label}</div>
      <div className="metric-value-line">
        <strong className="metric-value">{value}</strong>
        {unit ? <span className="metric-unit">{unit}</span> : null}
      </div>
    </article>
  );
}

export type TableRow = { key: string; values: ReactNode[] };

type InspectionTableProps = {
  caption: string;
  columns: string[];
  rows: TableRow[];
  emptyMessage: string;
};

export function InspectionTable({ caption, columns, rows, emptyMessage }: InspectionTableProps) {
  return (
    <div className="table-scroll" role="region" aria-label={caption} tabIndex={0}>
      <table className="data-table">
        <caption>{caption}</caption>
        <thead>
          <tr>{columns.map((column) => <th key={column} scope="col">{column}</th>)}</tr>
        </thead>
        {rows.length ? (
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                {row.values.map((value, index) => (
                  <td key={`${row.key}-${index}`} className={index === 0 ? "mono-cell primary-cell" : "mono-cell"}>{value}</td>
                ))}
              </tr>
            ))}
          </tbody>
        ) : null}
      </table>
      {!rows.length ? <p className="empty-state m-3">{emptyMessage}</p> : null}
    </div>
  );
}

export function BoundaryBanner({ children }: { children: ReactNode }) {
  return (
    <section className="boundary-banner" aria-label="Paper-only boundary">
      <span className="boundary-symbol" aria-hidden="true">
        <svg width="15" height="15" viewBox="0 0 16 16" fill="none">
          <path d="M8 1.8 13 3.7v3.8c0 3.2-2.1 5.4-5 6.7-2.9-1.3-5-3.5-5-6.7V3.7l5-1.9Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
          <path d="m5.7 7.8 1.5 1.5 3.2-3.2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <div className="boundary-copy">{children}</div>
    </section>
  );
}

export function PanelHeading({ title, kicker, meta }: { title: string; kicker: string; meta?: string }) {
  return (
    <div className="panel-heading">
      <div>
        <p className="panel-kicker">{kicker}</p>
        <h2>{title}</h2>
      </div>
      {meta ? <span className="panel-meta">{meta}</span> : null}
    </div>
  );
}

export function ServiceState({
  kind,
  title,
  resource = "portfolio",
}: {
  kind: "unavailable" | "missing" | "rejected" | "invalid";
  title?: string;
  resource?: "portfolio" | "BTC dataset catalog" | "BTC dataset candles" | "BTC ingestion manifests" | "BTC ingestion manifest" | "BTC ingestion records" | "BTC research runs" | "BTC research run";
}) {
  const copy = resource === "portfolio"
    ? {
      unavailable: `Start the local gateway at ${LOCAL_GATEWAY_ADDRESS}, then reload this page.`,
      missing: "This portfolio is not present in the validated local catalog.",
      rejected: "The broker rejected inspection because its persisted state needs recovery review.",
      invalid: "The gateway response did not match the read-only portfolio contract.",
    }[kind]
    : resource === "BTC dataset catalog"
      ? {
        unavailable: `Start the local gateway at ${LOCAL_GATEWAY_ADDRESS}, then reload this page.`,
        missing: "This BTC history revision is not present in the local catalog.",
        rejected: "The local history catalog could not be read safely.",
        invalid: "The gateway response did not match the read-only BTC catalog contract.",
      }[kind]
      : resource === "BTC dataset candles"
        ? {
        unavailable: `Start the local gateway at ${LOCAL_GATEWAY_ADDRESS}, then reload this page.`,
        missing: "This BTC history revision or page cursor is not present in the local catalog.",
        rejected: "Stored BTC candle data failed its integrity checks.",
        invalid: "The gateway response did not match the read-only BTC candle contract.",
        }[kind]
        : resource === "BTC ingestion manifests" || resource === "BTC ingestion manifest" || resource === "BTC ingestion records"
          ? {
          unavailable: `Start the local gateway at ${LOCAL_GATEWAY_ADDRESS}, then reload this page.`,
          missing: "This BTC ingestion manifest is not present in the local catalog.",
          rejected: "Stored BTC ingestion-manifest data failed its integrity checks.",
          invalid: "The gateway response did not match the read-only BTC manifest contract.",
          }[kind]
          : {
            unavailable: `Start the local gateway at ${LOCAL_GATEWAY_ADDRESS}, then reload this page.`,
            missing: "No matching BTC research run is present in the configured local store.",
            rejected: "Stored BTC research metrics or report failed its integrity checks.",
            invalid: "The gateway response did not match the read-only BTC research contract.",
          }[kind];

  return (
    <section className="service-state" role="status">
      <h2>{title ?? (kind === "unavailable" ? "Local gateway unavailable" : `${resource} unavailable`)}</h2>
      <p>{copy}</p>
    </section>
  );
}
