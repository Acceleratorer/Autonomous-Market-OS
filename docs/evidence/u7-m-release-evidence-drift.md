# U7-M Release Evidence Drift Audit

- Status: **CI-VERIFIED**
- Scope: same-run Windows/Linux CI evidence provenance and shared-boundary checks
- Implementation: `apps/desktop/electron/scripts/audit-release-drift.cjs`
- Focused test: `apps/desktop/electron/tests/release-drift.test.cjs`
- Focused result: **4 passed, 0 failed**
- Hosted run: [CI #43056896652](https://github.com/Acceleratorer/Autonomous-Market-OS/actions/runs/43056896652), job `u7-release-catalog`
- Hosted result: **passed**, drift count **0**, shared versions `0.1.0-ci.157.1` and `0.1.0-ci.157.2`

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

The hosted JSON and Markdown reports are retained in the existing
`market-os-u7-release-catalog` artifact. No VM, provider, credential, mutation,
or live execution path is enabled.
