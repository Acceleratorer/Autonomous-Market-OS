from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

import pytest

from market_os.adapters.vibe_trading import FixtureMarketDataAdapter, VibeTradingAdapter, VibeTradingUnavailable
from market_os import cli
from market_os.api import make_handler
from market_os.provider_selection import ProviderSelectionError, selected_workflow
from market_os.providers import ProviderCancelled, ProviderDeadline
from market_os.store import RunStore
from market_os.tests.provider_runtimes import find_optional_python
from market_os.workflow import MarketWorkflow


FIXTURE = Path(__file__).parent / "fixtures" / "vibe_trading" / "etf_ohlcv.json"
REFERENCE_ROOT = Path(os.environ.get("MARKET_OS_VIBE_TRADING_ROOT", "D:/Code/Github/company-projects/Vibe-Trading"))


def _vibe_python() -> str | None:
    return find_optional_python(
        "MARKET_OS_VIBE_TRADING_PYTHON",
        "market-os-m2.1-vibe",
        "from pydantic import ValidationError; import pandas, defusedxml; from src.tools.backtest_tool import run_backtest",
        pythonpath=REFERENCE_ROOT / "agent",
        include_system_python=True,
    )


def test_fixture_provider_normalizes_three_synthetic_etfs() -> None:
    provider = FixtureMarketDataAdapter(FIXTURE)
    bars = provider.bars(("SPY", "QQQ", "IWM"), "2026-01-02", "2026-01-09")
    assert len(bars) == 18
    assert {bar.symbol for bar in bars} == {"SPY", "QQQ", "IWM"}
    assert all(bar.venue == "NYSE Arca" for bar in bars)
    assert all(bar.adjustment_basis == "synthetic-unadjusted" for bar in bars)
    assert all(bar.provenance.source_ref == "fixture:m2.1-synthetic-us-etfs-v1" for bar in bars)
    assert provider.provider_metadata()["license"]["classification"] == "synthetic-internal"


def test_fixture_provider_rejects_invalid_ohlc_and_missing_symbol(tmp_path: Path) -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["rows"][0]["high"] = payload["rows"][0]["low"] - 1
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="OHLC"):
        FixtureMarketDataAdapter(invalid)

    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["license"]["classification"] = "unknown"
    unknown_license = tmp_path / "unknown-license.json"
    unknown_license.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="license classification"):
        FixtureMarketDataAdapter(unknown_license)

    provider = FixtureMarketDataAdapter(FIXTURE)
    with pytest.raises(ValueError, match="missing required symbol"):
        provider.bars(("SPY", "DIA"), "2026-01-02", "2026-01-09")
    with pytest.raises(ValueError, match="insufficient observations"):
        provider.bars(("SPY",), "2026-01-02", "2026-01-02")


def test_vibe_adapter_unavailable_error_is_actionable(tmp_path: Path) -> None:
    with pytest.raises(VibeTradingUnavailable, match="provider_unavailable:.*reference repository"):
        VibeTradingAdapter(FIXTURE, tmp_path / "missing-vibe-trading", "missing-python").run(("SPY",), "2026-01-02", "2026-01-09", 10_000.0)


def test_vibe_adapter_honors_cancellation_before_launch(tmp_path: Path) -> None:
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(ProviderCancelled, match="before launch"):
        VibeTradingAdapter(FIXTURE, tmp_path, sys.executable, tmp_path / "runs").run(
            ("SPY",), "2026-01-02", "2026-01-09", 10_000.0, cancel_event=cancel
        )


def test_provider_selection_rejects_unknown_provider(tmp_path: Path) -> None:
    with pytest.raises(ProviderSelectionError, match="must be one of"):
        selected_workflow(MarketWorkflow(RunStore(tmp_path / "selection")), "unknown")


def test_cli_and_api_dispatch_explicit_provider_selection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    selections: list[tuple[str, str | None]] = []

    def select(workflow: MarketWorkflow, provider: str, backtest_provider: str | None = None) -> MarketWorkflow:
        selections.append((provider, backtest_provider))
        return workflow

    monkeypatch.setattr("market_os.provider_selection.selected_workflow", select)
    monkeypatch.setattr(cli, "MarketWorkflow", lambda: MarketWorkflow(RunStore(tmp_path / "cli")))
    assert cli.main(["research", "CLI selection", "--symbols", "SPY", "--provider", "vibe-trading"]) == 0
    assert json.loads(capsys.readouterr().out)["run"]["status"] == "completed"

    handler = make_handler(MarketWorkflow(RunStore(tmp_path / "api")))
    from http.server import ThreadingHTTPServer
    from urllib.request import Request, urlopen

    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        payload = json.dumps({"objective": "API selection", "symbols": ["SPY"], "start": "2026-01-02", "end": "2026-01-06", "provider": "vibe-trading"}).encode()
        response = json.loads(urlopen(Request(f"http://127.0.0.1:{server.server_port}/v1/tasks", data=payload, headers={"Content-Type": "application/json"}), timeout=2).read())
        assert response["run"]["status"] == "completed"
    finally:
        server.shutdown()
        thread.join(timeout=2)
    assert selections == [("vibe-trading", None), ("vibe-trading", None)]


