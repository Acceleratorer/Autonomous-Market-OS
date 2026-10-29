"""Deterministic, local-only persistence for B3.1 synthetic artifacts."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .synthetic_reporting import REPORT_SCHEMA, SyntheticStabilityReport
from .synthetic_evaluation import RUNNER_SCHEMA, SyntheticEvaluationReport

BUNDLE_SCHEMA = "market-os.b3-1.synthetic-artifact-bundle@v1"
BUNDLE_VERSION = "v1"
_ARTIFACT_IDS = ("evaluation_report", "stability_report")
_FORBIDDEN_TOKENS = ("http://", "https://", "binance", "openai", "typesafe", "provider", "credential")


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _plain(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _canonical(value: Any) -> str:
    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 fingerprint")
    return value


def _reject_external(value: Any, *, key_context: str = "") -> None:
    if isinstance(value, str):
        lowered = value.lower()
        if "://" in lowered or "\\" in lowered or (key_context and any(token in lowered for token in _FORBIDDEN_TOKENS)):
            raise ValueError("bundle contains a forbidden external identity")
    elif isinstance(value, dict):
        for key, child in value.items():
            _reject_external(child, key_context=str(key).lower())
    elif isinstance(value, (list, tuple)):
        for child in value:
            _reject_external(child, key_context=key_context)


def _artifact_projection(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result.pop("fingerprint", None)
    return result


def _validate_artifact(payload: Any, *, schema: str, name: str) -> str:
    if not isinstance(payload, dict) or payload.get("schema") != schema:
        raise ValueError(f"{name} schema mismatch")
    if schema == RUNNER_SCHEMA and payload.get("synthetic_only") is not True:
        raise ValueError(f"{name} is not synthetic-only")
    fingerprint = _digest(payload.get("fingerprint"), f"{name} fingerprint")
    projection = _artifact_projection(payload)
    if schema == RUNNER_SCHEMA:
        projection.pop("version", None)
        projection.pop("status", None)
        row_counts = projection.get("row_counts")
        if isinstance(row_counts, dict):
            row_counts = dict(row_counts)
            row_counts.pop("untouched", None)
            projection["row_counts"] = row_counts
    elif schema == REPORT_SCHEMA:
        projection.pop("schema", None)
    if _fingerprint(projection) != fingerprint:
        raise ValueError(f"{name} fingerprint mismatch")
    _reject_external(payload)
    return fingerprint


@dataclass(frozen=True)
class SyntheticArtifactBundle:
    """A validated raw bundle; no provider or real-dataset reconstruction path."""

    bundle: dict[str, Any]

    @property
    def fingerprint(self) -> str:
        return self.bundle["bundle_fingerprint"]

    def to_dict(self) -> dict[str, Any]:
        return _plain(self.bundle)


def create_synthetic_artifact_bundle(
    report: SyntheticEvaluationReport,
    stability: SyntheticStabilityReport,
) -> SyntheticArtifactBundle:
    report_payload = report.to_dict()
    stability_payload = stability.to_dict()
    report_fp = _validate_artifact(report_payload, schema=RUNNER_SCHEMA, name="evaluation report")
    stability_fp = _validate_artifact(stability_payload, schema=REPORT_SCHEMA, name="stability report")
    if stability_payload.get("source_fingerprint") != report_fp:
        raise ValueError("stability report source fingerprint does not match evaluation report")
    artifacts = {
        "evaluation_report": report_payload,
        "stability_report": stability_payload,
    }
    projection = {
        "schema": BUNDLE_SCHEMA,
        "version": BUNDLE_VERSION,
        "synthetic_only": True,
        "source_fingerprints": {"evaluation_report": report_fp, "stability_report": stability_fp},
        "artifacts": artifacts,
    }
    bundle = {**projection, "bundle_fingerprint": _fingerprint(projection)}
    _reject_external(bundle)
    return SyntheticArtifactBundle(bundle)


def _validate_bundle(payload: Any) -> SyntheticArtifactBundle:
    if not isinstance(payload, dict):
        raise ValueError("bundle must be a JSON object")
    if payload.get("schema") != BUNDLE_SCHEMA or payload.get("version") != BUNDLE_VERSION:
        raise ValueError("bundle schema or version mismatch")
    if payload.get("synthetic_only") is not True:
        raise ValueError("bundle is not synthetic-only")
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != set(_ARTIFACT_IDS):
        raise ValueError("bundle must contain exactly one evaluation and one stability artifact")
    if len(set(artifacts)) != len(artifacts):
        raise ValueError("duplicate artifact identity")
    projection = dict(payload)
    bundle_fp = projection.pop("bundle_fingerprint", None)
    _digest(bundle_fp, "bundle fingerprint")
    if _fingerprint(projection) != bundle_fp:
        raise ValueError("bundle fingerprint mismatch")
    report_fp = _validate_artifact(artifacts["evaluation_report"], schema=RUNNER_SCHEMA, name="evaluation report")
    stability_fp = _validate_artifact(artifacts["stability_report"], schema=REPORT_SCHEMA, name="stability report")
    source_fingerprints = payload.get("source_fingerprints")
    if source_fingerprints != {"evaluation_report": report_fp, "stability_report": stability_fp}:
        raise ValueError("bundle source fingerprints mismatch")
    if artifacts["stability_report"].get("source_fingerprint") != report_fp:
        raise ValueError("stability report source fingerprint does not match evaluation report")
    _reject_external(payload)
    return SyntheticArtifactBundle(_plain(payload))


def write_synthetic_artifact_bundle(bundle: SyntheticArtifactBundle, path: str | os.PathLike[str]) -> None:
    """Atomically write canonical UTF-8 JSON to a caller-supplied local path."""
    validated = _validate_bundle(bundle.to_dict())
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(validated.to_dict(), handle, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def load_synthetic_artifact_bundle(path: str | os.PathLike[str]) -> SyntheticArtifactBundle:
    """Load and validate a bundle; malformed or tampered content fails closed."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("unable to read synthetic artifact bundle") from exc
    return _validate_bundle(payload)


__all__ = [
    "BUNDLE_SCHEMA",
    "BUNDLE_VERSION",
    "SyntheticArtifactBundle",
    "create_synthetic_artifact_bundle",
    "write_synthetic_artifact_bundle",
    "load_synthetic_artifact_bundle",
]
