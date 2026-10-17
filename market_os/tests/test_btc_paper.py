from __future__ import annotations

import json
import math
from pathlib import Path

from market_os.btc_paper import (
    BTC_API_VERSION,
    ClosedCandle,
    DatasetManifest,
    ExperimentConfig,
    FeatureRow,
    LabelRow,
    PredictionRequest,
    RawMarketEvent,
    FEATURE_VERSION,
    TARGET_VERSION,
    PredictionResult,
    btc_contract_from_json,
    btc_contract_to_json,
    replay_fixture,
)
from market_os.contracts import ContractError
import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "btc_paper" / "replay.json"


def test_fixture_replay_is_deterministic_and_classifies_bad_observations() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    first = replay_fixture(fixture)
    second = replay_fixture(fixture)

    assert first == second
    assert len(first.provenance) == len(fixture["events"])
    assert [candle.open_time for candle in first.candles] == [
        "2026-01-01T00:00:00+00:00",
        "2026-01-01T00:01:00+00:00",
        "2026-01-01T00:02:00+00:00",
        "2026-01-01T00:03:00+00:00",
        "2026-01-01T00:04:00+00:00",
        "2026-01-01T00:05:00+00:00",
        "2026-01-01T00:06:00+00:00",
        "2026-01-01T00:07:00+00:00",
        "2026-01-01T00:08:00+00:00",
        "2026-01-01T00:09:00+00:00",
        "2026-01-01T00:10:00+00:00",
        "2026-01-01T00:20:00+00:00",
    ]
    assert {outcome.status for outcome in first.outcomes} >= {
        "duplicate", "open", "invalid", "stale", "out_of_order", "accepted"
    }
    assert first.manifest.gaps == (("2026-01-01T00:11:00+00:00", "2026-01-01T00:20:00+00:00"),)
    assert first.features[0].input_refs == (first.candles[0].provenance_id,)
    assert first.features[0].source_timestamp == first.candles[0].source_timestamp
    assert first.features[0].received_at == first.candles[0].received_at
    assert first.features[0].input_fingerprint == first.labels[0].feature_input_fingerprint
    assert first.labels[0].target_fingerprint != first.labels[0].feature_input_fingerprint
    assert first.features[0].decision_eligible_at == first.candles[0].availability_timestamp
    assert first.labels[0].target_end == "2026-01-01T00:06:00+00:00"
    assert first.labels[0].target_end not in first.features[0].observable_fields
    assert first.manifest.input_fingerprint == second.manifest.input_fingerprint
    assert [label.target_end for label in first.labels] == [
        "2026-01-01T00:06:00+00:00",
        "2026-01-01T00:07:00+00:00",
        "2026-01-01T00:08:00+00:00",
        "2026-01-01T00:09:00+00:00",
        "2026-01-01T00:10:00+00:00",
        "2026-01-01T00:11:00+00:00",
    ]
    delayed = next(row for row in first.features if row.candle_close_time == "2026-01-01T00:21:00+00:00")
    assert delayed.decision_eligible_at == "2026-01-01T00:21:00+00:00"
    assert {"bar-20", "bar-20-conflict"}.intersection(delayed.input_refs)
    earlier = next(row for row in first.features if row.candle_close_time == "2026-01-01T00:10:00+00:00")
    assert "bar-20" not in earlier.input_refs
    assert {outcome.status for outcome in first.outcomes} >= {"conflict"}
    assert next(item for item in first.outcomes if item.event_id == "bar-04-copy").status == "duplicate"
    assert next(item for item in first.outcomes if item.event_id == "bar-invalid-volume").status == "invalid"


