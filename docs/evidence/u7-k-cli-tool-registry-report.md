# U7-K CLI Tool Registry Audit

- Status: **PASSED**
- Fixture fingerprint: `0089359ef3785ef44a80d68bc9c8b39b3efafed1c7cb33f58f29e092ef67bb18`
- Tools: **3** (2 enabled, 1 deferred)
- Promotion approved: **False**

## Registry

| Tool | Status | Capabilities | Execution enabled |
| --- | --- | --- | --- |
| market-os-btc-catalog | enabled | inspect, report | False |
| market-os-synthetic-economic-report | enabled | read_artifact, report | False |
| browser | deferred | inspect, mutate, network | False |

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
| generated_cli_execution | False |

synthetic tool registry audit only; no tool execution or live capability claim
