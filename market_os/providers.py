"""Small, replaceable providers used by the first offline proof."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from .contracts import Evidence, BacktestResult

class EvidenceProvider(Protocol):
    def retrieve(self, objective: str, symbols: tuple[str, ...], start: str, end: str) -> list[Evidence]: ...

class BacktestProvider(Protocol):
    def run(self, symbols: tuple[str, ...], start: str, end: str, initial_cash: float) -> BacktestResult: ...

@dataclass(frozen=True)
class FixtureMarketProvider:
    prices: dict[str, tuple[tuple[str, float], ...]]

    def retrieve(self, objective: str, symbols: tuple[str, ...], start: str, end: str) -> list[Evidence]:
        result: list[Evidence] = []
        for symbol in symbols:
            rows = tuple((day, price) for day, price in self.prices[symbol] if start <= day <= end)
            if not rows:
                raise ValueError(f"no market evidence for {symbol} in {start}:{end}")
            content = ", ".join(f"{day}={price:.2f}" for day, price in rows)
            result.append(Evidence(f"market-{symbol}", "market", f"{symbol} daily bars", "fixture:market", rows[-1][0], content, (symbol,)))
        result.append(Evidence("document-policy", "document", "Paper trading policy", "fixture:policy", end, "All generated orders remain paper-only and require risk approval."))
        return result

@dataclass(frozen=True)
class DeterministicBacktestProvider:
    prices: dict[str, tuple[tuple[str, float], ...]]

    def run(self, symbols: tuple[str, ...], start: str, end: str, initial_cash: float) -> BacktestResult:
        selected = {s: tuple((d, p) for d, p in self.prices[s] if start <= d <= end) for s in symbols}
        if any(not rows for rows in selected.values()):
            raise ValueError("backtest requires at least one price row per symbol")
        first = {s: rows[0][1] for s, rows in selected.items()}
        last = {s: rows[-1][1] for s, rows in selected.items()}
        allocation = initial_cash / len(symbols)
        final_cash = sum(allocation * last[s] / first[s] for s in symbols)
        curve = tuple({"symbol": s, "start": first[s], "end": last[s]} for s in symbols)
        fingerprint = sha256(repr((symbols, start, end, initial_cash, curve)).encode()).hexdigest()
        return BacktestResult(initial_cash, final_cash, (final_cash / initial_cash - 1) * 100, curve, fingerprint)

def default_providers() -> tuple[FixtureMarketProvider, DeterministicBacktestProvider]:
    prices = {
        "SPY": (("2026-01-02", 100.0), ("2026-01-05", 101.0), ("2026-01-06", 102.0)),
        "QQQ": (("2026-01-02", 100.0), ("2026-01-05", 99.0), ("2026-01-06", 101.0)),
        "IWM": (("2026-01-02", 100.0), ("2026-01-05", 100.5), ("2026-01-06", 100.8)),
    }
    market = FixtureMarketProvider(prices)
    return market, DeterministicBacktestProvider(prices)
