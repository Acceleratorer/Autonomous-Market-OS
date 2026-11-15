# U7-P Evidence Reproducibility Audit

U7-P is a local, deterministic audit for the committed U7-O catalog. It
regenerates U7-N from the U7-I pack and hosted U7-M drift evidence, regenerates
U7-J/K/L from their synthetic fixtures, builds the U7-O catalog twice, and
compares both runs with the committed catalog.

## Command

```text
python -m market_os.cli u7 evidence-repro \
  --catalog docs/evidence/u7-o-evidence-catalog.json \
  --pack docs/evidence/u7-i-local-evidence-pack.json \
  --drift docs/evidence/u7-m-release-evidence-drift.json \
  --economic market_os/tests/fixtures/economic/u7_j_synthetic_economic.json \
  --tools market_os/tests/fixtures/tools/u7_k_cli_anything_registry.json \
  --research market_os/tests/fixtures/research/u7_l_cited_research.json \
  --markdown output/u7-p/evidence-reproducibility.md \
  --json output/u7-p/evidence-reproducibility.json
```

The command writes only the requested output files. Intermediate reports are
created in a temporary directory and removed after each run. Source hashes
normalize line endings so Windows and Linux produce the same result.

## Contract

The `market-os.u7-p-evidence-reproducibility@v1` report requires:

- two regenerated U7-O catalogs with identical fingerprints;
- both regenerated fingerprints matching committed U7-O;
- matching catalog bodies and complete source hashes;
- the private, synthetic, paper-only, read-only, no-network boundary;
- provider, credential, mutation, promotion, and live-execution paths disabled.

Any mismatch produces `status: "failed"`, records a stable mismatch code, and
returns a non-zero CLI exit without changing the source artifacts.

## Evidence

The committed result is
[`u7-p-evidence-reproducibility.json`](evidence/u7-p-evidence-reproducibility.json)
and its human-readable companion
[`u7-p-evidence-reproducibility.md`](evidence/u7-p-evidence-reproducibility.md).
The current audit passed two identical runs with catalog fingerprint
`5c484710bc7007f90406352b660e5dbe4492c7662d6cdf9875a278c77649655e`.

U5.5 owner-VM promotion, providers, credentials, generated-tool execution,
Paper2Slides model/media execution, mutation routes, and live execution remain
deferred.
