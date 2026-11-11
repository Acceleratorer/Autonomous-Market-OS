# U7-O Evidence Catalog

U7-O closes the local U7 evidence surface by cataloging the committed U7-N
register with the U7-J economic report, U7-K CLI registry audit, and U7-L
Paper2Slides-ready research brief evidence. It is a deterministic, fail-closed
read-only catalog; it does not execute generated tools, call providers, or
claim deployment or live readiness.

## Command

```text
python -m market_os.u7_evidence_catalog \
  --register docs/evidence/u7-n-unified-evidence-register.json \
  --economic docs/evidence/u7-j-synthetic-economic-report.json \
  --tools docs/evidence/u7-k-cli-tool-registry-report.json \
  --research docs/evidence/u7-l-research-brief-evidence.json \
  --markdown output/u7-o/evidence-catalog.md \
  --json output/u7-o/evidence-catalog.json
```

The `market-os.u7-o-evidence-catalog@v1` output checks exact schemas and
statuses, source and report fingerprints, lineage, the shared private /
synthetic / paper-only / read-only / no-network boundary, and disabled
promotion or execution flags. Source hashes normalize line endings so the
catalog is reproducible on Windows and Linux.

## Evidence

The committed inputs are:

- `docs/evidence/u7-n-unified-evidence-register.json`
- `docs/evidence/u7-j-synthetic-economic-report.json`
- `docs/evidence/u7-k-cli-tool-registry-report.json`
- `docs/evidence/u7-l-research-brief-evidence.json`

CI renders and uploads `market-os-u7-o-evidence-catalog` after the hosted U7-N,
U7-J, U7-K, and U7-L steps. U5.5 owner-VM promotion, credentials, providers,
generated CLI execution, Paper2Slides model/media execution, mutation routes,
and live execution remain deferred.
