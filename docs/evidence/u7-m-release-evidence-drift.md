# U7-M Release Evidence Drift Audit

- Status: **local-verified**
- Scope: same-run Windows/Linux CI evidence provenance and shared-boundary checks
- Implementation: `apps/desktop/electron/scripts/audit-release-drift.cjs`
- Focused test: `apps/desktop/electron/tests/release-drift.test.cjs`
- Focused result: **4 passed, 0 failed**

## Covered cases

| Case | Result |
| --- | --- |
| Complete Windows/Linux snapshot | PASS |
| Boundary drift | FAIL CLOSED |
| Raw-to-derived manifest drift | FAIL CLOSED |
| Signed smoke route failure | FAIL CLOSED |

Target-specific manifest and archive hashes remain recorded as expected target
variance. The audit compares each target's provenance chain internally and
requires shared release versions, safe boundaries, signatures, four-route
smoke, promotion metadata, rollback metadata, and a passed U7-E catalog.

CI will produce the hosted U7-M JSON and Markdown reports in the existing
`market-os-u7-release-catalog` artifact. No VM, provider, credential, mutation,
or live execution path is enabled.
