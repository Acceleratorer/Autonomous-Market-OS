"""Bounded read-only inspection for persisted B2 and B3 run summaries."""
from __future__ import annotations

import hashlib
import heapq
import json
import math
import os
from pathlib import Path
import re
from typing import Any

MAX_RUN_MANIFEST_BYTES = 256 * 1024
MAX_RESULT_ARTIFACT_BYTES = 256 * 1024
MAX_RUN_SAMPLE_COUNT = 100_000
_DATASET_REVISION = re.compile(r"^btc-history-[0-9a-f]{20}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")

_ENGINES = {
    "b2": {
        "run_pattern": re.compile(r"^btc-b2-[0-9a-f]{20}$"),
        "schema": "market-os.btc-b2-run.v1",
        "api_version": "market-os.btc-b2.v1",
        "artifacts": {"config", "features", "labels", "splits", "predictions", "metrics", "calibration", "lineage"},
        "result_kind": "metrics",
    },
    "b3": {
        "run_pattern": re.compile(r"^btc-b3-[0-9a-f]{20}$"),
        "schema": "market-os.u3-b3.jev-benchmark.v1",
        "api_version": "market-os.btc-b3.v1",
        "artifacts": {"config", "fixture_cases", "responses", "splits", "predictions", "metrics", "calibration", "control_baselines", "matched_controls", "report", "lineage"},
        "result_kind": "report",
    },
}


class ResearchInspectionError(ValueError):
    """A bounded research artifact could not be inspected safely."""


def _invalid_constant(value: str) -> None:
    raise ValueError(f"unsupported JSON number: {value}")


def _load_json(raw: bytes) -> Any:
    return json.loads(raw, parse_constant=_invalid_constant)


def _text(value: Any, *, limit: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value) > limit:
        raise ResearchInspectionError("BTC research artifact contains invalid display text")
    return value


def _count(value: Any, *, limit: int = MAX_RUN_SAMPLE_COUNT) -> int:
    if type(value) is not int or not 0 <= value <= limit:
        raise ResearchInspectionError("BTC research artifact contains an invalid count")
    return value


def _digest(value: Any) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise ResearchInspectionError("BTC research artifact contains an invalid fingerprint")
    return value


