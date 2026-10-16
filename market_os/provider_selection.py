"""Explicit provider selection for CLI and API entry points."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .adapters.lightrag import LightRAGFixtureAdapter
from .adapters.vibe_trading import VibeTradingAdapter
from .model_summary import DeterministicTestSummaryProvider
from .providers import BacktestProvider, EvidenceProvider, default_providers
from .workflow import MarketWorkflow


class ProviderSelectionError(ValueError):
    """A requested provider is unknown or cannot be constructed."""


class _CombinedEvidenceProvider:
    """Combine fixture market evidence with an explicit document adapter."""

    def __init__(self, market: EvidenceProvider, documents: LightRAGFixtureAdapter) -> None:
        self.market = market
        self.documents = documents

    @property
    def last_documents(self):
        return self.documents.last_documents

    @property
    def last_document_payload(self):
        return self.documents.last_document_payload

    @property
    def last_retrieval_result(self):
        return self.documents.last_retrieval_result

    def retrieve(self, objective: str, symbols: tuple[str, ...], start: str, end: str):
        return self.market.retrieve(objective, symbols, start, end) + self.documents.retrieve(objective, symbols, start, end)

    def provider_metadata(self):
        return {
            "market": {"provider": "fixture", "source_ref": "fixture:market"},
            "documents": self.documents.provider_metadata(),
        }


def selected_workflow(
    workflow: MarketWorkflow,
    provider: str = "fixture",
    backtest_provider: str | None = None,
    summary_provider: str | None = None,
) -> MarketWorkflow:
    """Return a root-owned workflow with explicitly selected provider adapters."""
    if summary_provider not in {None, "deterministic-test", "openai", "openai-recorded"}:
        raise ProviderSelectionError("summary_provider must be deterministic-test, openai-recorded, or openai when explicitly selected")
    if summary_provider is not None and provider != "lightrag":
        raise ProviderSelectionError("summary_provider requires provider=lightrag")
    if backtest_provider is None:
        if provider == "lightrag":
            raise ProviderSelectionError("lightrag is retrieval-only; select --backtest-provider vibe-trading")
        backtest_provider = provider
    evidence, backtest = _providers(provider, backtest_provider)
    summary = None
    if summary_provider == "deterministic-test":
        summary = DeterministicTestSummaryProvider()
    elif summary_provider == "openai-recorded":
        from .adapters.openai_summary import RecordedResponsesSummaryProvider

        summary = RecordedResponsesSummaryProvider.from_environment()
    elif summary_provider == "openai":
        from .adapters.openai_summary import OpenAIResponsesSummaryProvider

        summary = OpenAIResponsesSummaryProvider.from_environment()
    return MarketWorkflow(
        workflow.store,
        evidence_provider=evidence,
        backtest_provider=backtest,
        initial_cash=workflow.initial_cash,
        max_notional=workflow.max_notional,
        max_symbols=workflow.max_symbols,
        summary_provider=summary,
    )


def _providers(provider: str, backtest_provider: str) -> tuple[EvidenceProvider, BacktestProvider]:
    allowed_evidence = {"fixture", "vibe-trading", "lightrag"}
    allowed_backtest = {"fixture", "vibe-trading"}
    if provider not in allowed_evidence or backtest_provider not in allowed_backtest:
        raise ProviderSelectionError(
            f"provider must be one of {sorted(allowed_evidence)} and backtest_provider must be one of {sorted(allowed_backtest)}"
        )
    if provider == "fixture" and backtest_provider == "fixture":
        return default_providers()

    vibe = _vibe_adapter() if "vibe-trading" in {provider, backtest_provider} else None
    if provider == "vibe-trading":
        assert vibe is not None
        return vibe, vibe if backtest_provider == "vibe-trading" else default_providers()[1]
    if provider == "lightrag":
        documents = _lightrag_adapter()
        market, _ = default_providers()
        return _CombinedEvidenceProvider(market, documents), vibe or default_providers()[1]
    default_evidence, default_backtest = default_providers()
    return (
        default_evidence,
        vibe or default_backtest,
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


def _lightrag_adapter() -> LightRAGFixtureAdapter:
    package_root = Path(__file__).resolve().parents[1]
    reference_root = Path(
        os.environ.get(
            "MARKET_OS_LIGHTRAG_ROOT",
            str(package_root.parent / "company-projects" / "LightRAG"),
        )
    )
    python_executable = os.environ.get("MARKET_OS_LIGHTRAG_PYTHON", sys.executable)
    corpus = package_root / "market_os" / "tests" / "fixtures" / "lightrag" / "corpus.json"
    return LightRAGFixtureAdapter(corpus, reference_root, python_executable)
