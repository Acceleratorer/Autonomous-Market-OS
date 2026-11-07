# U7-G Deterministic Quality Benchmark Report

**Status:** Implemented locally; CI report upload is required for closeout.

## Contract

`market-os benchmark report` runs the existing synthetic
`market-os.quality-benchmark.v2` fixture and emits the versioned
`market-os.u7-g-quality-benchmark-report@v1` reviewer projection as JSON and
Markdown. The command writes only the existing content-addressed benchmark
artifact store plus the requested report files; it does not touch trading
state or add an HTTP route.

The stable projection includes:

- fixture ID and SHA-256 lineage;
- benchmark and report fingerprints;
- case/evaluation counts;
- replay stability and gate-correctness outcomes;
- threshold metrics and decisions with machine-specific latency removed;
- read-only, no-provider, no-live-order safety checks; and
- the existing `Not ready` promotion status with unavailable deterministic
  test-double cost.

The report rejects schema/version mismatches, fingerprint tampering, unstable
replay, incomplete lineage, unsafe safety flags, benchmark procedure failures,
false accepts/rejects, provider execution, and any attempt to treat the
deterministic test double as real-model evidence.

## CLI

```text
market-os benchmark report \
  --store-root <local-report-store> \
  --fixture market_os/tests/fixtures/quality/benchmark.json \
  --markdown <quality-benchmark-report.md> \
  --json <quality-benchmark-report.json>
```

CI uploads both report formats and the content-addressed benchmark artifact.
Real providers, credentials, network calls, mutation routes, live execution,
mobile, and U5.5 owner-VM promotion remain deferred.
