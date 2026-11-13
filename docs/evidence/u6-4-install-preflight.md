# U6.4-D Installer Preflight

- Status: **PASSED**
- Target: `windows-x64`
- Version: `0.1.0-ci.1793993550152.2`
- Signature: **verified**
- Preflight fingerprint: `f8148b818aa0f2d7768c181bac7344a4597aefcb99eccb85846ea50c76ca2250`

The preflight validates an unpacked target-native artifact without installing a service, embedding Python, changing release slots, or changing the execution boundary.

## Checks

| Check | Result |
| --- | --- |
| manifest_schema | PASS |
| target_matches_host | PASS |
| signature_or_unsigned_state | PASS |
| electron_binary | PASS |
| python_sidecar | PASS |
| storage_isolation | PASS |
| slot_metadata | PASS |
| runtime_boundary | PASS |
| destination_separate | PASS |

## Boundary

| Field | Value |
| --- | --- |
| loopback_only | true |
| synthetic | true |
| paper_only | true |
| read_only | true |
| credentials | false |
| provider_requests | 0 |
| mutation_routes | false |
| live_trading | false |

## Installation actions

- performed: **false**
- embedded_python: **false**
- native_service: **false**
- destination: `not supplied`

Deferred: embedded Python runtime, native service installation, credentials, providers, mutation routes, and live execution.
