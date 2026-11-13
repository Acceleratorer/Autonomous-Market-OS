# U8-A Live-Readiness Decision Pack

- Status: **GATED**
- Decision fingerprint: `5362b05d58144e55053aab994f22cb2ff6f3b628bff8f2a894241061134db999`
- Classification: `local_preflight_passed_connected_runtime_not_verified`

## Evidence items

| Milestone | Schema | Status | Source SHA-256 |
| --- | --- | --- | --- |
| local-exit | `market-os.local-exit-gate@v1` | green-local-boundary | `396bd566b49e1f91c40479b3d0946096be625f24a3667290bc842c8bad1da7f6` |
| U5.5 | `market-os.u5-5.stack-runtime-review-evidence@v1` | locally-verified-not-enabled | `b77bce0b193bdd5c5850d2cdfb168b58fa17e20ad19fd1fcd10e778e1179332f` |
| U5.5 | `market-os.u5-5.promotion-evidence@v1` | locally-verified-not-enabled | `585d0a955bb1fb8f1a9da214231e406d29ff5c6b92a10b28732219a55d3161c1` |
| U5.5 | `market-os.u5-5.connected-browser-smoke@v1` | passed | `2ba41f5fe3bd00abe2a395bd93cade6a236d97d63cd34e000b6e975a8b55b0d5` |
| U6.4-C | `market-os.u6.4-release-hardening@v1` | ci-verified-with-release-reports | `07cf8a96a68b65fa1146b3b20216cdee0daa1988a7069afda883674b3215fcd7` |
| U7-O | `market-os.u7-o-evidence-catalog@v1` | passed | `1ef7f9ae43d1cf573c90849abdd43a4797146df322deb52812d0f73769dfb706` |

## Local checks

| Check | Result |
| --- | --- |
| local_exit_gate_green | PASS |
| u7_catalog_passed | PASS |
| u5_5_contract_defined | PASS |
| identity_and_authorization_contract | PASS |
| storage_isolation_contract | PASS |
| session_replay_revocation_contract | PASS |
| audit_redaction_contract | PASS |
| server_only_secrets_contract | PASS |
| abuse_limits_contract | PASS |
| connected_browser_smoke_passed | PASS |
| local_promotion_rollback_simulation | PASS |
| u6_4_signed_smoke_and_rollback | PASS |
| paper_boundary_consistent | PASS |

## External gates

| Gate | Status | Reason |
| --- | --- | --- |
| owner_vm_access | blocked | owner VM/access is not available |
| owner_vm_health | blocked | owner VM health probe has not run |
| owner_tailscale | blocked | owner-only Tailscale Serve probe has not run |
| owner_vm_promotion_and_rollback | blocked | connected promotion and rollback remain pending |
| production_observability | blocked | production retention, alerting, and operator review are not verified |
| credentials_provider_approval | blocked | credentials and provider approval remain disabled |
| live_execution_authorization | blocked | live execution is disabled and separately gated |

## Boundary

| Boundary | Value |
| --- | --- |
| private | True |
| synthetic_only | True |
| paper_only | True |
| read_only | True |
| network_access | False |
| provider_requests | 0 |
| credentials | False |
| mutation_routes | False |
| live_execution | False |

## Decision

- Paper-only default: **True**
- Execution boundary change: **False**
- Owner decision required: **True**

## Deferred gates

- connected promotion and rollback
- credentials and provider approval
- embedded Python runtime/native installer
- live execution authorization
- mobile
- mutation routes
- owner VM/access
- owner-only Tailscale Serve verification
- production observability retention and alerting

Local U8-A preflight passes the existing paper-only contracts but does not verify or enable a connected runtime or live execution boundary.
