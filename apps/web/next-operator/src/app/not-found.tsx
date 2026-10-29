import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { PageHeading, ServiceState } from "@/components/ui";

export default function NotFound() {
  return (
    <AppShell current="registry" gatewayStatus="unknown">
      <div className="page-stack">
        <PageHeading
          eyebrow="Local portfolio inspection"
          title="Portfolio not found"
          description="The requested route does not identify a valid local portfolio."
          actions={<Link className="action-link" href="/">Back to portfolios</Link>}
        />
        <ServiceState kind="missing" />
      </div>
    </AppShell>
  );
}
