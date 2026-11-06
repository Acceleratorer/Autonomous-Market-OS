# U5.5 private operator runtime

This directory is the owner-approved Linux VM/systemd/Tailscale Serve
promotion package for the single-tenant read-only operator.

U5.5 is locally verified and remains disabled. The selected target is a
private Linux VM supervised by `systemd`, with owner-only Tailscale Serve
ingress. Owner-VM promotion and rollback are still pending.

The runtime contract is:

- Python gateway: `127.0.0.1:8787`, Python remains the accounting, risk,
  reservation, ledger, recovery, replay, audit, backup, and inspection
  authority.
- Next.js: `127.0.0.1:3000`, server-rendered GET/HEAD only.
- Browser ingress: Tailscale Serve only; Python is never served directly.
- Subject: `owner-only`, using the owner login configured in
  `MARKET_OS_TAILSCALE_OWNER_LOGIN`.
- Portfolio: `paper-main` only.
- Portfolio root: `/var/lib/autonomous-market-os/portfolios`.
- Session assertions: 15 minutes, 60-second clock tolerance, one-time hashed
  `jti` replay state, and local revocation support.
- Promotion: encrypted `age` backup before promotion, one `known-good` slot,
  health-gated restart, and explicit rollback.

The current operator UI includes the existing portfolio, BTC dataset, and
research inspection routes plus the read-only `/desk` workspace. `/desk`
provides bounded BTC chart context, a catalog-backed watchlist, portfolio
state, research lineage, and an explicit locked execution panel. It does not
create an order ticket mutation, stream quotes, call a provider, or derive
accounting values in Next.js.

## First installation

1. Install the selected release under `/opt/autonomous-market-os/releases/<version>`,
   create `/opt/autonomous-market-os/current`, and create the `market-os` user.
2. Create the exact portfolio root and session/log directories. The
   `paper-main` directory must be a real directory, not a symlink, junction, or
   bind alias. It must contain a recoverable named `paper-main` B4 portfolio.
3. Copy `operator.env.example` to
   `/etc/autonomous-market-os/operator.env`, replace the placeholders, and set
   mode `0600`. Do not commit the file.
4. Install the two `.service` files into `/etc/systemd/system/`, run
   `systemctl daemon-reload`, and enable both services.
5. Apply `tailnet-policy.hujson` in the owner-controlled tailnet after replacing
   the owner identity. Tag only the VM with `tag:market-os`.
6. Run `tailscale-serve.sh`. Verify the generated tailnet hostname is the same
   value configured in `MARKET_OS_TAILSCALE_HOSTNAME`.
7. Run `healthcheck.sh`, then run the local U5.5 matrix against the tailnet
   hostname. The direct Python port and direct Next.js operator routes must
   return denial; `/healthz` is a process-only health endpoint.
8. Verify `/desk` through the tailnet hostname with the owner identity. Confirm
   that the chart/watchlist/book panels show only validated local records and
   that the execution panel remains visibly locked.

## Promotion and rollback

`promote.sh` requires an `age` recipient file at
`/etc/autonomous-market-os/backup-recipient`. It encrypts `paper-main` before
changing `current`, updates the one `known-good` slot, restarts both services,
and restores the known-good release if health fails. `rollback.sh` explicitly
activates that slot and reruns the health check.

## Promotion evidence

Run the local simulation without starting services or contacting the owner VM:

```text
python deploy/u5-5/promotion_evidence.py --mode dry-run
python deploy/u5-5/promotion_evidence.py --validate
```

The harness validates the service, Serve, origin-denial, owner-subject,
`paper-main` storage, encrypted-backup, and rollback contracts, then emits
`docs/evidence/u5-5-promotion-evidence.json`. On the selected VM, set
`MARKET_OS_U55_OWNER_VM=1` and use `--mode owner-vm` only for read-only
`healthcheck.sh` and `tailscale serve status --json` checks.

No script deletes portfolio data, enables mutations, adds provider credentials,
starts Binance/live execution, or exposes a public listener.

## Evidence boundary

The repository can verify the connected authorization chain locally by
simulating Tailscale headers. Actual VM provisioning, Tailscale tailnet policy
application, service installation, and promotion require the owner's Linux VM
and Tailscale control-plane access; those are not claimed until run on that
host.
