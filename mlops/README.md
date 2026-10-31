# MLOps boundary

Market OS keeps MLOps offline, reproducible, and explicitly non-promoted.
Existing B1/B2/B3 artifacts already carry dataset revisions, feature/label or
fixture fingerprints, replay fingerprints, metrics, calibration, lineage, and
the `not-promoted` decision. This directory adds the small validation seam
around those artifacts; it does not move accounting or execution into an ML
system.

## Local tracking profile

The optional Compose `mlops` profile starts MLflow on host loopback only:

```bash
docker compose --profile mlops up mlflow
```

It is a tracking UI/store, not a model-serving endpoint. Do not publish it,
put credentials in the repository, or interpret a run as trading approval.

## Manifest validation

Validate a run manifest before attaching it to a release/evidence record:

```bash
python mlops/validate_manifest.py mlops/experiment-manifest.example.json
```

Required properties include deterministic code/data fingerprints, zero provider
requests for offline runs, explicit metrics, and `promotion_decision` equal to
`not-promoted`. A future connected or promoted ML workflow requires a new
contract, review, and separate approval.
