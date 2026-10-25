from __future__ import annotations

import json

import pytest

from market_os.b34_strategy import NormalizedNumericalSignal, StrategyConfig
from market_os.b35_strategy_replay import StrategySignalFixture
from market_os.b38_synthetic_session import (
    FIXTURE_SCHEMA,
    SyntheticSessionFixture,
    fixture_from_dict,
    run_synthetic_fixture,
    write_synthetic_session_run,
)
from market_os.paper_venue import SyntheticMarketEvent, VenueConfig


def event(event_id: str, time_ms: int, bid: float = 100.0, ask: float = 101.0) -> SyntheticMarketEvent:
    return SyntheticMarketEvent(event_id, "BTCUSDT", time_ms, bid, ask, (bid + ask) / 2.0, 1.0, "a" * 64)


def signal(signal_id: str, time_ms: int, probability: float) -> NormalizedNumericalSignal:
    return NormalizedNumericalSignal(signal_id, "BTCUSDT", time_ms, "calibrated_probability", probability, "usable", "b" * 64)


def fixture() -> SyntheticSessionFixture:
    return SyntheticSessionFixture(
        StrategyConfig(allocation_fraction=0.5),
        VenueConfig(),
        (event("e1", 1_000), event("e2", 2_000, 102.0, 103.0), event("e3", 3_000, 99.0, 100.0)),
        (StrategySignalFixture("e1", signal("s1", 1_000, 0.9)), StrategySignalFixture("e2", signal("s2", 2_000, 0.1))),
    )


def test_fixture_round_trip_and_run_are_deterministic() -> None:
    source = fixture()
    decoded = fixture_from_dict(source.to_dict())
    first = run_synthetic_fixture(source)
    second = run_synthetic_fixture(decoded)
    assert decoded == source
    assert first.replay == second.replay
    assert first.accounting == second.accounting


def test_writer_creates_fingerprinted_artifacts(tmp_path) -> None:
    result = write_synthetic_session_run(run_synthetic_fixture(fixture()), tmp_path)
    assert result["schema"] == "market-os.b3-8.synthetic-session-manifest@v1"
    assert result["files"] == {"replay": "strategy-replay.json", "accounting": "accounting.json"}
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    replay = json.loads((tmp_path / "strategy-replay.json").read_text(encoding="utf-8"))
    accounting = json.loads((tmp_path / "accounting.json").read_text(encoding="utf-8"))
    assert manifest["fixture_fingerprint"] == fixture().fingerprint
    assert manifest["replay_fingerprint"] == replay["fingerprint"]
    assert manifest["accounting_fingerprint"] == accounting["fingerprint"]
    assert manifest["synthetic_only"] is True


def test_writer_does_not_overwrite_existing_artifacts(tmp_path) -> None:
    write_synthetic_session_run(run_synthetic_fixture(fixture()), tmp_path)
    with pytest.raises(FileExistsError, match="already exist"):
        write_synthetic_session_run(run_synthetic_fixture(fixture()), tmp_path)


def test_fixture_rejects_unknown_fields_and_tampered_fingerprint() -> None:
    payload = fixture().to_dict()
    payload["unexpected"] = True
    with pytest.raises(ValueError, match="unsupported fields"):
        fixture_from_dict(payload)
    payload = fixture().to_dict()
    payload["fingerprint"] = "0" * 64
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        fixture_from_dict(payload)


def test_fixture_requires_the_canonical_schema_and_synthetic_marker() -> None:
    payload = fixture().to_dict()
    payload["schema"] = FIXTURE_SCHEMA + ".other"
    with pytest.raises(ValueError, match="synthetic boundary|schema"):
        fixture_from_dict(payload)


def test_cli_run_writes_replay_accounting_and_manifest(tmp_path, capsys) -> None:
    from pathlib import Path

    from market_os.cli import main

    fixture_path = Path(__file__).parent / "fixtures" / "b38" / "synthetic_session.json"
    assert main(["synthetic", "run", "--fixture", str(fixture_path), "--output", str(tmp_path)]) == 0
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert json.loads(capsys.readouterr().out)["replay_fingerprint"] == manifest["replay_fingerprint"]
    assert (tmp_path / "strategy-replay.json").exists()
    assert (tmp_path / "accounting.json").exists()
