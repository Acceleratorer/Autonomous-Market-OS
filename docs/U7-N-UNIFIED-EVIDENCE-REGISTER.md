# U7-N: Unified Evidence Register

**Status:** implemented locally; CI validation runs in `offline-tests`

## Purpose

U7-N joins the committed U7-I local evidence pack with the hosted-verified
U7-M release drift evidence. It creates one deterministic register for the
current safe U7 boundary without claiming deployment, profitability, or live
readiness.

The register consumes exactly two machine-readable inputs:

```text
docs/evidence/u7-i-local-evidence-pack.json
docs/evidence/u7-m-release-evidence-drift.json
```

Run it with:

```text
python -m market_os.u7_evidence_register \
  --pack docs/evidence/u7-i-local-evidence-pack.json \
  --drift docs/evidence/u7-m-release-evidence-drift.json \
  --markdown <unified-evidence-register.md> \
  --json <unified-evidence-register.json>
```

## Contract

The output schema is
`market-os.u7-n-unified-evidence-register@v1`. It records:

- exact U7-I/U7-M source schemas and statuses;
- newline-normalized source SHA-256 hashes and a deterministic register fingerprint;
- all required U7-I checks and all U7-M checks;
- zero U7-M drift and two shared target release versions;
- normalized shared private, synthetic, paper-only, read-only,
  no-network/no-credentials/no-mutation/live-execution-disabled boundary;
- combined deferred gates from both source evidence products.

The command fails closed on missing or malformed JSON, schema/status drift,
failed source checks, non-zero U7-M drift, invalid target versions, or a
boundary mismatch. CI renders and uploads the JSON/Markdown register in the
`market-os-u7-n-unified-evidence-register` artifact.

U5.5 owner-VM promotion, embedded Python/native installer, mobile, providers,
credentials, mutation routes, and live execution remain deferred.