def _optional_metric(value: Any, *, bounded: bool = False) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ResearchInspectionError("BTC research metrics contain an invalid number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ResearchInspectionError("BTC research metrics contain an invalid number") from exc
    if not math.isfinite(result):
        raise ResearchInspectionError("BTC research metrics contain an invalid number")
    if result < 0 or (bounded and result > 1):
        raise ResearchInspectionError("BTC research metrics contain an out-of-range number")
    return result


def _optional_delta(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ResearchInspectionError("BTC research deltas contain an invalid number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ResearchInspectionError("BTC research deltas contain an invalid number") from exc
    if not math.isfinite(result):
        raise ResearchInspectionError("BTC research deltas contain an invalid number")
    return result


def _metric_score(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"status", "n", "log_loss", "brier", "accuracy"}:
        raise ResearchInspectionError("BTC research metrics have an invalid shape")
    status = value["status"]
    n = _count(value["n"])
    if status not in {"measured", "unavailable"} or (status == "measured") != (n > 0):
        raise ResearchInspectionError("BTC research metrics have an invalid status")
    return {
        "status": status,
        "n": n,
        "log_loss": _optional_metric(value["log_loss"]),
        "brier": _optional_metric(value["brier"], bounded=True),
        "accuracy": _optional_metric(value["accuracy"], bounded=True),
    }


class BtcResearchInspectionStore:
    """Read fixed B2/B3 run metadata without creating or mutating a store."""

    def __init__(self, root: str | Path, engine: str) -> None:
        if engine not in _ENGINES:
            raise ValueError("unsupported BTC research engine")
        self.root = Path(root)
        self.engine = engine
        self.spec = _ENGINES[engine]
        self.runs = self.root / "runs"

    def list_runs_page(self, *, limit: int = 25, after_run_id: str | None = None) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ResearchInspectionError("limit must be an integer between 1 and 100")
        if after_run_id is not None and self.spec["run_pattern"].fullmatch(after_run_id) is None:
            raise KeyError(after_run_id)
        roots = self._resolved_roots(missing_ok=True)
        if roots is None:
            if after_run_id is not None:
                raise KeyError(after_run_id)
            return self._empty_page(limit)
        root, runs = roots

        if after_run_id is not None:
            self._read_manifest(root, runs, after_run_id)

        try:
            with os.scandir(runs) as entries:
                candidates = heapq.nsmallest(
                    limit + 1,
                    (
                        entry.name
                        for entry in entries
                        if self.spec["run_pattern"].fullmatch(entry.name)
                        and (after_run_id is None or entry.name > after_run_id)
                        and entry.is_dir(follow_symlinks=False)
                    ),
                )
        except (OSError, RuntimeError) as exc:
            raise ResearchInspectionError("BTC research run catalog cannot be read") from exc

        has_more = len(candidates) > limit
        run_ids = candidates[:limit]
        summaries = [self._summary(self._read_manifest(root, runs, run_id)) for run_id in run_ids]
        next_run_id = summaries[-1]["run_id"] if has_more and summaries else None
        return {
            "engine": self.engine,
            "runs": summaries,
            "page": {
                "limit": limit,
                "after_run_id": after_run_id,
                "has_more": has_more,
                "next_after_run_id": next_run_id,
            },
        }

    def inspect_run(self, run_id: str) -> dict[str, Any]:
        if self.spec["run_pattern"].fullmatch(run_id) is None:
            raise KeyError(run_id)
        roots = self._resolved_roots(missing_ok=False)
        assert roots is not None
        root, runs = roots
        manifest = self._read_manifest(root, runs, run_id)
        summary = self._summary(manifest)
        artifact = next(item for item in manifest["artifacts"] if item["kind"] == self.spec["result_kind"])
        result = self._read_result(root, runs, run_id, artifact)
        if self.engine == "b2":
            result = self._validate_b2_metrics(result, summary["sample_count"])
        else:
            result = self._validate_b3_report(result, summary)
        return {"engine": self.engine, "run": summary, "result": result}

    def _empty_page(self, limit: int) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "runs": [],
            "page": {"limit": limit, "after_run_id": None, "has_more": False, "next_after_run_id": None},
        }

    def _resolved_roots(self, *, missing_ok: bool) -> tuple[Path, Path] | None:
        try:
            root = self.root.resolve(strict=True)
            if not root.is_dir():
                raise ResearchInspectionError("BTC research store must be a directory")
            runs = self.runs.resolve(strict=True)
            if not runs.is_dir() or not runs.is_relative_to(root):
                raise ResearchInspectionError("BTC research run storage is invalid")
            return root, runs
        except FileNotFoundError:
            if missing_ok:
                return None
            raise KeyError("BTC research run not found")
        except (OSError, RuntimeError) as exc:
            raise ResearchInspectionError("BTC research store cannot be resolved safely") from exc

    def _read_manifest(self, root: Path, runs: Path, run_id: str) -> dict[str, Any]:
        try:
            run_dir = (runs / run_id).resolve(strict=True)
            if not run_dir.is_dir() or not run_dir.is_relative_to(runs):
                raise KeyError(run_id)
            path = (run_dir / "manifest.json").resolve(strict=True)
            if not path.is_file() or not path.is_relative_to(run_dir):
                raise ResearchInspectionError("BTC research run manifest is outside its run directory")
            with path.open("rb") as source:
                raw = source.read(MAX_RUN_MANIFEST_BYTES + 1)
        except FileNotFoundError as exc:
            raise KeyError(run_id) from exc
        except KeyError:
            raise
        except (OSError, RuntimeError) as exc:
            raise ResearchInspectionError("BTC research run manifest cannot be read safely") from exc
        if len(raw) > MAX_RUN_MANIFEST_BYTES:
            raise ResearchInspectionError("BTC research run manifest exceeds the local inspection limit")
        try:
            manifest = _load_json(raw)
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
            raise ResearchInspectionError("BTC research run manifest is malformed") from exc
        if not isinstance(manifest, dict):
            raise ResearchInspectionError("BTC research run manifest has an invalid shape")
        self._validate_manifest(manifest, run_id)
        return manifest

    def _validate_manifest(self, manifest: dict[str, Any], run_id: str) -> None:
        if (
            manifest.get("schema") != self.spec["schema"]
            or manifest.get("api_version") != self.spec["api_version"]
            or manifest.get("run_id") != run_id
            or not isinstance(manifest.get("dataset_revision"), str)
            or _DATASET_REVISION.fullmatch(manifest["dataset_revision"]) is None
            or type(manifest.get("sample_count")) is not int
            or not 0 <= manifest["sample_count"] <= MAX_RUN_SAMPLE_COUNT
        ):
            raise ResearchInspectionError("BTC research run manifest does not match its catalog ID")
        if self.engine == "b2":
            _digest(manifest.get("feature_fingerprint"))
            _digest(manifest.get("label_fingerprint"))
            if manifest.get("baselines") != ["naive_0_5", "empirical_rate", "conditional_rate"]:
                raise ResearchInspectionError("B2 run manifest contains unsupported baselines")
        else:
            _text(manifest.get("experiment_version"), limit=128)
            for key in (
                "feature_fingerprint", "fixture_fingerprint", "request_fingerprint",
                "response_fingerprint", "split_fingerprint", "calibration_fingerprint",
            ):
                _digest(manifest.get(key))
            if manifest.get("promotion_decision") != "not-promoted":
                raise ResearchInspectionError("B3 run manifest has an unsupported promotion decision")
        _digest(manifest.get("replay_fingerprint"))

        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, list) or len(artifacts) != len(self.spec["artifacts"]):
            raise ResearchInspectionError("BTC research artifact list is invalid")
        kinds: set[str] = set()
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                raise ResearchInspectionError("BTC research artifact metadata is invalid")
            kind = artifact.get("kind")
            if not isinstance(kind, str) or kind not in self.spec["artifacts"] or kind in kinds:
                raise ResearchInspectionError("BTC research artifact kind is invalid")
            kinds.add(kind)
            expected_path = f"runs/{run_id}/{kind}.json"
            if artifact.get("path") != expected_path:
                raise ResearchInspectionError("BTC research artifact path is invalid")
            _digest(artifact.get("sha256"))
            if type(artifact.get("size_bytes")) is not int or not 0 <= artifact["size_bytes"] <= 1_000_000_000:
                raise ResearchInspectionError("BTC research artifact size is invalid")
            lineage = artifact.get("lineage")
            if not isinstance(lineage, list) or len(lineage) > len(self.spec["artifacts"]) + 3 or any(
                not isinstance(value, str) or not value or len(value) > 128 for value in lineage
            ):
                raise ResearchInspectionError("BTC research artifact lineage is invalid")
        if kinds != self.spec["artifacts"]:
            raise ResearchInspectionError("BTC research artifact list is incomplete")

    def _summary(self, manifest: dict[str, Any]) -> dict[str, Any]:
        common = {
            "run_id": manifest["run_id"],
            "dataset_revision": manifest["dataset_revision"],
            "sample_count": manifest["sample_count"],
            "replay_fingerprint": manifest["replay_fingerprint"],
            "artifact_count": len(manifest["artifacts"]),
        }
        if self.engine == "b2":
            return {
                **common,
                "feature_fingerprint": manifest["feature_fingerprint"],
                "label_fingerprint": manifest["label_fingerprint"],
                "baselines": list(manifest["baselines"]),
            }
        return {
            **common,
            "experiment_version": manifest["experiment_version"],
            "feature_fingerprint": manifest["feature_fingerprint"],
            "fixture_fingerprint": manifest["fixture_fingerprint"],
            "request_fingerprint": manifest["request_fingerprint"],
            "response_fingerprint": manifest["response_fingerprint"],
            "promotion_decision": manifest["promotion_decision"],
        }

    def _read_result(self, root: Path, runs: Path, run_id: str, artifact: dict[str, Any]) -> Any:
        try:
            run_dir = (runs / run_id).resolve(strict=True)
            path = (root / artifact["path"]).resolve(strict=True)
            if not path.is_file() or not path.is_relative_to(run_dir):
                raise ResearchInspectionError("BTC research result is outside its run directory")
            with path.open("rb") as source:
                raw = source.read(MAX_RESULT_ARTIFACT_BYTES + 1)
        except (OSError, RuntimeError) as exc:
            raise ResearchInspectionError("BTC research result cannot be read safely") from exc
        if len(raw) > MAX_RESULT_ARTIFACT_BYTES:
            raise ResearchInspectionError("BTC research result exceeds the local inspection limit")
        if len(raw) != artifact["size_bytes"] or hashlib.sha256(raw).hexdigest() != artifact["sha256"]:
            raise ResearchInspectionError("BTC research result failed its integrity check")
        try:
            return _load_json(raw)
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
            raise ResearchInspectionError("BTC research result is malformed") from exc

    def _validate_b2_metrics(self, value: Any, sample_count: int) -> dict[str, Any]:
        expected = {"naive_0_5", "empirical_rate", "conditional_rate"}
        if not isinstance(value, dict) or set(value) != expected:
            raise ResearchInspectionError("B2 metrics contain an invalid shape")
        result = {}
        for model in sorted(expected):
            arms = value[model]
            if not isinstance(arms, dict) or set(arms) != {"raw", "calibrated"}:
                raise ResearchInspectionError("B2 baseline metrics contain an invalid shape")
            result[model] = {name: _metric_score(arms[name]) for name in ("raw", "calibrated")}
            if any(score["n"] != sample_count for score in result[model].values()):
                raise ResearchInspectionError("B2 metric sample count does not match its run manifest")
        return result

    def _validate_b3_report(self, value: Any, summary: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict) or value.get("schema") != "market-os.u3-b3.report.v1":
            raise ResearchInspectionError("B3 report has an invalid schema")
        experiment = value.get("experiment")
        if not isinstance(experiment, dict) or not isinstance(experiment.get("answer_schema"), dict):
            raise ResearchInspectionError("B3 report experiment metadata is invalid")
        if _text(experiment.get("version"), limit=128) != summary["experiment_version"]:
            raise ResearchInspectionError("B3 report experiment version does not match its run manifest")
        answer_schema = experiment["answer_schema"]
        options = answer_schema.get("options")
        returns = answer_schema.get("returns")
        if (
            answer_schema.get("type") != "choice"
            or not isinstance(options, list)
            or len(options) > 8
            or any(not isinstance(item, str) or len(item) > 64 for item in options)
            or not isinstance(returns, list)
            or len(returns) > 8
            or any(not isinstance(item, str) or len(item) > 64 for item in returns)
        ):
            raise ResearchInspectionError("B3 report answer schema is invalid")
        source = value.get("source_boundary")
        if not isinstance(source, dict):
            raise ResearchInspectionError("B3 report source boundary is invalid")
        source_boundary = {
            "dataset_revision": _text(source.get("dataset_revision"), limit=64),
            "feature_fingerprint": _digest(source.get("feature_fingerprint")),
            "fixture_id": _text(source.get("fixture_id"), limit=128),
            "fixture_fingerprint": _digest(source.get("fixture_fingerprint")),
            "network_requests": _count(source.get("network_requests"), limit=300),
            "provider_requests": _count(source.get("provider_requests"), limit=300),
        }
        if (
            source_boundary["dataset_revision"] != summary["dataset_revision"]
            or source_boundary["feature_fingerprint"] != summary["feature_fingerprint"]
            or source_boundary["fixture_fingerprint"] != summary["fixture_fingerprint"]
            or source_boundary["network_requests"] != 0
            or source_boundary["provider_requests"] != 0
        ):
            raise ResearchInspectionError("B3 report lineage does not match its run manifest")
        coverage = value.get("coverage")
        if not isinstance(coverage, dict) or set(coverage) != {"E1_numerical_only", "E2_numerical_plus_jev"}:
            raise ResearchInspectionError("B3 report coverage is invalid")
        safe_coverage = {name: self._validate_coverage(item) for name, item in coverage.items()}
        failures = self._count_map(value.get("failure_counts"))
        fixture_kinds = self._count_map(value.get("fixture_case_kinds"))
        latency = value.get("latency_usage_cost")
        if not isinstance(latency, dict) or set(latency) != {"latency", "usage", "cost"} or any(
            latency.get(key) != "unknown-not-observed-offline" for key in ("latency", "usage", "cost")
        ):
            raise ResearchInspectionError("B3 report offline usage metadata is invalid")
        matched = value.get("matched_controls")
        if not isinstance(matched, dict) or matched.get("same_inputs") is not True:
            raise ResearchInspectionError("B3 report matched-control summary is invalid")
        uncertainty = matched.get("uncertainty")
        if not isinstance(uncertainty, dict):
            raise ResearchInspectionError("B3 report uncertainty summary is invalid")
        deltas = matched.get("deltas_candidate_minus_control")
        if not isinstance(deltas, dict) or set(deltas) - {"log_loss", "brier", "accuracy"}:
            raise ResearchInspectionError("B3 report deltas are invalid")
        safe_deltas = {key: _optional_delta(item) for key, item in deltas.items()}
        promotion = value.get("promotion")
        if not isinstance(promotion, dict) or promotion.get("decision") != "not-promoted":
            raise ResearchInspectionError("B3 report promotion boundary is invalid")
        next_evidence = promotion.get("required_next_evidence")
        if not isinstance(next_evidence, list) or len(next_evidence) > 16:
            raise ResearchInspectionError("B3 report next-evidence list is invalid")
        safe_promotion = {
            "decision": "not-promoted",
            "reason": _text(promotion.get("reason"), limit=1024),
            "matched_control_status": _text(promotion.get("matched_control_status"), limit=64),
            "required_next_evidence": [_text(item, limit=256) for item in next_evidence],
        }
        safe_matched = {
            "status": _text(matched.get("status"), limit=64),
            "n": _count(matched.get("n")),
            "same_inputs": True,
            "control": _text(matched.get("control"), limit=64),
            "candidate": _text(matched.get("candidate"), limit=64),
            "control_metrics": _metric_score(matched.get("control_metrics")),
            "candidate_metrics": _metric_score(matched.get("candidate_metrics")),
            "deltas_candidate_minus_control": safe_deltas,
            "uncertainty": {
                "status": _text(uncertainty.get("status"), limit=64),
                "reason": _text(uncertainty.get("reason"), limit=512),
            },
        }
        if (
            safe_matched["status"] not in {"measured", "unavailable"}
            or (safe_matched["status"] == "measured") != (safe_matched["n"] > 0)
            or safe_matched["n"] > summary["sample_count"]
            or safe_matched["control"] != "E1_numerical_only"
            or safe_matched["candidate"] != "E2_numerical_plus_jev"
            or safe_matched["control_metrics"]["n"] != safe_matched["n"]
            or safe_matched["candidate_metrics"]["n"] != safe_matched["n"]
            or safe_promotion["matched_control_status"] != safe_matched["status"]
        ):
            raise ResearchInspectionError("B3 report matched-control metrics are inconsistent")
        if _text(value.get("status"), limit=64) != "implemented-and-verified-offline":
            raise ResearchInspectionError("B3 report status is unsupported")
        return {
            "schema": "market-os.u3-b3.report.v1",
            "status": "implemented-and-verified-offline",
            "experiment": {
                "version": _text(experiment.get("version"), limit=128),
                "question_id": _text(experiment.get("question_id"), limit=128),
                "decision_question": _text(experiment.get("decision_question"), limit=1024),
                "answer_schema": {"type": "choice", "options": list(options), "returns": list(returns)},
            },
            "source_boundary": source_boundary,
            "coverage": safe_coverage,
            "failure_counts": failures,
            "fixture_case_kinds": fixture_kinds,
            "latency_usage_cost": dict(latency),
            "matched_controls": safe_matched,
            "promotion": safe_promotion,
            "scientific_boundary": _text(value.get("scientific_boundary"), limit=512),
        }

    @staticmethod
    def _count_map(value: Any) -> dict[str, int]:
        if not isinstance(value, dict) or len(value) > 32:
            raise ResearchInspectionError("BTC research outcome counts are invalid")
        counts = {}
        for key, amount in value.items():
            if not isinstance(key, str) or re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", key) is None:
                raise ResearchInspectionError("BTC research outcome category is invalid")
            counts[key] = _count(amount)
        return dict(sorted(counts.items()))

    def _validate_coverage(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ResearchInspectionError("B3 report coverage entry is invalid")
        candidate_n = _count(value.get("candidate_n"))
        predicted_n = _count(value.get("predicted_n"))
        abstention_n = _count(value.get("abstention_n"))
        if predicted_n > candidate_n or abstention_n != candidate_n - predicted_n:
            raise ResearchInspectionError("B3 report coverage counts are inconsistent")
        status = value.get("status")
        if status not in {"measured", "unavailable"} or (status == "measured") != (candidate_n > 0):
            raise ResearchInspectionError("B3 report coverage status is invalid")
        outcomes = self._count_map(value.get("outcomes"))
        coverage = _optional_metric(value.get("coverage"), bounded=True)
        abstention_rate = _optional_metric(value.get("abstention_rate"), bounded=True)
        return {
            "status": status,
            "candidate_n": candidate_n,
            "predicted_n": predicted_n,
            "abstention_n": abstention_n,
            "coverage": coverage,
            "abstention_rate": abstention_rate,
            "outcomes": outcomes,
        }