def test_fixture_deadline_and_cancellation_are_observable(tmp_path: Path) -> None:
    provider = FixtureMarketDataAdapter(FIXTURE)
    with pytest.raises(TimeoutError, match="deadline"):
        provider.bars(("SPY",), "2026-01-02", "2026-01-09", deadline=ProviderDeadline(0.0000001))

    cancel = threading.Event()
    cancel.set()
    class CancelledProvider:
        def run(self, *_args, cancel_event=None):
            if cancel_event and cancel_event.is_set():
                raise ProviderCancelled("cancelled")
            raise AssertionError("cancellation was not passed")

    workflow = MarketWorkflow(RunStore(tmp_path / "cancel"), backtest_provider=CancelledProvider())
    task = workflow.create_task("Cancel provider", ["SPY"], "2026-01-02", "2026-01-09")
    result = workflow.run(task, cancel)
    assert result["run"]["status"] == "cancelled"


@pytest.mark.integration
def test_actual_vibe_trading_backtest_is_numeric_and_reproducible(tmp_path: Path) -> None:
    python_executable = _vibe_python()
    if python_executable is None or not REFERENCE_ROOT.is_dir():
        pytest.skip("set MARKET_OS_VIBE_TRADING_PYTHON and MARKET_OS_VIBE_TRADING_ROOT for actual execution")
    adapter = VibeTradingAdapter(FIXTURE, REFERENCE_ROOT, python_executable, tmp_path / "runs")
    first = adapter.run(("SPY", "QQQ", "IWM"), "2026-01-02", "2026-01-09", 10_000.0)
    second = adapter.run(("SPY", "QQQ", "IWM"), "2026-01-02", "2026-01-09", 10_000.0)
    assert first.final_cash == pytest.approx(10_260.10)
    assert first.return_pct == pytest.approx(2.601)
    assert first.input_fingerprint == second.input_fingerprint
    assert first.equity_curve == second.equity_curve


@pytest.mark.integration
def test_actual_vibe_workflow_persists_citations_lineage_and_paper_plan(tmp_path: Path) -> None:
    python_executable = _vibe_python()
    if python_executable is None or not REFERENCE_ROOT.is_dir():
        pytest.skip("set MARKET_OS_VIBE_TRADING_PYTHON and MARKET_OS_VIBE_TRADING_ROOT for actual execution")
    base = MarketWorkflow(RunStore(tmp_path / "store"))
    adapter = VibeTradingAdapter(FIXTURE, REFERENCE_ROOT, python_executable, tmp_path / "runs")
    workflow = MarketWorkflow(base.store, evidence_provider=adapter, backtest_provider=adapter)
    task = workflow.create_task("Compare synthetic ETF candidates", ["SPY", "QQQ", "IWM"], "2026-01-02", "2026-01-09", idempotency_key="m2.1-actual")
    result = workflow.run(task)
    assert result["run"]["status"] == "completed"
    assert result["order_plan"]["mode"] == "paper"
    assert result["research"]["citations"] == ["vibe-fixture-SPY", "vibe-fixture-QQQ", "vibe-fixture-IWM", "document-policy"]
    assert {item["kind"] for item in result["artifacts"]} >= {"evidence", "research", "backtest", "order-plan", "risk-decision"}
    assert any(event.provenance["backtest"]["provider"] == "vibe-trading" for event in RunStore(tmp_path / "store").events_for(result["run"]["run_id"]))
    replay = workflow.run(workflow.create_task("Compare synthetic ETF candidates", ["SPY", "QQQ", "IWM"], "2026-01-02", "2026-01-09", idempotency_key="m2.1-actual"))
    assert replay == result
    assert MarketWorkflow(RunStore(tmp_path / "store")).inspect_run(result["run"]["run_id"])["run"]["status"] == "completed"
