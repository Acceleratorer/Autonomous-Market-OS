#!/usr/bin/env python3
"""Recompute UTC-day scoring diagnostics for the frozen BTC B2 test split."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "btc-b2-dde76de3b2965ac6f66a"
SOURCE = ROOT / ".market_os" / "btc-b2" / "runs" / RUN_ID / "predictions.json"
OUTPUT = ROOT / "docs" / "evidence" / "btc-b2-daily-stability-diagnostic-2026-11-20.json"
MODELS = ("conditional_rate", "empirical_rate", "naive_0_5")


def utc_minute(timestamp_ms: int) -> datetime:
    return datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc)


def score(rows: list[dict[str, object]], field: str) -> dict[str, float]:
    outcomes = [int(row["actual_direction"] == "up") for row in rows]
    probabilities = [float(row[field]) for row in rows]
    if not probabilities or any(not 0 < probability < 1 for probability in probabilities):
        raise ValueError(f"invalid or empty probability series: {field}")

    count = len(rows)
    return {
        "accuracy_at_0_5": sum(
            (probability >= 0.5) == bool(outcome)
            for outcome, probability in zip(outcomes, probabilities)
        ) / count,
        "brier_score": sum(
            (probability - outcome) ** 2
            for outcome, probability in zip(outcomes, probabilities)
        ) / count,
        "log_loss": sum(
            -(outcome * math.log(probability) + (1 - outcome) * math.log1p(-probability))
            for outcome, probability in zip(outcomes, probabilities)
        ) / count,
        "mean_probability_up": sum(probabilities) / count,
        "predicted_up_rate_at_0_5": sum(probability >= 0.5 for probability in probabilities) / count,
    }


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    outcomes = [int(row["actual_direction"] == "up") for row in rows]
    observed_rate = sum(outcomes) / len(outcomes)
    raw = score(rows, "raw_probability_up")
    calibrated = score(rows, "calibrated_probability_up")
    return {
        "n": len(rows),
        "observed_up_rate": observed_rate,
        "raw": raw,
        "calibrated": calibrated,
        "calibration_error_raw": raw["mean_probability_up"] - observed_rate,
        "calibration_error_calibrated": calibrated["mean_probability_up"] - observed_rate,
    }


def build_evidence() -> dict[str, object]:
    source_bytes = SOURCE.read_bytes()
    prediction_rows = json.loads(source_bytes)
    rows = [row for row in prediction_rows if row["split"] == "test"]
    if not rows or any(row["split"] != "test" for row in prediction_rows):
        raise ValueError("expected this immutable predictions artifact to contain only test rows")
    if {row["model"] for row in rows} != set(MODELS):
        raise ValueError("the frozen test artifact has an unexpected prediction-arm set")

    by_model: dict[str, list[dict[str, object]]] = {
        model: [row for row in rows if row["model"] == model] for model in MODELS
    }
    if any(not model_rows for model_rows in by_model.values()):
        raise ValueError("the frozen test artifact is missing a prediction arm")

    timestamps: dict[str, set[int]] = {}
    actual_by_timestamp: dict[int, str] = {}
    target_end_by_timestamp: dict[int, int] = {}
    seen_model_timestamps: set[tuple[str, int]] = set()
    for model, model_rows in by_model.items():
        timestamps[model] = set()
        for row in model_rows:
            timestamp = int(row["feature_close_time_ms"])
            actual = str(row["actual_direction"])
            if actual not in {"up", "down", "flat"}:
                raise ValueError(f"unknown outcome label: {actual}")
            if (model, timestamp) in seen_model_timestamps:
                raise ValueError(f"duplicate model/timestamp row: {model}, {timestamp}")
            seen_model_timestamps.add((model, timestamp))
            timestamps[model].add(timestamp)
            if timestamp in actual_by_timestamp and actual_by_timestamp[timestamp] != actual:
                raise ValueError(f"outcome differs across arms at {timestamp}")
            actual_by_timestamp[timestamp] = actual
            target_end = int(row["target_end_ms"])
            if target_end != timestamp + 300_000:
                raise ValueError(f"unexpected five-minute target window at {timestamp}")
            if timestamp in target_end_by_timestamp and target_end_by_timestamp[timestamp] != target_end:
                raise ValueError(f"target end differs across arms at {timestamp}")
            target_end_by_timestamp[timestamp] = target_end

    if len({frozenset(value) for value in timestamps.values()}) != 1:
        raise ValueError("prediction arms do not share the same test timestamps")

    ordered_timestamps = sorted(actual_by_timestamp)
    minute_steps = [
        right - left for left, right in zip(ordered_timestamps, ordered_timestamps[1:])
    ]
    non_minute_steps = sum(step != 60_000 for step in minute_steps)
    if non_minute_steps:
        raise ValueError("the frozen test timestamps are not a contiguous one-minute sequence")
    day_rows: dict[str, dict[str, list[dict[str, object]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for model, model_rows in by_model.items():
        for row in model_rows:
            day = utc_minute(int(row["feature_close_time_ms"])).date().isoformat()
            day_rows[day][model].append(row)

    daily: dict[str, object] = {}
    for day, arm_rows in sorted(day_rows.items()):
        reference_rows = next(iter(arm_rows.values()))
        daily[day] = {
            "n": len(reference_rows),
            "positive": sum(row["actual_direction"] == "up" for row in reference_rows),
            "positive_rate": sum(row["actual_direction"] == "up" for row in reference_rows)
            / len(reference_rows),
            "by_model": {
                model: summarize(arm_rows[model])
                for model in MODELS
            },
        }

    unique_outcomes = list(actual_by_timestamp.values())
    positive = sum(outcome == "up" for outcome in unique_outcomes)
    negative = sum(outcome == "down" for outcome in unique_outcomes)
    flat = sum(outcome == "flat" for outcome in unique_outcomes)
    daily_rates = [float(value["positive_rate"]) for value in daily.values()]
    calibrated_worse_brier = all(
        daily[day]["by_model"][model]["calibrated"]["brier_score"]
        > daily[day]["by_model"][model]["raw"]["brier_score"]
        for day in daily
        for model in ("empirical_rate", "conditional_rate")
    )
    calibrated_worse_log_loss = all(
        daily[day]["by_model"][model]["calibrated"]["log_loss"]
        > daily[day]["by_model"][model]["raw"]["log_loss"]
        for day in daily
        for model in ("empirical_rate", "conditional_rate")
    )
    if not calibrated_worse_brier or not calibrated_worse_log_loss:
        raise ValueError("daily calibration comparison changed; review the report before regeneration")

    return {
        "schema": "market-os.btc-b2-daily-stability-diagnostic@v1",
        "created_at": date(2026, 11, 20).isoformat(),
        "status": "exploratory_diagnostic",
        "scope": {
            "run_id": RUN_ID,
            "source_artifact": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "split": "test",
            "prediction_rows": len(rows),
            "models": list(MODELS),
            "unique_timestamps": len(ordered_timestamps),
            "duplicate_model_timestamp_rows": 0,
            "matched_target_end_times_across_arms": True,
            "non_minute_steps": non_minute_steps,
            "test_start_utc": utc_minute(ordered_timestamps[0]).isoformat().replace("+00:00", "Z"),
            "test_end_utc": utc_minute(ordered_timestamps[-1]).isoformat().replace("+00:00", "Z"),
        },
        "method": {
            "grouping": "UTC calendar date derived from feature_close_time_ms",
            "outcome": "up is positive; down and flat are non-positive",
            "classification_threshold": "probability_up >= 0.5 predicts up",
            "probability_metrics": ["Brier score", "log loss"],
            "calibration_error": "mean_probability_up - observed_up_rate",
            "calibration": "use the persisted one-bin probability; do not refit",
            "rounding": "full Python double precision in machine-readable values",
            "test_set_policy": "read-only; no tuning, refitting, or arm selection",
        },
        "label_counts": {
            "positive": positive,
            "negative": negative,
            "flat_non_positive": flat,
            "non_positive_total": negative + flat,
            "positive_rate": positive / len(unique_outcomes),
        },
        "overall_by_model": {
            model: summarize(model_rows) for model, model_rows in by_model.items()
        },
        "daily_utc": daily,
        "summary_checks": {
            "empirical_raw_predicts_non_positive_every_day": all(
                daily[day]["by_model"]["empirical_rate"]["raw"]["predicted_up_rate_at_0_5"] == 0
                for day in daily
            ),
            "conditional_raw_predicts_non_positive_every_day": all(
                daily[day]["by_model"]["conditional_rate"]["raw"]["predicted_up_rate_at_0_5"] == 0
                for day in daily
            ),
            "one_bin_calibration_worse_brier_than_both_raw_arms_on_every_day": calibrated_worse_brier,
            "one_bin_calibration_worse_log_loss_than_both_raw_arms_on_every_day": calibrated_worse_log_loss,
            "daily_positive_rate_min": min(daily_rates),
            "daily_positive_rate_max": max(daily_rates),
        },
        "interpretation_limits": [
            "This is a descriptive check of one frozen six-day test window, not multi-period or regime stability.",
            "Each feature close advances one minute while the target looks five minutes ahead; adjacent outcomes overlap and are temporally dependent.",
            "The empirical and conditional raw arms predict non-positive for every row, so their accuracy equals that day's non-positive share and does not show row-level discrimination.",
            "The persisted one-bin calibrated probability scores worse than both raw statistical arms on each of the six UTC days; this comparison does not authorize retuning on the test set.",
            "No profitability, execution-cost, paper-fill, or live-trading claim follows from these scores.",
        ],
    }


def main() -> None:
    evidence = build_evidence()
    OUTPUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    print(f"Source SHA-256: {evidence['scope']['source_sha256']}")
    print(f"UTC days: {len(evidence['daily_utc'])}; unique test timestamps: {evidence['scope']['unique_timestamps']}")
    print(f"Calibration worsened Brier every day: {evidence['summary_checks']['one_bin_calibration_worse_brier_than_both_raw_arms_on_every_day']}")
    print(f"Calibration worsened log loss every day: {evidence['summary_checks']['one_bin_calibration_worse_log_loss_than_both_raw_arms_on_every_day']}")


if __name__ == "__main__":
    main()
