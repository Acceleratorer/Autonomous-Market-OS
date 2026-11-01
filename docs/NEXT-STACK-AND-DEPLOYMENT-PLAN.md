# Next Stack and Deployment Plan

**Status:** Locally verified; U5.5 connected implementation is not enabled or promoted on the owner VM.
**Date:** 2026-11-01

The durable U5.5 decision is recorded in
[`ADR-0050`](decisions/ADR-0050-u5-5-runtime-identity-contract.md). The owner
selected the Linux VM/systemd/Tailscale Serve target; promotion remains gated
on the owner VM evidence.

## Recommended stack by responsibility

| Responsibility | Selected technology | Why |
|---|---|---|
| Domain, accounting, risk, persistence, replay | Python 3.11+ in `market_os/` | Existing authoritative implementation and test surface. |
| Local gateway transport | Python stdlib HTTP in `apps/gateway/` | Existing loopback boundary; no new framework is needed for local scope. |
| CLI | Python entrypoint through `apps/cli/` and `market_os.cli` | Keeps domain logic out of presentation and preserves compatibility. |
| Local/private browser operator | TypeScript, React, Next.js App Router, Node.js 20.9+, Tailwind CSS | Already implemented and verified locally in `apps/web/next-operator/`. |
| Disconnected public preview | Static HTML/CSS in `apps/web/public/` | No API, credentials, portfolio state, or mutation path. |
| Persistence | File-backed JSONL ledger plus JSON metadata/checkpoint | Existing append-only, fingerprinted, replayable authority. Do not add a database just for connected hosting. |
| Validation/testing | pytest, compileall, TypeScript check, Next build, Playwright, CI evidence | Existing verification path. |

## Immediate order

1. Review B4.18, B4.19, and B4.20 evidence; target-native recovery,
   local capability authorization, and read-only archive preflight are verified
   locally, while connected access remains separately gated.
2. Reconcile the selective product commit from the exact path inventory in
   `docs/WORKTREE-BASELINE-MANIFEST.json` (staging remains owner-authorized).
3. Use the selected Linux VM/systemd/Tailscale Serve target and the
   `deploy/u5-5/` promotion package.
4. Review the subject-to-portfolio and storage-isolation evidence for the
   selected target.
5. Run the owner-VM U5.5 matrix and promotion/rollback procedure before
   enabling access.
6. Maintain and revalidate the disconnected static preview separately; its
   current public artifact is live, while the private runtime remains gated.

## Connected runtime prerequisites

Connected web is not ready until all of these are selected and verified:

- always-on hosting runtime for Next.js and the Python gateway;
- reverse proxy or managed edge with HTTPS and request limits;
- identity provider/login method and stable subject identity;
- server-side subject-to-portfolio authorization;
- one-tenant storage isolation and explicit portfolio allowlist;
- identity propagation from ingress to Next.js to Python with forged-header
  rejection;
- bounded sessions, expiry, revocation, clock tolerance, and secure cookies;
- CSRF/origin policy for any future cookie-authenticated mutation;
- rate limits, body limits, timeouts, abuse responses, and denied-request audit;
- structured logs, retention, alerting, backup/restore, rollback, and operator
  access review;
- CI checks for authn/authz, cross-tenant denial, direct-origin denial,
  replayed/expired sessions, secrets, build, and dependency health.

## Candidate access paths

- **Tailscale Serve:** best fit when every operator device can join the private
  tailnet; keeps the app private and adds few hosting components.
- **Cloudflare Tunnel + Access:** best fit when browser-only access is needed;
  requires origin lockdown and server-side validation of the Access assertion.
- **WireGuard plus application OIDC:** most operator-owned, but adds VPN,
  certificate, peer lifecycle, and OIDC operations.

Tailscale Serve on the owner-controlled Linux VM is selected for U5.5. The
DirectAdmin decision applies only to the disconnected static artifact and must
not host the private Next.js/gateway path.

## Security rules carried into implementation

- Keep secrets server-only; never use `NEXT_PUBLIC_*` for credentials.
- Run `next build` and `next start` in any connected production runtime.
- Put a reverse proxy/edge layer in front of self-hosted Next.js.
- Enforce authorization in server-side handlers, not client UI.
- Keep current GET-only local operator unchanged until a versioned connected
  contract exists.
- Do not expose the Python gateway directly to the public Internet.

## Explicit non-goals

This plan does not authorize live trading, Binance, provider credentials,
public mutation routes, multi-tenant hosting, distributed broker ownership, or
promotion of the private connected runtime. The disconnected DirectAdmin static
preview is already deployed under separate evidence; any additional deployment
or scope change requires its own contract and evidence.
