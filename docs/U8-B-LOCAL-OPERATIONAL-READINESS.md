# U8-B Local Operational Readiness

## Scope

U8-B joins the existing local observability, retention, platform, release,
and U8-A evidence into a deterministic operational-readiness pack. It checks
request correlation and redaction, loopback access, bounded metrics labels,
the private observability profile, read-only retention, backup/restore, and
signed release rollback.

The output schema is `market-os.u8-b-local-operational-readiness@v1`.
U8-B does not enable production retention, alert delivery, on-call ownership,
owner-VM failure drills, connected reconciliation, credentials, or live
execution.

## Decision

The current local result is:

- `status`: `gated`
- `classification`: `local_operational_controls_passed_production_operations_not_verified`
- `paper_only_default`: `true`
- `execution_boundary_change`: `false`
- `owner_decision_required`: `true`

Local controls pass. Production log retention and alerting, operator review,
owner-VM failure handling, connected reconciliation, and live authorization
remain blocked external gates.

## Inputs

- `docs/evidence/u5-3-deployment-access-observability.json`
- `docs/evidence/b4-20-retention-archive-preflight.json`
- `docs/evidence/platform-toolchain-readiness.json`
- `docs/evidence/u6-4-release-hardening.json`
- `docs/evidence/u8-a-live-readiness-decision.json`

Each source is checked for its exact schema/status and safety fields. U8-A is
required to remain gated with all external gates blocked and the canonical
private, synthetic, paper-only, read-only, no-network boundary unchanged.

## Reproducible command

```text
python -m market_os.u8b_operations \
  --observability docs/evidence/u5-3-deployment-access-observability.json \
  --retention docs/evidence/b4-20-retention-archive-preflight.json \
  --platform docs/evidence/platform-toolchain-readiness.json \
  --release docs/evidence/u6-4-release-hardening.json \
  --u8-a docs/evidence/u8-a-live-readiness-decision.json \
  --markdown output/u8-b/local-operational-readiness.md \
  --json output/u8-b/local-operational-readiness.json
```

CI renders and uploads both outputs as
`market-os-u8-b-local-operational-readiness` after U8-A.

## Evidence

The current local output is in
`docs/evidence/u8-b-local-operational-readiness.json` and
`docs/evidence/u8-b-local-operational-readiness.md`. It is an operational
decision record only and does not alter the private, read-only, paper-only, or
execution-disabled boundary.
