# U7-P Evidence Reproducibility Audit

- Status: **PASSED**
- Reproducibility fingerprint: `146c332a386d83ece76a02d717aea658d09d687b0f336f41ced1706efb3d5d2d`
- Committed U7-O catalog: `5c484710bc7007f90406352b660e5dbe4492c7662d6cdf9875a278c77649655e`

## Regenerated catalogs

- Run 1: `5c484710bc7007f90406352b660e5dbe4492c7662d6cdf9875a278c77649655e`
- Run 2: `5c484710bc7007f90406352b660e5dbe4492c7662d6cdf9875a278c77649655e`

## Audit checks

| Check | Result |
| --- | --- |
| sources_hashes_present | PASS |
| regenerated_catalogs_valid | PASS |
| catalog_fingerprint_match | PASS |
| deterministic_runs | PASS |
| catalog_body_match | PASS |
| boundaries_consistent | PASS |
| private_read_only_paper_only | PASS |
| no_provider_network_credentials | PASS |
| no_mutation_or_live_execution | PASS |

## Source artifacts

| Source | Artifact | SHA-256 |
| --- | --- | --- |
| catalog | `u7-o-evidence-catalog.json` | `1ef7f9ae43d1cf573c90849abdd43a4797146df322deb52812d0f73769dfb706` |
| pack | `u7-i-local-evidence-pack.json` | `0f8c12c476990a27b76c219286d1358300b11cc0df09dbfa035b992fc7e11b5e` |
| drift | `u7-m-release-evidence-drift.json` | `849e33c9fbeb9a8fc800a7eb16f2cda0887b2cdcc09487a61119d7ef6b2772d0` |
| economic_fixture | `u7_j_synthetic_economic.json` | `318580d84f753e0cf60d1cc16c8f585c2ccedf945f12a1845e6293cd79bd66b8` |
| tools_fixture | `u7_k_cli_anything_registry.json` | `40a923ec15c2981f6b127da01d1093848893056ee1110c73bb07a0a0d1a09441` |
| research_fixture | `u7_l_cited_research.json` | `5819f93bd962546e5ff63f7867febe63d2388ec00109a8680c8b2f8b044467c0` |

## Mismatches

- None

U7-N/J/K/L evidence regenerates deterministically into the committed U7-O catalog without network, provider, mutation, or live-execution access.
