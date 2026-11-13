# U8-A Live-Readiness Decision Pack

## Scope

U8-A is a local, fail-closed decision pack over the already verified U5.5,
U6.4-C, and U7-O evidence. It records whether the repository is ready to
change the execution boundary. It does not promote a VM, enable credentials,
or authorize live execution.

The output schema is `market-os.u8-a-live-readiness-decision@v1`.

## Decision

The current local result is:

- `status`: `gated`
- `classification`: `local_preflight_passed_connected_runtime_not_verified`
- `paper_only_default`: `true`
- `execution_boundary_change`: `false`
- `owner_decision_required`: `true`

The pack records two owner choices: keep paper-only mode permanently, or
continue live-readiness after the external gates are available. The second
choice remains blocked until the required evidence exists.

## Inputs

The renderer consumes these checked-in evidence records:

- `docs/evidence/local-exit-gate.json`
- `docs/evidence/u5-5-stack-runtime-review.json`
- `docs/evidence/u5-5-promotion-evidence.json`
- `docs/evidence/u5-5-connected-browser-smoke.json`
- `docs/evidence/u6-4-release-hardening.json`
- `docs/evidence/u7-o-evidence-catalog.json` (CI uses the hosted U7-O output)

Each input is checked for its exact schema and status. The renderer also
rechecks identity, storage isolation, session replay/revocation, audit and
redaction, server-only secrets, abuse limits, signed smoke, two-version
promotion/rollback, and the shared private/synthetic/paper-only/read-only
boundary.

## Blocked external gates

These gates are intentionally explicit and fail closed:

- owner VM access and health
- owner-only Tailscale Serve verification
- connected promotion and rollback
- production observability retention, alerting, and operator review
- credentials and provider approval
- live execution authorization

Mobile, mutation routes, and an embedded Python/native installer remain
separate deferred work.

## Reproducible command

```text
python -m market_os.u8a_readiness \
  --local-exit docs/evidence/local-exit-gate.json \
  --stack docs/evidence/u5-5-stack-runtime-review.json \
  --promotion docs/evidence/u5-5-promotion-evidence.json \
  --browser docs/evidence/u5-5-connected-browser-smoke.json \
  --release docs/evidence/u6-4-release-hardening.json \
  --u7 docs/evidence/u7-o-evidence-catalog.json \
  --markdown output/u8-a/live-readiness-decision.md \
  --json output/u8-a/live-readiness-decision.json
```

The generated JSON includes a deterministic `decision_fingerprint`; Markdown
is the reviewer-facing projection. CI uploads both as
`market-os-u8-a-live-readiness-decision`.

## Evidence

The current local output is in
`docs/evidence/u8-a-live-readiness-decision.json` and
`docs/evidence/u8-a-live-readiness-decision.md`. It is a readiness decision
record only; it does not change the private, read-only, paper-only, or
execution-disabled boundary.
