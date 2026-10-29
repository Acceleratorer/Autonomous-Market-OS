# U5.5 connected web options

**Checked:** 2026-10-29
**Status:** Owner selected the private single-tenant preview scope on 2026-10-29. The host, identity provider/login method, and deployment remain unselected and disabled.

## Repository constraints

- U5.8 uses a Node.js Next.js server for the browser and keeps portfolio identity, accounting, risk, recovery, and persistence in the Python gateway. The current app is loopback-only and read-only. [U5.8 contract](../U5.8-NEXT-LOCAL-OPERATOR-WEB.md)
- B4.13's local broker uses process/portfolio writer locks and rejects stale writers until reload; distributed ownership and network locks are not part of that contract. [B4.13 contract](../B4.13-CONCURRENCY-CONTRACT.md)
- U5.5 requires subject-to-resource authorization, storage isolation, session/revocation policy, request limits, production observability, backup/rollback, and operator access review before connected access. [U5.5 contract](../U5.5-AUTHENTICATED-CONNECTED-WEB-CONTRACT.md)

## Selected direction

The owner selected a private, single-tenant, read-only preview and selected TypeScript/React/Node.js/Next.js/Tailwind CSS for its browser-facing application. This chooses scope and framework, not a hosting vendor or identity provider. The number of allowed user subjects inside that tenant remains open; one owner subject is the smallest proposed preview. Keep portfolio accounting, recovery, authorization, and persistence in Python. Do not expose the current loopback API or enable connected access until the U5.5 promotion criteria are met.

## Candidate access paths

### Tailscale Serve on an owner-controlled private host — recommended when clients can join the tailnet

Run Next.js and the Python gateway on one owner-controlled, always-on host. Keep both application services bound to loopback and use Tailscale Serve to provide HTTPS access only from the tailnet. Serve access is subject to the tailnet's access-control policy. [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve) · [Tailscale access control](https://tailscale.com/docs/features/access-control)

