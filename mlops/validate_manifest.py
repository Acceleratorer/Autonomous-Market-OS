"""Validate a bounded, offline, non-promoted Market OS experiment manifest."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


HEX64 = re.compile(r"^[0-9a-f]{64}$")
SCHEMA = "market-os.mlops.experiment-manifest@v1"


def validate(payload: object) -> None:
    if not isinstance(payload, dict):
        raise ValueError("manifest must be an object")
    required = {
        "schema", "experiment_id", "code_revision", "dataset_revision",
        "dataset_fingerprint", "feature_fingerprint", "replay_fingerprint",
        "metrics", "network_requests", "provider_requests", "artifact_lineage",
        "promotion_decision",
    }
    if set(payload) != required:
        raise ValueError("manifest fields do not match the v1 contract")
    if payload["schema"] != SCHEMA or payload["promotion_decision"] != "not-promoted":
        raise ValueError("manifest is not an offline, non-promoted run")
    for name in ("code_revision", "dataset_revision", "experiment_id"):
        if not isinstance(payload[name], str) or not payload[name].strip():
            raise ValueError(f"{name} must be a non-empty string")
    for name in ("dataset_fingerprint", "feature_fingerprint", "replay_fingerprint"):
        value = payload[name]
        if not isinstance(value, str) or (value != "replace-with-64-char-sha256" and not HEX64.fullmatch(value)):
            raise ValueError(f"{name} must be a SHA-256 fingerprint or an example placeholder")
    if payload["network_requests"] != 0 or payload["provider_requests"] != 0:
        raise ValueError("offline manifest must not record network/provider requests")
    if not isinstance(payload["metrics"], dict) or not isinstance(payload["artifact_lineage"], list):
        raise ValueError("metrics and artifact_lineage have invalid shapes")


def main(argv: list[str] | None = None) -> int:
    path = Path((argv or sys.argv[1:])[0])
    validate(json.loads(path.read_text(encoding="utf-8")))
    print(f"validated offline MLOps manifest: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
