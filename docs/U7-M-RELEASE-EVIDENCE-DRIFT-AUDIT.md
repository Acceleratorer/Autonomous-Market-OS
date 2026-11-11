# U7-M: Release Evidence Drift Audit

**Status:** hosted CI verified on commit `7d33e08`

## Purpose

U7-M audits one Windows/Linux CI release evidence snapshot end to end:

```text
U6.4-C ci-evidence.json
  -> U7-A ci-evidence-validation.json
  -> U7-B release-evidence-report.json
  -> U7-D portable-archive-index.json
  -> U7-E cross-target-release-catalog.json
  -> U7-M drift report
```

The audit catches missing, stale, or contradictory evidence without treating
expected Windows/Linux artifact hash differences as a failure. It remains an
offline report over CI files. It does not contact a VM, provider, credential
store, network service, or live execution path.

## Contract

The command is:

```text
cd apps/desktop/electron
pnpm run release:drift -- \
  --windows <windows-evidence-dir> \
  --linux <linux-evidence-dir> \
  --catalog <cross-target-release-catalog.json> \
  --markdown <release-evidence-drift.md> \
  --json <release-evidence-drift.json>
```

The JSON output uses schema
`market-os.u7-m-release-evidence-drift@v1` and contains:

- `status`: `passed` or `failed`;
- `checks`: deterministic booleans for bundle presence, shared versions,
  manifest provenance, signatures, smoke routes, promotion/rollback metadata,
  archive-index checks, and boundary consistency;
- `target_summaries`: the normalized Windows/Linux evidence chain;
- `expected_target_variance`: target-specific manifest and archive hashes,
  which are recorded rather than compared for equality;
- `drift` and `drift_count`: sorted, structured failures with a code, path,
  target or target pair, observed value, and expected value;
- `boundary`: the shared private, synthetic, paper-only, read-only,
  execution-disabled boundary.

## Required checks

For each target, U7-M requires passed schemas and statuses for U6.4-C, U7-A,
U7-B, U7-D, and the release drill. It verifies:

1. known-good and candidate roles have distinct versions;
2. U7-A manifest hashes match U7-B, U7-D, and each signed smoke report;
3. signatures are verified and archive-index checks are true;
4. `/readyz`, `/healthz`, `/overview`, and `/runtime` returned HTTP 200 and
   both local ports closed after smoke;
5. failed-launch restoration, candidate promotion, known-good preservation,
   rollback availability, rollback success, and storage isolation are true;
6. raw and derived boundary values match the safe contract.

Across targets it requires shared known-good/candidate versions, identical
safe boundaries, valid target identity, and a valid U7-E catalog. Windows and
Linux component/archive/manifest hashes may differ because they are target
artifacts; each value must remain internally consistent with its own evidence
chain.

Any missing input, schema mismatch, unsafe boundary, hash mismatch, failed
smoke route, inconsistent promotion metadata, or invalid catalog produces a
failed report and a non-zero command exit status.

## Verification

Focused coverage lives in
`apps/desktop/electron/tests/release-drift.test.cjs` and covers:

- a passing two-target snapshot;
- boundary drift;
- raw-to-derived manifest drift;
- a failed signed smoke route.

CI runs U7-M in the existing `u7-release-catalog` job after U7-E/F and uploads
both Markdown and JSON drift reports beside the catalog evidence.

## Deferred boundaries

U5.5 owner-VM promotion, embedded Python/native installer, mobile, credentials,
provider access, mutation routes, and live execution remain deferred.
