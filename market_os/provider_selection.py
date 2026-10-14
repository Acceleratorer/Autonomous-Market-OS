"""Explicit provider selection for CLI and API entry points."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .adapters.vibe_trading import VibeTradingAdapter
from .providers import BacktestProvider, EvidenceProvider, default_providers
from .workflow import MarketWorkflow


class ProviderSelectionError(ValueError):
    """A requested provider is unknown or cannot be constructed."""


def selected_workflow(
    workflow: MarketWorkflow,
    provider: str = "fixture",
    backtest_provider: str | None = None,
) -> MarketWorkflow:
    """Return a root-owned workflow with explicitly selected provider adapters."""
    evidence, backtest = _providers(provider, backtest_provider or provider)
    return MarketWorkflow(
        workflow.store,
        evidence_provider=evidence,
        backtest_provider=backtest,
        initial_cash=workflow.initial_cash,
        max_notional=workflow.max_notional,
        max_symbols=workflow.max_symbols,
    )


def _providers(provider: str, backtest_provider: str) -> tuple[EvidenceProvider, BacktestProvider]:
    allowed = {"fixture", "vibe-trading"}
    if provider not in allowed or backtest_provider not in allowed:
        raise ProviderSelectionError(
            f"provider and backtest_provider must be one of {sorted(allowed)}"
        )
    if provider == "fixture" and backtest_provider == "fixture":
        return default_providers()

    adapter = _vibe_adapter() if "vibe-trading" in {provider, backtest_provider} else None
    if provider == "vibe-trading" and backtest_provider == "vibe-trading":
        assert adapter is not None
        return adapter, adapter
    default_evidence, default_backtest = default_providers()
    return (
        adapter if provider == "vibe-trading" else default_evidence,
        adapter if backtest_provider == "vibe-trading" else default_backtest,
    )


def _vibe_adapter() -> VibeTradingAdapter:
    package_root = Path(__file__).resolve().parents[1]
    reference_root = Path(
        os.environ.get(
            "MARKET_OS_VIBE_TRADING_ROOT",
            str(package_root.parent / "company-projects" / "Vibe-Trading"),
        )
    )
    python_executable = os.environ.get("MARKET_OS_VIBE_TRADING_PYTHON", sys.executable)
    fixture = package_root / "market_os" / "tests" / "fixtures" / "vibe_trading" / "etf_ohlcv.json"
    return VibeTradingAdapter(fixture, reference_root, python_executable)
