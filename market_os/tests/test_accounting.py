from __future__ import annotations

import json

import pytest

from market_os.strategy import NormalizedNumericalSignal, StrategyConfig
from market_os.strategy_replay import StrategySignalFixture, run_strategy_replay
from market_os.accounting import build_synthetic_accounting_report, verify_synthetic_accounting
from market_os.paper_venue import SyntheticMarketEvent, VenueConfig


def event(event_id: str, time_ms: int, bid: float = 100.0, ask: float = 101.0) -> SyntheticMarketEvent:
    return SyntheticMarketEvent(event_id, "BTCUSDT", time_ms, bid, ask, (bid + ask) / 2.0, 1.0, "a" * 64)


def signal(signal_id: str, time_ms: int, probability: float, status: str = "usable") -> NormalizedNumericalSignal:
    return NormalizedNumericalSignal(signal_id, "BTCUSDT", time_ms, "calibrated_probability", probability, status, "b" * 64)


def replay():
    events = (event("e1", 1_000), event("e2", 2_000, 102.0, 103.0), event("e3", 3_000, 99.0, 100.0))
    fixtures = (
        StrategySignalFixture("e1", signal("s1", 1_000, 0.9)),
        StrategySignalFixture("e2", signal("s2", 2_000, 0.1)),
    )
    return run_strategy_replay(events, fixtures, strategy_config=StrategyConfig(allocation_fraction=0.5), venue_config=VenueConfig())


def test_accounting_reuses_venue_totals_and_is_deterministic() -> None:
    first = build_synthetic_accounting_report(replay())
    second = build_synthetic_accounting_report(replay())
    assert verify_synthetic_accounting(first, second)
    payload = first.to_dict()
    assert payload["decision_counts"] == {"buy": 1, "sell": 1, "missing_signal": 1}
    assert payload["accounting"]["fill_count"] == 2
    assert payload["accounting"]["turnover_usdt"] == pytest.approx(payload["accounting"]["total_notional_usdt"])
    assert payload["accounting"]["total_fees_usdt"] > 0
    assert payload["accounting"]["final_btc_quantity"] == pytest.approx(0.0)


def test_accounting_reports_terminal_order_without_fabricating_fill() -> None:
    report = build_synthetic_accounting_report(
        run_strategy_replay(
            (event("e1", 1_000),),
            (StrategySignalFixture("e1", signal("s1", 1_000, 0.9)),),
        )
    )
    payload = report.to_dict()
    assert payload["unexecuted_end_of_stream_count"] == 1
    assert payload["pending_command_count"] == 0
    assert payload["rejected_command_count"] == 0


def test_accounting_counts_venue_rejections() -> None:
    report = build_synthetic_accounting_report(
        run_strategy_replay(
            (event("e1", 1_000), event("e2", 2_000, 102.0, 103.0)),
            (StrategySignalFixture("e1", signal("s1", 1_000, 0.9)),),
        )
    )
    payload = report.to_dict()
    assert payload["rejected_command_count"] == 1
    assert payload["rejection_reasons"] == {"order exceeds max_order_notional_usdt": 1}
    assert payload["accounting"]["fill_count"] == 0


def test_accounting_projection_has_only_top_level_fingerprint_added() -> None:
    report = build_synthetic_accounting_report(replay())
    projection = json.loads(report.canonical_payload)
    assert "fingerprint" not in projection
    assert report.to_dict()["fingerprint"] == report.fingerprint


def test_accounting_rejects_tampered_replay_report() -> None:
    source = replay()
    with pytest.raises(ValueError, match="fingerprint"):
        build_synthetic_accounting_report(type(source)(source.canonical_payload, "0" * 64))


def test_cli_inspects_replay_and_accounting_without_mutating_source(tmp_path, capsys) -> None:
    from market_os.cli import main

    path = tmp_path / "strategy-replay.json"
    original = json.dumps(replay().to_dict(), sort_keys=True)
    path.write_text(original, encoding="utf-8")
    assert main(["synthetic", "inspect", "--replay-report", str(path), "--resource", "accounting"]) == 0
    accounting = json.loads(capsys.readouterr().out)
    assert accounting["schema"] == "market-os.b3-6.synthetic-accounting-report@v1"
    assert accounting["accounting"]["fill_count"] == 2
    assert path.read_text(encoding="utf-8") == original

    assert main(["synthetic", "inspect", "--replay-report", str(path), "--resource", "replay"]) == 0
    replay_payload = json.loads(capsys.readouterr().out)
    assert replay_payload["schema"] == "market-os.b3-5.synthetic-strategy-session@v1"


def test_cli_rejects_tampered_strategy_replay(tmp_path) -> None:
    from market_os.cli import main

    payload = replay().to_dict()
    payload["decision_counts"]["buy"] = 99
    path = tmp_path / "tampered-replay.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SystemExit, match="invalid synthetic replay report"):
        main(["synthetic", "inspect", "--replay-report", str(path)])