def test_btc_contract_round_trip_and_rejects_non_paper_results() -> None:
    config = ExperimentConfig("btc-fixture")
    assert config.api_version == BTC_API_VERSION
    assert btc_contract_from_json(btc_contract_to_json(config), ExperimentConfig) == config
    with pytest.raises(ContractError, match="strictly paper-only"):
        ExperimentConfig("btc-fixture", execution_mode="live")
    with pytest.raises(ContractError, match="cannot contain a model or action"):
        PredictionResult("btc-fixture", "2026-01-01T00:01:00+00:00", "btc-dataset-aaaaaaaaaaaaaaaa", "a" * 64, "b" * 64, "fixture-only", "buy")
    with pytest.raises(ContractError, match="feature version is unsupported"):
        PredictionRequest("btc-fixture", "2026-01-01T00:01:00+00:00", "btc-dataset-aaaaaaaaaaaaaaaa", "a" * 64, "v2")


def test_btc_contract_json_rejects_unknown_fields_and_missing_fields() -> None:
    with pytest.raises(ContractError, match="unknown BTC contract field"):
        btc_contract_from_json('{"experiment_id":"fixture","surprise":true}', ExperimentConfig)
    with pytest.raises(ContractError, match="missing a required field"):
        btc_contract_from_json('{"api_version":"market-os.btc-paper.v1"}', ExperimentConfig)


def test_closed_candle_rejects_non_utc_or_invalid_ohlcv() -> None:
    payload = {
        "symbol": "BTCUSDT", "interval": "1m", "open_time": "2026-01-01T00:00:00+00:00",
        "close_time": "2026-01-01T00:01:00+00:00", "open": 100.0, "high": 99.0,
        "low": 98.0, "close": 99.5, "volume": 1.0, "source_timestamp": "2026-01-01T00:01:00+00:00",
        "received_at": "2026-01-01T00:01:00+00:00", "availability_timestamp": "2026-01-01T00:01:00+00:00",
        "provenance_id": "fixture", "candle_fingerprint": "a" * 64,
    }
    with pytest.raises(ContractError, match="do not contain"):
        ClosedCandle(**payload)
    payload["high"] = 101.0
    payload["availability_timestamp"] = "2026-01-01T01:01:00+01:00"
    with pytest.raises(ContractError, match="must be in UTC"):
        ClosedCandle(**payload)


def test_replay_fingerprint_is_independent_of_packet_order_and_nan_is_classified() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ordered = replay_fixture(fixture)
    shuffled = replay_fixture({**fixture, "events": list(reversed(fixture["events"]))})
    assert ordered.manifest == shuffled.manifest
    assert ordered.candles == shuffled.candles
    renamed = json.loads(FIXTURE.read_text(encoding="utf-8"))
    renamed["events"] = [{**event, "event_id": f"renamed-{index}"} for index, event in enumerate(renamed["events"])]
    assert ordered.manifest == replay_fixture(renamed).manifest

    fixture["events"].append({
        "event_id": "bar-nan", "symbol": "BTCUSDT", "source": "synthetic-fixture",
        "source_timestamp": "2026-01-01T00:22:00+00:00", "received_at": "2026-01-01T00:22:00+00:00",
        "availability_timestamp": "2026-01-01T00:22:00+00:00",
        "payload": {"interval": "1m", "open_time": "2026-01-01T00:21:00+00:00", "close_time": "2026-01-01T00:22:00+00:00", "is_closed": True, "open": math.nan, "high": 1, "low": 1, "close": 1, "volume": 0},
    })
    replay = replay_fixture(fixture)
    assert next(item for item in replay.outcomes if item.event_id == "bar-nan").status == "invalid"


def test_reused_event_id_with_different_payload_is_a_conflict() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    changed = dict(fixture["events"][0])
    changed["payload"] = {**changed["payload"], "close": 100.75}
    fixture["events"].append(changed)
    replay = replay_fixture(fixture)
    assert replay.outcomes[-1].status == "conflict"
    baseline = replay_fixture(json.loads(FIXTURE.read_text(encoding="utf-8")))
    assert replay.manifest == baseline.manifest


