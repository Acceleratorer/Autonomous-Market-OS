import Link from "next/link";
import type { ReactNode } from "react";

type AppShellProps = {
  children: ReactNode;
  current:
    | "overview"
    | "registry"
    | "portfolio"
    | "datasets"
    | "datasetDetail"
    | "experiments"
    | "experimentDetail";
  gatewayStatus?: "available" | "unavailable" | "unknown";
};

function navigationCurrent(
  current: AppShellProps["current"],
  page: AppShellProps["current"],
  detail?: AppShellProps["current"],
): "page" | "location" | undefined {
  if (current === page) return "page";
  if (detail !== undefined && current === detail) return "location";
  return undefined;
}

function BrandMark() {
  return (
    <svg aria-hidden="true" width="20" height="20" viewBox="0 0 20 20" fill="none">
      <path d="M3 14.5 7.4 10l3.1 2.8L17 5.8" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12.8 5.8H17v4.1" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PortfolioIcon() {
  return (
    <svg aria-hidden="true" className="nav-icon" width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="2.25" y="2.25" width="4.25" height="4.25" rx="1" stroke="currentColor" strokeWidth="1.3" />
      <rect x="9.5" y="2.25" width="4.25" height="4.25" rx="1" stroke="currentColor" strokeWidth="1.3" />
      <rect x="2.25" y="9.5" width="4.25" height="4.25" rx="1" stroke="currentColor" strokeWidth="1.3" />
      <rect x="9.5" y="9.5" width="4.25" height="4.25" rx="1" stroke="currentColor" strokeWidth="1.3" />
    </svg>
  );
}

function OverviewIcon() {
  return (
    <svg aria-hidden="true" className="nav-icon" width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M2 2.5h4.5v4.25H2zM9.5 2.5H14v7h-4.5zM2 9.75h4.5V14H2zM9.5 12h4.5v2h-4.5z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
    </svg>
  );
}

function DatasetIcon() {
  return (
    <svg aria-hidden="true" className="nav-icon" width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M2.25 3.25c0-1.1 2.57-2 5.75-2s5.75.9 5.75 2-2.57 2-5.75 2-5.75-.9-5.75-2Z" stroke="currentColor" strokeWidth="1.3" />
      <path d="M2.25 3.25v4.5c0 1.1 2.57 2 5.75 2s5.75-.9 5.75-2v-4.5M2.25 7.75v4.5c0 1.1 2.57 2 5.75 2s5.75-.9 5.75-2v-4.5" stroke="currentColor" strokeWidth="1.3" />
    </svg>
  );
}

function ResearchIcon() {
  return (
    <svg aria-hidden="true" className="nav-icon" width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M2.25 13.5h11.5M3.5 11V7.5m4.5 3.5V3.5m4.5 8V5.75" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" />
    </svg>
  );
}

export function AppShell({ children, current, gatewayStatus = "unknown" }: AppShellProps) {
  const gatewayAddress = `127.0.0.1:${process.env.MARKET_OS_API_PORT ?? "8787"}`;
  const gatewayLabel = {
    available: "Gateway available",
    unavailable: "Gateway unavailable",
    unknown: "Gateway not checked",
  }[gatewayStatus];
  const currentLabel = {
    overview: "Operator overview",
    registry: "Portfolio registry",
    portfolio: "Portfolio detail",
    datasets: "BTC dataset registry",
    datasetDetail: "BTC dataset detail",
    experiments: "BTC research runs",
    experimentDetail: "BTC research detail",
  }[current];

  return (
    <div className="app-layout">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <aside className="sidebar">
        <Link className="brand-link" href="/overview" aria-label="Market OS local operator home">
          <span className="brand-mark"><BrandMark /></span>
          <span>
            <span className="brand-name">MARKET OS</span>
            <span className="brand-subtitle">Operator workspace</span>
          </span>
        </Link>

        <p className="nav-label">Workspace</p>
        <nav aria-label="Primary navigation">
          <Link className="nav-link" href="/overview" aria-current={navigationCurrent(current, "overview")}>
            <OverviewIcon />
            <span>Overview</span>
          </Link>
          <Link
            className="nav-link"
            href="/"
            aria-current={navigationCurrent(current, "registry", "portfolio")}
          >
            <PortfolioIcon />
            <span>Portfolios</span>
          </Link>
          <Link
            className="nav-link"
            href="/datasets"
            aria-current={navigationCurrent(current, "datasets", "datasetDetail")}
          >
            <DatasetIcon />
            <span>BTC datasets</span>
          </Link>
          <Link
            className="nav-link"
            href="/experiments"
            aria-current={navigationCurrent(current, "experiments", "experimentDetail")}
          >
            <ResearchIcon />
            <span>BTC research</span>
          </Link>
        </nav>

        <div className="sidebar-spacer" />
        <section className="service-card" aria-label="Local gateway address">
          <div className="service-card-heading"><span className={`service-dot service-dot-${gatewayStatus}`} aria-hidden="true" />{gatewayLabel}</div>
          <p>{gatewayAddress}</p>
        </section>
        <p className="sidebar-note">Local research data · paper-only broker</p>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="crumb">
            <span>Local workspace</span>
            <span className="crumb-separator" aria-hidden="true">/</span>
            <span aria-current="page">{currentLabel}</span>
          </div>
          <div className="topbar-tags" role="group" aria-label="Environment boundaries">
            <span className="topbar-tag topbar-tag-local">Local only</span>
            <span className="topbar-tag">Read only</span>
          </div>
        </header>

        <main id="main-content" className="main-content" tabIndex={-1}>{children}</main>

        <footer className="footer-note">
          <span>GET-only local inspection · paper-only broker</span>
          <span>No credentials · no provider calls · no live venue</span>
        </footer>
      </div>
    </div>
  );
}
