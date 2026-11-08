# U7-I Local Evidence Pack

`market_os.evidence_pack` builds the versioned
`market-os.u7-i-local-evidence-pack@v1` index from the stable U7-F, U7-G, and
U7-H evidence products. It rechecks exact schemas and statuses, required
checks, source hashes, reviewer fingerprints, and the shared private,
synthetic, paper-only, read-only boundary.

The pack is an evidence index. It does not add domain logic, runtime behavior,
deployment, profitability, or live-readiness authority.

```text
python -m market_os.evidence_pack \
  --release docs/evidence/u7-f-cross-target-release-catalog-report.json \
  --quality docs/evidence/u7-g-quality-benchmark-report.json \
  --session docs/evidence/u7-h-synthetic-session-accounting-report.json \
  --markdown <local-evidence-pack.md> \
  --json <local-evidence-pack.json>
```

CI uploads the stable JSON and Markdown outputs. Providers, credentials,
network access, mutation routes, live execution, mobile, and U5.5 owner-VM
promotion remain deferred.