def test_all_btc_contracts_round_trip_from_json() -> None:
    replay = replay_fixture(json.loads(FIXTURE.read_text(encoding="utf-8")))
    values = [
        replay.provenance[0], replay.candles[0], replay.manifest, replay.features[0], replay.labels[0],
        PredictionRequest("btc-fixture", replay.features[0].decision_eligible_at,
                          replay.features[0].dataset_revision, replay.features[0].input_fingerprint,
                          replay.features[0].feature_version),
        PredictionResult("btc-fixture", replay.features[0].decision_eligible_at,
                         replay.features[0].dataset_revision, replay.features[0].input_fingerprint,
                         "b" * 64),
        ExperimentConfig("btc-fixture"),
    ]
    for value in values:
        assert btc_contract_from_json(btc_contract_to_json(value), type(value)) == value


def test_contracts_reject_timestamp_order_and_feature_label_leakage() -> None:
    with pytest.raises(ContractError, match="must not precede"):
        RawMarketEvent("event-1", "BTCUSDT", "fixture", "2026-01-01T00:02:00+00:00",
                       "2026-01-01T00:01:00+00:00", "2026-01-01T00:03:00+00:00", "a" * 64)
    with pytest.raises(ContractError, match="labels cannot be observable"):
        FeatureRow("BTCUSDT", FEATURE_VERSION, "2026-01-01T00:01:00+00:00",
                   "2026-01-01T00:01:00+00:00", "2026-01-01T00:01:00+00:00",
                   "2026-01-01T00:01:00+00:00", "2026-01-01T00:01:00+00:00",
                   ("open", "high", "low", "close", "volume"),
                   (("target_return", 0.01),),
                   "btc-dataset-" + "a" * 16, "a" * 64, ("candle-1",))
    with pytest.raises(ContractError, match="direction must match"):
        LabelRow("BTCUSDT", TARGET_VERSION, "2026-01-01T00:01:00+00:00",
                 "2026-01-01T00:06:00+00:00", 0.01, "down", "a" * 64, "b" * 64, ("future-1",))


def test_contract_json_rejects_non_finite_values_and_replay_requires_fixture_schema() -> None:
    with pytest.raises(ContractError, match="non-finite"):
        btc_contract_from_json('{"experiment_id":"fixture","horizon_minutes":NaN}', ExperimentConfig)
    with pytest.raises(ContractError, match="fixture schema"):
        replay_fixture({"as_of": "2026-01-01T00:00:00+00:00", "events": []})


def test_fixture_replay_is_repeatable_and_does_not_write_local_state(tmp_path) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert replay_fixture(fixture) == replay_fixture(fixture)
    assert list(tmp_path.iterdir()) == []


def test_label_contract_enforces_exact_five_minute_horizon() -> None:
    with pytest.raises(ContractError, match="five minutes"):
        LabelRow("BTCUSDT", TARGET_VERSION, "2026-01-01T00:01:00+00:00", "2026-01-01T00:07:00+00:00", 0.01, "up", "a" * 64, "b" * 64, ("future-1",))


def test_replay_never_uses_not_yet_available_candles_and_handles_empty_input() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fixture["as_of"] = "2026-01-01T00:20:00+00:00"
    fixture["events"].append({
        "event_id": "late-bar", "symbol": "BTCUSDT", "source": "synthetic-fixture",
        "source_timestamp": "2026-01-01T00:30:00+00:00", "received_at": "2026-01-01T00:30:00+00:00",
        "availability_timestamp": "2026-01-01T00:30:00+00:00",
        "payload": {"interval": "1m", "open_time": "2026-01-01T00:29:00+00:00", "close_time": "2026-01-01T00:30:00+00:00", "is_closed": True, "open": 103, "high": 104, "low": 102, "close": 103.5, "volume": 1},
    })
    replay = replay_fixture(fixture)
    assert next(item for item in replay.outcomes if item.event_id == "late-bar").status == "not_yet_available"
    assert "late-bar" not in replay.features[-1].input_refs

    fixture["events"] = []
    empty = replay_fixture(fixture)
    assert empty.manifest.candle_count == 0
    assert empty.manifest.first_open_time is None
