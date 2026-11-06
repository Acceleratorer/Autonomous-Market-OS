import { AppShell } from "@/components/app-shell";
import {
  BoundaryBanner,
  EventStream,
  EvidenceChain,
  FingerprintRow,
  PageHeading,
  RuntimePanel,
} from "@/components/ui";
import { getReleaseMetadata } from "@/lib/release-metadata";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default function RuntimeReleasePage() {
  const release = getReleaseMetadata();
  const signedLocally = release.signature.startsWith("Verified");

  return (
    <AppShell current="runtime" gatewayStatus="unknown">
      <div className="page-stack runtime-page">
        <PageHeading
          eyebrow="U6.4 · release observation"
          title="Runtime / release status"
          description="A read-only view of the local shell boundary and the release gates that remain open."
        />

        <BoundaryBanner>
          <strong>Local, paper-only, and execution disabled.</strong>
          <span className="boundary-separator" aria-hidden="true">·</span>
          <span>{signedLocally
            ? "U6.4-B signing and slot verification are observable locally; owner-VM promotion remains gated."
            : "U6.4-A unsigned artifact is observable; signing, promotion, and rollback remain gated."}</span>
        </BoundaryBanner>

        <RuntimePanel
          version={release.version}
          sidecar={release.sidecar}
          signature={release.signature}
          currentSlot={release.currentSlot}
          knownGoodSlot={release.knownGoodSlot}
          rollback={release.rollback}
        />

        <section className="panel" aria-label="Release identity">
          <div className="panel-heading">
            <div className="panel-heading-copy">
              <h2>Release identity</h2>
              <span className="panel-kicker">provenance / bounded snapshot</span>
            </div>
            <span className="panel-meta">READ ONLY</span>
          </div>
          <div className="dataset-detail-meta">
            <FingerprintRow label="Renderer" value="Next.js server-rendered operator" />
            <FingerprintRow label="Native shell" value="Electron · U6.3 local slice" />
            <FingerprintRow label="Transport" value="http://127.0.0.1:<port> only" />
            <FingerprintRow label="Connected access" value="Pending owner-VM promotion + rollback (U5.5)" />
          </div>
        </section>

        <section className="runtime-lower-grid" aria-label="Release evidence">
          <section className="panel">
            <div className="panel-heading">
              <div className="panel-heading-copy">
                <h2>Evidence chain</h2>
                <span className="panel-kicker">renderer → shell → release gate</span>
              </div>
            </div>
            <div className="panel-body">
              <EvidenceChain
                items={[
                  { label: "Renderer", value: "Next.js operator", href: "/overview" },
                  { label: "Local shell", value: "Electron U6.3" },
                  { label: "Release gate", value: "U6.4-B signing / promotion / rollback" },
                  { label: "Connected runtime", value: "U5.5 owner-VM promotion + rollback pending" },
                ]}
              />
            </div>
          </section>

          <section className="panel">
            <div className="panel-heading">
              <div className="panel-heading-copy">
                <h2>Event stream</h2>
                <span className="panel-kicker">append-only local observations</span>
              </div>
              <span className="panel-meta">4 EVENTS</span>
            </div>
            <EventStream
              items={[
                { sequence: "0001", label: "U6.1 shell parity", detail: "Next.js overview and dataset catalog verified", status: "verified" },
                { sequence: "0002", label: "U6.2 platform", detail: "Electron selected for Windows/Linux shell", status: "accepted" },
                { sequence: "0003", label: "U6.3 lifecycle", detail: "Loopback child-process smoke passed", status: "verified" },
                { sequence: "0004", label: signedLocally ? "U6.4-B release contract" : "U6.4-A artifact", detail: signedLocally ? "Signature, promotion, and rollback checks passed locally" : "Unsigned package smoke passed; signing and rollback remain open", status: "verified" },
              ]}
            />
          </section>
        </section>
      </div>
    </AppShell>
  );
}