Tailscale does not provide user identity. It delegates user authentication to the OIDC identity provider configured for the tailnet; the owner must identify that provider before implementation. Serve adds identity headers to tailnet requests and strips spoofed copies. A local process can still call a loopback service directly with its own headers, so this candidate assumes local host users and processes are trusted. Tailscale recommends keeping a backend that trusts these headers on localhost. [Tailscale identity](https://tailscale.com/docs/concepts/tailscale-identity) · [Serve identity headers](https://tailscale.com/docs/features/tailscale-serve)

The identity arrives at Next.js, while the Python gateway receives a separate server-side request. A versioned, fail-closed identity propagation and verification path from Next.js to Python is still required; neither service may authorize from an unverified subject header.

This fits the current file-backed store and one-writer model with the fewest new hosting components. The host must remain online, clients must be in the tailnet, and storage backup, restore, and host patching remain operator responsibilities. If the current Windows workstation is chosen, its sleep and availability policy must be acceptable for the preview.

### Cloudflare Tunnel + Access — candidate when clients must use a browser without a VPN client

Run the same app on an owner-controlled private host and use an outbound Cloudflare Tunnel, which avoids opening an inbound firewall port. Cloudflare Access checks requests before forwarding them. This path uses a public hostname protected by Access, so it is not network-private in the same sense as Tailscale Serve; the owner must accept Cloudflare as an identity-aware proxy and choose an OIDC provider or Cloudflare email one-time PIN login method. Before authorizing a subject, validate the signed `Cf-Access-Jwt-Assertion` against the expected issuer and application audience, or configure the tunnel to validate Access JWTs. Keep the origin reachable only through the tunnel so requests cannot bypass Access. [Private web application](https://developers.cloudflare.com/cloudflare-one/setup/secure-private-apps/private-web-app/) · [Cloudflare identity providers](https://developers.cloudflare.com/cloudflare-one/integrations/identity-providers/) · [One-time PIN login](https://developers.cloudflare.com/cloudflare-one/integrations/identity-providers/one-time-pin/) · [Validate Access JWTs](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/) · [Tunnel origin Access validation](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/origin-parameters/)

### Self-hosted WireGuard VPN + Next.js OIDC — alternative if the owner wants to operate the private network

Run the Next.js preview and Python gateway on one owner-controlled VM or always-on server. Admit client devices through WireGuard peers, bind the browser-facing reverse proxy to the VPN interface, and keep the Python API on loopback. For remote access, the host needs a reachable WireGuard UDP endpoint; the web app itself can remain unavailable on public HTTP/HTTPS ports. WireGuard configuration associates each peer's public key with permitted IP ranges. This authenticates a device peer, not a human application subject. **Inference:** add application-level OIDC for the subject-to-portfolio boundary rather than treating possession of a WireGuard peer key as user authorization. [WireGuard quick start](https://www.wireguard.com/quickstart/) · [WireGuard protocol paper](https://www.wireguard.com/papers/wireguard.pdf)

Auth.js supports generic OIDC providers configured with an issuer, client ID, and client secret, so the owner can select an existing OIDC identity provider independently from the VPN. Next.js recommends a reverse proxy for self-hosted deployments. The verified OIDC subject must still cross a versioned, fail-closed server boundary from Next.js to Python; do not pass an unverified subject header and authorize from it. [Auth.js custom OIDC provider](https://authjs.dev/guides/configuring-oauth-providers) · [Next.js self-hosting](https://nextjs.org/docs/app/guides/self-hosting)

WireGuard protects traffic between peers, but does not provide a browser HTTPS certificate. **Inference:** serve the application over HTTPS on a privately resolved name under a publicly owned FQDN, with split-horizon DNS mapping it to the VPN address. A publicly trusted certificate can be issued with ACME DNS-01 while the web app stays private; HTTP-01 would require public port 80. A private-only suffix needs a private CA, whose root certificate must be trusted on each client. Avoid placing broad DNS API credentials on the web host; use narrowly scoped credentials or perform DNS validation separately. Next.js recommends `Secure` session cookies for HTTPS, so the certificate plan is part of the application boundary. This adds certificate/client trust work alongside WireGuard peer enrollment and key revocation, firewall rules, host patching, OIDC sessions, and single-instance storage backup/restore. [WireGuard protocol paper](https://www.wireguard.com/papers/wireguard.pdf) · [Let's Encrypt challenge types](https://letsencrypt.org/docs/challenge-types/) · [Next.js authentication and cookies](https://nextjs.org/docs/app/guides/authentication) · [Next.js self-hosting](https://nextjs.org/docs/app/guides/self-hosting)

## Proposed storage and authorization boundary

**Inference from the existing local store and the selected scope:** keep one tenant on one active Python service instance with the existing durable store and writer lock. Bind each allowed subject to an explicit server-side allowlist of portfolio IDs. The browser must not choose its own tenant or rely on hidden links for authorization. Keep the current accounting and recovery code authoritative; add a versioned authenticated service boundary instead of widening the existing unauthenticated loopback endpoint. Define the identity propagation and verification path from ingress through Next.js to Python, including protection against unverified or forged principal values. Review this proposal against the chosen host before implementation.

## Owner decisions still required

1. Whether to use Tailscale Serve with tailnet-only clients, Cloudflare Tunnel + Access for browser access without a VPN client, or a self-operated WireGuard VPN with the web app reachable only inside that VPN.
2. The concrete always-on host and either the OIDC identity provider or login method configured for the chosen path.
3. If WireGuard is chosen, the peer enrollment/revocation policy, firewall scope, and either a public FQDN with split-horizon DNS/ACME DNS-01 or a private suffix with a client-trusted private CA.
4. Whether the tenant permits one owner subject or an explicit allowlist of multiple subjects.
5. Approval of the proposed one-tenant, one-active-Python-instance storage boundary and explicit portfolio allowlist.
6. The versioned identity propagation and verification path from ingress through Next.js to Python.
7. Session expiry, revocation, clock tolerance, and denied-request audit policy.
8. Rate limits, request-size limits, timeouts, and abuse responses.
9. Log retention, alerting, backup/restore, rollback, and operator access review.

No credentials, services, application code, or deployment configuration were changed for this research.
