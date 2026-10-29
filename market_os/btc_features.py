"""Deterministic offline BTC feature, label, and numerical baseline research.

This module consumes only hash-checked canonical rows exposed by B1.  It has
no market-data, model-provider, broker, or execution transport.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .btc_history import HistoryStore

B2_API_VERSION = "market-os.btc-b2.v1"
B2_FEATURE_VERSION = "btc.b2.features.v1"
B2_TARGET_VERSION = "btc.b2.close-return-5m.v1"
B2_RUN_SCHEMA = "market-os.btc-b2-run.v1"
_MINUTE_MS = 60_000
_HORIZON_MS = 5 * _MINUTE_MS
_UTC = timezone.utc


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _parse_ms(value: int | str) -> int:
    if isinstance(value, bool):
        raise ValueError("timestamp must be an integer millisecond value or UTC timestamp")
    if isinstance(value, int):
        return value
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be timezone-aware UTC")
    return int(parsed.timestamp() * 1000)


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, _UTC).isoformat(timespec="milliseconds")


def _as_of_ms(value: str) -> int:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("as_of must be timezone-aware UTC")
    return int(parsed.timestamp() * 1000)


def _finite(value: Any, field: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        raise ValueError(f"{field} is invalid")
    return result


@dataclass(frozen=True)
class B2Config:
    experiment_id: str
    as_of: str | None = None
    max_staleness_seconds: int = 1800
    horizon_minutes: int = 5
    warmup_minutes: int = 5
    purge_minutes: int = 5
    embargo_minutes: int = 5
    train_fraction: float = 0.6
    calibration_fraction: float = 0.2
    test_fraction: float = 0.2
    feature_version: str = B2_FEATURE_VERSION
    target_version: str = B2_TARGET_VERSION
    execution_mode: str = "paper"
    api_version: str = B2_API_VERSION

    def __post_init__(self) -> None:
        if not self.experiment_id.strip():
            raise ValueError("experiment_id must not be empty")
        if self.as_of is not None:
            _as_of_ms(self.as_of)
        if self.max_staleness_seconds <= 0 or self.horizon_minutes != 5 or self.warmup_minutes != 5:
            raise ValueError("B2 requires a positive staleness limit, 5-minute horizon, and 5-minute warm-up")
        if self.purge_minutes != 5 or self.embargo_minutes != 5:
            raise ValueError("B2 purge and embargo are fixed at the 5-minute label horizon")
        if any(value <= 0 for value in (self.train_fraction, self.calibration_fraction, self.test_fraction)):
            raise ValueError("split fractions must be positive")
        if not math.isclose(self.train_fraction + self.calibration_fraction + self.test_fraction, 1.0):
            raise ValueError("split fractions must sum to one")
        if self.feature_version != B2_FEATURE_VERSION or self.target_version != B2_TARGET_VERSION:
            raise ValueError("unsupported B2 feature or target version")
        if self.execution_mode != "paper":
            raise ValueError("B2 is strictly paper-only")
        if self.api_version != B2_API_VERSION:
            raise ValueError("unsupported B2 API version")


def _normal_row(row: dict[str, Any]) -> dict[str, Any]:
    open_ms = _parse_ms(row["open_time_ms"])
    close_ms = _parse_ms(row["close_time_ms"])
    if close_ms - open_ms != _MINUTE_MS or open_ms % _MINUTE_MS:
        raise ValueError("candle is not an aligned one-minute row")
    values = {
        "open": _finite(row["open"], "open", minimum=0.0000000001),
        "high": _finite(row["high"], "high", minimum=0.0000000001),
        "low": _finite(row["low"], "low", minimum=0.0000000001),
        "close": _finite(row["close"], "close", minimum=0.0000000001),
        "volume": _finite(row["volume"], "volume", minimum=0),
    }
    if values["high"] < max(values["open"], values["close"], values["low"]):
        raise ValueError("high does not contain OHLC values")
    if values["low"] > min(values["open"], values["close"], values["high"]):
        raise ValueError("low does not contain OHLC values")
    availability_ms = _parse_ms(row["availability_timestamp"])
    source_ms = _parse_ms(row["source_timestamp"])
    received_ms = _parse_ms(row["received_at"])
    if source_ms < close_ms or received_ms < source_ms or availability_ms < received_ms:
        raise ValueError("candle timestamp lineage is not monotonic")
    return {
        "open_time_ms": open_ms,
        "close_time_ms": close_ms,
        **values,
        "source_timestamp": row["source_timestamp"],
        "received_at": row["received_at"],
        "availability_timestamp": row["availability_timestamp"],
        "canonical_fingerprint": str(row["canonical_fingerprint"]),
    }


def _ref(row: dict[str, Any], role: str) -> dict[str, Any]:
    return {
        "role": role,
        "open_time_ms": row["open_time_ms"],
        "close_time_ms": row["close_time_ms"],
        "source_timestamp": row["source_timestamp"],
        "received_at": row["received_at"],
        "availability_timestamp": row["availability_timestamp"],
        "canonical_fingerprint": row["canonical_fingerprint"],
    }


def _status_row(row: dict[str, Any], status: str, reason: str, *, decision_ms: int | None = None) -> dict[str, Any]:
    return {
        "feature_version": B2_FEATURE_VERSION,
        "close_time_ms": row.get("close_time_ms"),
        "close_time": _iso(row["close_time_ms"]) if row.get("close_time_ms") is not None else None,
        "source_timestamp": row.get("source_timestamp"),
        "received_at": row.get("received_at"),
        "availability_timestamp": row.get("availability_timestamp"),
        "decision_eligible_at": _iso(decision_ms) if decision_ms is not None else None,
        "decision_eligible": status == "eligible",
        "status": status,
        "reason": reason,
        "values": {},
        "input_refs": [],
    }


def _label_status(feature: dict[str, Any], status: str, reason: str, target: dict[str, Any] | None = None) -> dict[str, Any]:
    result = {
        "target_version": B2_TARGET_VERSION,
        "dataset_revision": feature.get("dataset_revision"),
        "feature_close_time_ms": feature["close_time_ms"],
        "target_end_ms": feature["close_time_ms"] + _HORIZON_MS,
        "target_end": _iso(feature["close_time_ms"] + _HORIZON_MS),
        "status": status,
        "reason": reason,
        "target_return": None,
        "direction": None,
        "feature_input_fingerprint": feature.get("input_fingerprint"),
        "target_fingerprint": None,
        "target_refs": [_ref(target, "future_target")] if target is not None else [],
    }
    if target is not None and status == "eligible":
        result["target_return"] = math.log(target["close"] / feature["values"]["close"])
        result["direction"] = "up" if result["target_return"] > 0 else "down" if result["target_return"] < 0 else "flat"
        result["target_fingerprint"] = _sha({
            "target_version": B2_TARGET_VERSION,
            "feature_input_fingerprint": feature["input_fingerprint"],
            "target": target,
        })
    return result


def materialize_rows(
    rows: list[dict[str, Any]],
    config: B2Config,
    *,
    dataset_revision: str | None = None,
) -> dict[str, Any]:
    """Materialize point-in-time features and separate future labels.

    Feature inputs are limited to the current row and exact one/five-minute
    historical rows. Labels are emitted separately and may reference only the
    exact future target row.
    """
    as_of_ms = _as_of_ms(config.as_of) if config.as_of is not None else None
    normalized: dict[int, dict[str, Any]] = {}
    invalid: dict[int, dict[str, Any]] = {}
    for raw in rows:
        try:
            item = _normal_row(raw)
            current = normalized.get(item["open_time_ms"])
            if current is None or item["canonical_fingerprint"] < current["canonical_fingerprint"]:
                normalized[item["open_time_ms"]] = item
        except (KeyError, TypeError, ValueError) as exc:
            try:
                open_ms = _parse_ms(raw["open_time_ms"])
            except (KeyError, TypeError, ValueError):
                continue
            invalid[open_ms] = {"open_time_ms": open_ms, "close_time_ms": open_ms + _MINUTE_MS, "canonical_fingerprint": str(raw.get("canonical_fingerprint", "invalid"))}
    ordered = [normalized[key] for key in sorted(normalized)]
    features: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    label_outcomes: list[dict[str, Any]] = []
    by_open = {item["open_time_ms"]: item for item in ordered}
    for row in ordered:
        close_ms = row["close_time_ms"]
        decision_ms = max(close_ms, _parse_ms(row["availability_timestamp"]))
        if as_of_ms is not None and decision_ms > as_of_ms:
            feature = _status_row(row, "unavailable", "decision eligibility is after materialization as_of", decision_ms=decision_ms)
            features.append(feature)
            continue
        if as_of_ms is not None and as_of_ms - _parse_ms(row["availability_timestamp"]) > config.max_staleness_seconds * 1000:
            features.append(_status_row(row, "stale", "availability exceeds max_staleness_seconds", decision_ms=decision_ms))
            continue
        previous = by_open.get(row["open_time_ms"] - _MINUTE_MS)
        five_back = by_open.get(row["open_time_ms"] - _HORIZON_MS)
        required = [by_open.get(row["open_time_ms"] - offset * _MINUTE_MS) for offset in range(1, 6)]
        if previous is None or five_back is None:
            features.append(_status_row(row, "warm_up", "five contiguous historical candles are required", decision_ms=decision_ms))
            continue
        if any(item is None for item in required):
            features.append(_status_row(row, "gap", "historical candle continuity is incomplete", decision_ms=decision_ms))
            continue
        unavailable = [item for item in required if _parse_ms(item["availability_timestamp"]) > decision_ms]
        if unavailable or (as_of_ms is not None and any(_parse_ms(item["availability_timestamp"]) > as_of_ms for item in required)):
            features.append(_status_row(row, "unavailable", "historical input was not available at decision eligibility", decision_ms=decision_ms))
            continue
        if as_of_ms is not None and any(as_of_ms - _parse_ms(item["availability_timestamp"]) > config.max_staleness_seconds * 1000 for item in required):
            features.append(_status_row(row, "stale", "historical input exceeds max_staleness_seconds", decision_ms=decision_ms))
            continue
        refs = [_ref(row, "current"), *[_ref(item, "lookback") for item in required[::-1]]]
        values = {
            "close": row["close"],
            "log_return_1m": math.log(row["close"] / previous["close"]),
            "log_return_5m": math.log(row["close"] / five_back["close"]),
            "range_pct": (row["high"] - row["low"]) / row["close"],
            "log_volume": math.log1p(row["volume"]),
        }
        feature = {
            "feature_version": B2_FEATURE_VERSION,
            "dataset_revision": dataset_revision,
            "close_time_ms": close_ms,
            "close_time": _iso(close_ms),
            "source_timestamp": row["source_timestamp"],
            "received_at": row["received_at"],
            "availability_timestamp": row["availability_timestamp"],
            "decision_eligible_at": _iso(decision_ms),
            "decision_eligible": True,
            "status": "eligible",
            "reason": None,
            "values": values,
            "input_refs": refs,
        }
        feature["input_fingerprint"] = _sha({"dataset_revision": dataset_revision, "feature": feature})
        features.append(feature)
        target = by_open.get(row["open_time_ms"] + _HORIZON_MS)
        if target is None:
            label_outcomes.append(_label_status(feature, "gap", "future five-minute target candle is missing"))
        elif target["open_time_ms"] != row["open_time_ms"] + _HORIZON_MS:
            label_outcomes.append(_label_status(feature, "gap", "future target is not exactly five minutes ahead"))
        elif any(by_open.get(row["open_time_ms"] + offset * _MINUTE_MS) is None for offset in range(1, 6)):
            label_outcomes.append(_label_status(feature, "gap", "future target path contains a missing candle", target))
        elif as_of_ms is not None and _parse_ms(target["availability_timestamp"]) > as_of_ms:
            label_outcomes.append(_label_status(feature, "unavailable", "future target was not available by materialization as_of", target))
        else:
            label_outcomes.append(_label_status(feature, "eligible", "future target is available", target))
            labels.append(label_outcomes[-1])
    for open_ms, item in invalid.items():
        features.append(_status_row(item, "invalid", "canonical candle failed deterministic validation"))
    for feature in features:
        feature.setdefault("dataset_revision", dataset_revision)
    features.sort(key=lambda item: (item["close_time_ms"] is None, item["close_time_ms"] or 0))
    label_outcomes.sort(key=lambda item: item["feature_close_time_ms"])
    labels = [item for item in label_outcomes if item["status"] == "eligible"]
    feature_fingerprint = _sha(features)
    label_fingerprint = _sha(labels)
    return {
        "feature_version": B2_FEATURE_VERSION,
        "target_version": B2_TARGET_VERSION,
        "dataset_revision": dataset_revision,
        "as_of": config.as_of,
        "features": features,
        "labels": labels,
        "label_outcomes": label_outcomes,
        "feature_fingerprint": feature_fingerprint,
        "label_fingerprint": label_fingerprint,
        "outcome_counts": _counts([item["status"] for item in features]),
        "label_outcome_counts": _counts([item["status"] for item in label_outcomes]),
    }


def _counts(values: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return dict(sorted(result.items()))


def _artifact_identity(artifact: dict[str, Any]) -> dict[str, Any]:
    return {key: artifact[key] for key in ("kind", "sha256", "size_bytes", "lineage")}


def build_splits(samples: list[dict[str, Any]], config: B2Config) -> dict[str, Any]:
    """Create chronological train/calibration/test partitions.

    At each boundary, samples whose target reaches the boundary are purged;
    the next five minutes are embargoed. This makes the overlap rule explicit
    even when a small fixture leaves a partition empty.
    """
    ordered = sorted(samples, key=lambda item: item["feature_close_time_ms"])
    if not ordered:
        return {
            "policy": {
                "purge": "remove rows with target_end_ms >= the next split boundary",
                "embargo": "remove the first 5 minutes after each split boundary",
                "horizon_minutes": 5,
                "boundaries_are_frozen_before_model_fit": True,
            },
            "boundaries": {},
            "rows": [],
            "counts": {},
        }
    n = len(ordered)
    train_boundary = ordered[max(1, min(n - 1, int(n * config.train_fraction)))]["feature_close_time_ms"]
    test_boundary = ordered[max(1, min(n - 1, int(n * (config.train_fraction + config.calibration_fraction))))]["feature_close_time_ms"]
    boundaries = {"train_calibration_ms": train_boundary, "calibration_test_ms": test_boundary}
    assignments = []
    for sample in ordered:
        feature_ms = sample["feature_close_time_ms"]
        target_end_ms = sample["target_end_ms"]
        if feature_ms < train_boundary and target_end_ms < train_boundary:
            split, reason = "train", "chronological train interval"
        elif feature_ms >= train_boundary + config.embargo_minutes * _MINUTE_MS and feature_ms < test_boundary and target_end_ms < test_boundary:
            split, reason = "calibration", "chronological calibration interval after embargo"
        elif feature_ms >= test_boundary + config.embargo_minutes * _MINUTE_MS:
            split, reason = "test", "chronological test interval after embargo"
        elif feature_ms < train_boundary or feature_ms < test_boundary:
            split, reason = "purged", "target overlaps a split boundary or lies in embargo"
        else:
            split, reason = "purged", "outside frozen split interval"
        assignments.append({"feature_close_time_ms": feature_ms, "target_end_ms": target_end_ms, "split": split, "reason": reason})
    return {
        "policy": {
            "purge": "remove rows with target_end_ms >= the next split boundary",
            "embargo": "remove the first 5 minutes after each split boundary",
            "horizon_minutes": 5,
            "boundaries_are_frozen_before_model_fit": True,
        },
        "boundaries": {key: value for key, value in boundaries.items()},
        "rows": assignments,
        "counts": _counts([item["split"] for item in assignments]),
    }


def _predictor_rate(train: list[dict[str, Any]], samples: list[dict[str, Any]]) -> list[float]:
    rate = sum(item["direction"] == "up" for item in train) / len(train) if train else 0.5
    return [rate] * len(samples)


def _conditional_rate(train: list[dict[str, Any]], samples: list[dict[str, Any]]) -> list[float]:
    groups: dict[str, list[bool]] = {"up": [], "down": [], "flat": []}
    for item in train:
        value = item["feature_values"]["log_return_1m"]
        group = "up" if value > 0 else "down" if value < 0 else "flat"
        groups[group].append(item["direction"] == "up")
    fallback = sum(item["direction"] == "up" for item in train) / len(train) if train else 0.5
    result = []
    for item in samples:
        value = item["feature_values"]["log_return_1m"]
        group = "up" if value > 0 else "down" if value < 0 else "flat"
        values = groups[group]
        result.append(sum(values) / len(values) if values else fallback)
    return result


def _log_loss(predictions: list[float], samples: list[dict[str, Any]]) -> float | None:
    if not samples:
        return None
    losses = []
    for probability, item in zip(predictions, samples):
        bounded = min(1 - 1e-15, max(1e-15, probability))
        losses.append(-math.log(bounded if item["direction"] == "up" else 1 - bounded))
    return sum(losses) / len(losses)


def _score(predictions: list[float], samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        return {"status": "unavailable", "n": 0, "log_loss": None, "brier": None, "accuracy": None}
    actual = [item["direction"] == "up" for item in samples]
    predicted = [probability >= 0.5 for probability in predictions]
    return {
        "status": "measured",
        "n": len(samples),
        "log_loss": _log_loss(predictions, samples),
        "brier": sum((probability - truth) ** 2 for probability, truth in zip(predictions, actual)) / len(samples),
        "accuracy": sum(prediction == truth for prediction, truth in zip(predicted, actual)) / len(samples),
    }


def _calibrate(raw: list[float], calibration: list[dict[str, Any]], calibration_raw: list[float], target: list[dict[str, Any]]) -> tuple[list[float], dict[str, Any]]:
    if not calibration:
        return raw, {"status": "unavailable", "method": "one-bin empirical calibration", "n": 0, "reason": "no leakage-safe calibration rows after purge/embargo"}
    rate = sum(item["direction"] == "up" for item in calibration) / len(calibration)
    return [rate] * len(target), {"status": "measured", "method": "one-bin empirical calibration", "n": len(calibration), "calibration_rate": rate, "raw_probability_fingerprint": _sha(calibration_raw)}


def _sample_rows(materialized: dict[str, Any]) -> list[dict[str, Any]]:
    labels = {item["feature_close_time_ms"]: item for item in materialized["labels"]}
    return [
        {**label, "feature_values": feature["values"]}
        for feature in materialized["features"]
        if feature["status"] == "eligible" and feature["close_time_ms"] in labels
        for label in [labels[feature["close_time_ms"]]]
    ]


def evaluate_baselines(materialized: dict[str, Any], config: B2Config) -> dict[str, Any]:
    samples = _sample_rows(materialized)
    splits = build_splits(samples, config)
    split_by_time = {item["feature_close_time_ms"]: item["split"] for item in splits["rows"]}
    train = [item for item in samples if split_by_time.get(item["feature_close_time_ms"]) == "train"]
    calibration = [item for item in samples if split_by_time.get(item["feature_close_time_ms"]) == "calibration"]
    test = [item for item in samples if split_by_time.get(item["feature_close_time_ms"]) == "test"]
    predictors = {
        "naive_0_5": lambda: [0.5] * len(test),
        "empirical_rate": lambda: _predictor_rate(train, test),
        "conditional_rate": lambda: _conditional_rate(train, test),
    }
    predictions: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}
    calibration_outputs: dict[str, Any] = {}
    for name, predictor in predictors.items():
        raw = predictor()
        calibration_raw = [0.5] * len(calibration) if name == "naive_0_5" else _predictor_rate(train, calibration) if name == "empirical_rate" else _conditional_rate(train, calibration)
        calibrated, calibration_output = _calibrate(raw, calibration, calibration_raw, test)
        calibration_outputs[name] = calibration_output
        metrics[name] = {"raw": _score(raw, test), "calibrated": _score(calibrated, test)}
        for sample, probability, calibrated_probability in zip(test, raw, calibrated):
            predictions.append({
                "model": name,
                "feature_close_time_ms": sample["feature_close_time_ms"],
                "target_end_ms": sample["target_end_ms"],
                "split": "test",
                "raw_probability_up": probability,
                "calibrated_probability_up": calibrated_probability,
                "actual_direction": sample["direction"],
            })
    return {"splits": splits, "predictions": predictions, "metrics": metrics, "calibration": calibration_outputs, "sample_count": len(samples)}


class B2Store:
    def __init__(self, root: str | Path, *, read_only: bool = False) -> None:
        self.root = Path(root)
        self.read_only = read_only
        self.runs = self.root / "runs"
        if not read_only:
            self.root.mkdir(parents=True, exist_ok=True)
            self.runs.mkdir(exist_ok=True)

    def _run_dir(self, run_id: str) -> Path:
        path = (self.runs / run_id).resolve()
        if not path.is_relative_to(self.runs.resolve()):
            raise ValueError("invalid B2 run ID")
        return path

    def _artifact_path(self, artifact: dict[str, Any]) -> Path:
        path = (self.root / artifact["path"]).resolve()
        if not path.is_relative_to(self.root.resolve()) or not path.is_file():
            raise ValueError(f"B2 artifact path is missing or outside storage: {artifact['kind']}")
        return path

    def _write(self, path: Path, value: Any) -> dict[str, Any]:
        raw = _json(value).encode("utf-8")
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"immutable B2 artifact collision: {path.name}")
        if not path.exists():
            path.write_bytes(raw)
        relative = path.resolve().relative_to(self.root.resolve()).as_posix()
        return {"path": relative, "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}

    def persist(self, run: dict[str, Any]) -> dict[str, Any]:
        if self.read_only:
            raise ValueError("B2 store is read-only")
        directory = self._run_dir(run["run_id"])
        directory.mkdir(parents=True, exist_ok=True)
        artifacts = []
        for kind in ("config", "features", "labels", "splits", "predictions", "metrics", "calibration"):
            artifact = self._write(directory / f"{kind}.json", run[kind])
            artifacts.append({"kind": kind, **artifact, "lineage": [run["dataset_revision"], run["feature_fingerprint"], run["label_fingerprint"]]})
        lineage = {"dataset_revision": run["dataset_revision"], "feature_fingerprint": run["feature_fingerprint"], "label_fingerprint": run["label_fingerprint"], "artifact_lineage": artifacts}
        lineage_artifact = self._write(directory / "lineage.json", lineage)
        artifacts.append({"kind": "lineage", **lineage_artifact, "lineage": [item["sha256"] for item in artifacts]})
        manifest = {key: run[key] for key in ("schema", "api_version", "run_id", "dataset_revision", "feature_fingerprint", "label_fingerprint", "baselines", "sample_count")}
        manifest.update({"artifacts": artifacts, "replay_fingerprint": _sha({"run": run, "artifacts": [_artifact_identity(item) for item in artifacts]}), "lineage": lineage})
        self._write(directory / "manifest.json", manifest)
        return manifest

    def inspect(self, run_id: str, resource: str = "manifest", item_id: str | None = None) -> Any:
        directory = self._run_dir(run_id)
        if not directory.is_dir() or not (directory / "manifest.json").is_file():
            raise KeyError(run_id)
        if resource not in {"manifest", "config", "features", "labels", "splits", "predictions", "metrics", "calibration", "lineage", "artifacts"}:
            raise KeyError(resource)
        if resource in {"manifest", "artifacts"}:
            path = directory / "manifest.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if resource == "manifest" else value["artifacts"]
        manifest = self.inspect(run_id, "manifest")
        artifact = next((item for item in manifest["artifacts"] if item["kind"] == resource), None)
        if artifact is None:
            raise KeyError(resource)
        path = self._artifact_path(artifact)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != artifact["sha256"]:
            raise ValueError(f"B2 artifact hash mismatch: {resource}")
        value = json.loads(raw)
        if item_id is None:
            return {"run_id": run_id, "resource": resource, "value": value}
        if isinstance(value, list):
            return [item for item in value if str(item.get("feature_close_time_ms", item.get("model", ""))) == item_id]
        raise KeyError(item_id)

    def replay(self, run_id: str) -> dict[str, Any]:
        manifest = self.inspect(run_id, "manifest")
        if manifest.get("schema") != B2_RUN_SCHEMA or manifest.get("api_version") != B2_API_VERSION:
            raise ValueError("unsupported B2 run manifest")
        for artifact in manifest["artifacts"]:
            path = self._artifact_path(artifact)
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != artifact["sha256"]:
                raise ValueError(f"B2 artifact hash mismatch: {artifact['kind']}")
        directory = self._run_dir(run_id)
        expected_run = {
            key: json.loads((directory / f"{key}.json").read_text(encoding="utf-8"))
            for key in ("config", "features", "labels", "splits", "predictions", "metrics", "calibration")
        }
        expected_run.update({key: manifest[key] for key in ("schema", "api_version", "run_id", "dataset_revision", "feature_fingerprint", "label_fingerprint", "baselines", "sample_count")})
        expected = _sha({"run": expected_run, "artifacts": [_artifact_identity(item) for item in manifest["artifacts"]]})
        if expected != manifest["replay_fingerprint"]:
            raise ValueError("B2 replay fingerprint mismatch")
        return {"run_id": run_id, "replayed": True, "replay_fingerprint": manifest["replay_fingerprint"], "network_requests": 0}


def run_b2(history: HistoryStore, dataset_revision: str, store: B2Store, config: B2Config | None = None) -> dict[str, Any]:
    manifest = history.inspect_manifest(dataset_revision)
    if config is None:
        config = B2Config("btc-b2-offline", manifest["availability_timestamp_max"])
    if config.as_of is None:
        config = B2Config(**{**asdict(config), "as_of": manifest["availability_timestamp_max"]})
    candles = history.inspect_candles(dataset_revision)
    materialized = materialize_rows(candles, config, dataset_revision=dataset_revision)
    evaluation = evaluate_baselines(materialized, config)
    identity = {"config": asdict(config), "dataset_revision": dataset_revision, "feature_fingerprint": materialized["feature_fingerprint"], "label_fingerprint": materialized["label_fingerprint"]}
    run_id = f"btc-b2-{_sha(identity)[:20]}"
    run = {
        "schema": B2_RUN_SCHEMA,
        "api_version": B2_API_VERSION,
        "run_id": run_id,
        "dataset_revision": dataset_revision,
        "feature_fingerprint": materialized["feature_fingerprint"],
        "label_fingerprint": materialized["label_fingerprint"],
        "baselines": ["naive_0_5", "empirical_rate", "conditional_rate"],
        "sample_count": evaluation["sample_count"],
        "config": asdict(config),
        "features": materialized["features"],
        "labels": {"rows": materialized["labels"], "outcomes": materialized["label_outcomes"], "fingerprint": materialized["label_fingerprint"]},
        "splits": evaluation["splits"],
        "predictions": evaluation["predictions"],
        "metrics": evaluation["metrics"],
        "calibration": evaluation["calibration"],
    }
    persisted = store.persist(run)
    return {**run, "artifacts": persisted["artifacts"], "replay_fingerprint": persisted["replay_fingerprint"]}
