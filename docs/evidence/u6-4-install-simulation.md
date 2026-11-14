# U6.4-E Offline Install Simulation

- Status: **PASSED**
- Target: `windows-x64`
- Version: `0.1.0-ci.1793993550152.2`
- Signature: **verified**
- Source manifest: `5b0a4cd3cf539656516e0c41157977b41dc5d02d52ca04d82e712512c66392d5`
- Destination manifest: `5b0a4cd3cf539656516e0c41157977b41dc5d02d52ca04d82e712512c66392d5`
- Artifact tree: `127bb9864fb39b3d197c803b2b048c57831e17ffb12a52222fc08fad614b18c7`

The simulation publishes a verified artifact through a separate staging directory and resets artifact-local mutable storage. It does not install a service, embed Python, or change release slots.

## Checks

| Check | Result |
| --- | --- |
| source_preflight | PASS |
| staged_preflight | PASS |
| destination_preflight | PASS |
| destination_separate | PASS |
| staged_tree_matches_source | PASS |
| destination_tree_matches_source | PASS |
| destination_manifest_matches_source | PASS |
| source_unchanged | PASS |
| mutable_storage_reset | PASS |
| staging_clean | PASS |
| boundary | PASS |

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

Deferred: embedded Python runtime, native service installation, credentials, providers, mutation routes, live execution, and U5.5 owner-VM promotion.
