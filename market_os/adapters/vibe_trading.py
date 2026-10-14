"""Offline Vibe-Trading adapter for deterministic Market OS research runs."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts import BacktestResult, Evidence
from ..providers import (
    CachePolicy,
    DeterministicFixture,
    MarketBar,
    LicenseMetadata,
    ProviderCapability,
    ProviderCancelled,
    ProviderDeadline,
    ProviderError,
    ProviderHealth,
    Provenance,
)


class VibeTradingUnavailable(RuntimeError):
    """The optional Vibe-Trading runtime cannot be used for this request."""

    def __init__(self, message: str, *, code: str = "provider_unavailable", retryable: bool = False) -> None:
        self.provider_error = ProviderError(code, message, retryable, "vibe-trading")
        super().__init__(f"{code}: {message}")


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise ValueError("fixture timestamps must use UTC")
    return parsed


def _timestamp(day: str) -> str:
    return f"{day}T00:00:00+00:00"


class FixtureMarketDataAdapter:
    """Normalize one versioned, synthetic OHLCV fixture without network I/O."""

    provider_name = "vibe-trading-fixture"

    def __init__(self, fixture_path: str | Path) -> None:
        self.fixture_path = Path(fixture_path).resolve()
        self.payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        self.fixture = DeterministicFixture(
            self.payload["fixture_id"],
            hashlib.sha256(self.fixture_path.read_bytes()).hexdigest(),
            "m2.1",
        )
        license_payload = self.payload.get("license")
        if not isinstance(license_payload, dict) or license_payload.get("classification") != "synthetic-internal":
            raise ValueError("fixture has an unknown or unsupported license classification")
        self.license = LicenseMetadata(
            license_payload["classification"],
            license_payload.get("license_name"),
            license_payload.get("attribution"),
            tuple(license_payload.get("restrictions", ())),
        )
        self._validate_payload()

    def health(self) -> ProviderHealth:
        return ProviderHealth(self.provider_name, "healthy", self.payload["retrieved_at"], "synthetic fixture")

    def capabilities(self) -> tuple[ProviderCapability, ...]:
        return (
            ProviderCapability("market-data", "daily-ohlcv-v1", "normalized synthetic daily bars"),
            ProviderCapability("backtest", "vibe-trading-local-v1", "offline local-loader backtest"),
        )

    def bars(
        self,
        symbols: tuple[str, ...],
        start: str,
        end: str,
        *,
        deadline: ProviderDeadline | None = None,
        cache: CachePolicy | None = None,
    ) -> tuple[MarketBar, ...]:
        del cache
        deadline_at = time.monotonic() + deadline.timeout_seconds if deadline else None
        if deadline_at is not None and deadline.timeout_seconds < 0.001:
            raise TimeoutError("fixture market-data deadline expired")
        requested = tuple(dict.fromkeys(symbols))
        missing = sorted(set(requested) - set(self.payload["required_symbols"]))
        if missing:
            raise ValueError(f"missing required symbol(s): {', '.join(missing)}")
        result: list[MarketBar] = []
        previous: dict[str, str] = {}
        observations = {symbol: 0 for symbol in requested}
        for row in self.payload["rows"]:
            if deadline_at is not None and time.monotonic() > deadline_at:
                raise TimeoutError("fixture market-data deadline expired")
            symbol = row["symbol"]
            if symbol not in requested or not start <= row["date"] <= end:
                continue
            if previous.get(symbol, "") >= row["date"]:
                raise ValueError(f"duplicate or unordered timestamp for {symbol}")
            previous[symbol] = row["date"]
            observations[symbol] += 1
            values = {key: float(row[key]) for key in ("open", "high", "low", "close", "volume")}
            if not all(math.isfinite(value) for value in values.values()) or any(
                values[key] <= 0 for key in ("open", "high", "low", "close")
            ) or values["volume"] < 0:
                raise ValueError(f"invalid non-finite or non-positive value for {symbol}")
            if not (
                values["low"] <= values["open"] <= values["high"]
                and values["low"] <= values["close"] <= values["high"]
                and values["low"] <= values["high"]
            ):
                raise ValueError(f"invalid OHLC relationship for {symbol} on {row['date']}")
            result.append(
                MarketBar(
                    symbol,
                    self.payload["venue"],
                    self.payload["currency"],
                    _timestamp(row["date"]),
                    values["open"],
                    values["high"],
                    values["low"],
                    values["close"],
                    values["volume"],
                    self.payload["adjustment_basis"],
                    self.provider_name,
                    self.payload["retrieved_at"],
                    Provenance(self.provider_name, f"fixture:{self.fixture.fixture_id}", self.payload["retrieved_at"]),
                )
            )
        missing_rows = sorted(symbol for symbol, count in observations.items() if count < 2)
        if missing_rows:
            raise ValueError(f"insufficient observations for {', '.join(missing_rows)}")
        return tuple(result)

    def retrieve(self, objective: str, symbols: tuple[str, ...], start: str, end: str) -> list[Evidence]:
        del objective
        bars = self.bars(symbols, start, end)
        result: list[Evidence] = []
        for symbol in symbols:
            selected = [asdict(bar) for bar in bars if bar.symbol == symbol]
            result.append(
                Evidence(
                    f"vibe-fixture-{symbol}",
                    "market",
                    f"Synthetic {symbol} daily OHLCV fixture",
                    f"fixture:{self.fixture.fixture_id}",
                    selected[-1]["timestamp"],
                    json.dumps(selected, sort_keys=True, separators=(",", ":")),
                    (symbol,),
                )
            )
        result.append(
            Evidence(
                "document-policy",
                "document",
                "Synthetic fixture and paper-only policy",
                f"fixture:{self.fixture.fixture_id}",
                self.payload["retrieved_at"],
                "Synthetic data is for internal deterministic testing only; generated orders remain paper-only.",
            )
        )
        return result

    def provider_metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "fixture_id": self.fixture.fixture_id,
            "fixture_sha256": self.fixture.checksum,
            "source_ref": f"fixture:{self.fixture.fixture_id}",
            "license": asdict(self.license),
        }

    def _validate_payload(self) -> None:
        if "synthetic" not in self.payload.get("label", "").lower():
            raise ValueError("fixture must be explicitly labelled synthetic")
        _utc(self.payload["retrieved_at"])
        required = tuple(self.payload["required_symbols"])
        if set(required) != {"SPY", "QQQ", "IWM"}:
            raise ValueError("fixture must contain the three required synthetic ETF symbols")
        seen: dict[str, list[str]] = {symbol: [] for symbol in required}
        for row in self.payload["rows"]:
            if row["symbol"] not in seen:
                raise ValueError(f"unexpected fixture symbol: {row['symbol']}")
            for field in ("venue", "currency", "adjustment_basis"):
                if field in row and row[field] != self.payload[field]:
                    raise ValueError(f"mixed {field} in fixture")
            seen[row["symbol"]].append(row["date"])
        if any(len(dates) < 2 or dates != sorted(set(dates)) for dates in seen.values()):
            raise ValueError("fixture has duplicate, unordered, or insufficient observations")
        self.bars(required, min(min(values) for values in seen.values()), max(max(values) for values in seen.values()))


class VibeTradingAdapter(FixtureMarketDataAdapter):
    """Run the actual Vibe-Trading backtest runner against local fixture CSVs."""

    provider_name = "vibe-trading"

    def __init__(
        self,
        fixture_path: str | Path,
        reference_root: str | Path,
        python_executable: str | Path | None = None,
        workspace: str | Path | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        super().__init__(fixture_path)
        self.reference_root = Path(reference_root).resolve()
        self.python_executable = str(python_executable or sys.executable)
        self.workspace = Path(workspace or tempfile.gettempdir())
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive and finite")
        self.timeout_seconds = timeout_seconds

    def run(
        self,
        symbols: tuple[str, ...],
        start: str,
        end: str,
        initial_cash: float,
        *,
        cancel_event: threading.Event | None = None,
        deadline: ProviderDeadline | None = None,
    ) -> BacktestResult:
        if not self.reference_root.is_dir():
            raise VibeTradingUnavailable(f"Vibe-Trading reference repository is unavailable: {self.reference_root}", code="provider_unavailable")
        if not Path(self.python_executable).exists():
            raise VibeTradingUnavailable(f"Vibe-Trading Python executable is unavailable: {self.python_executable}", code="dependency_unavailable")
        if not math.isfinite(initial_cash) or initial_cash <= 0:
            raise ValueError("initial_cash must be positive and finite")
        bars = self.bars(symbols, start, end)
        run_root = self.workspace.resolve()
        run_root.mkdir(parents=True, exist_ok=True)
        run_dir = Path(tempfile.mkdtemp(prefix="m2-1-vibe-", dir=run_root))
        env_root = run_dir / "home"
        data_dir = run_dir / "data"
        (run_dir / "code").mkdir(parents=True)
        data_dir.mkdir()
        try:
            sources: list[dict[str, Any]] = []
            for symbol in symbols:
                path = data_dir / f"{symbol}.csv"
                with path.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=("date", "open", "high", "low", "close", "volume"))
                    writer.writeheader()
                    for bar in bars:
                        if bar.symbol == symbol:
                            writer.writerow({"date": bar.timestamp[:10], **{key: getattr(bar, key) for key in ("open", "high", "low", "close", "volume")}})
                sources.append({"symbol": symbol, "path": str(path)})
            config_dir = env_root / ".vibe-trading" / "data-bridge"
            config_dir.mkdir(parents=True)
            (config_dir / "config.yaml").write_text(_fixture_yaml(sources), encoding="utf-8")
            (run_dir / "config.json").write_text(json.dumps({
                "codes": list(symbols), "start_date": start, "end_date": end,
                "source": "local", "interval": "1D", "initial_cash": initial_cash,
                "position_adjustment": "hold", "slippage_us": 0.0,
            }, sort_keys=True), encoding="utf-8")
            (run_dir / "code" / "signal_engine.py").write_text(
                "import pandas as pd\n\nclass SignalEngine:\n    def generate(self, data_map):\n        weight = 1.0 / len(data_map)\n        return {code: pd.Series(weight, index=df.index) for code, df in data_map.items()}\n",
                encoding="utf-8",
            )
            command = [
                self.python_executable,
                "-c",
                "import sys; from src.tools.backtest_tool import run_backtest; print(run_backtest(sys.argv[1]))",
                str(run_dir),
            ]
            env = os.environ.copy()
            env.update({
                "PYTHONPATH": str(self.reference_root / "agent"), "HOME": str(env_root),
                "USERPROFILE": str(env_root), "VIBE_TRADING_ALLOWED_RUN_ROOTS": str(run_root),
                "VIBE_TRADING_DATA_CACHE": "0", "VIBE_TRADING_TOOL_TIMEOUT_SECONDS": "30",
                "NO_PROXY": "*", "no_proxy": "*",
            })
            if cancel_event is not None and cancel_event.is_set():
                raise ProviderCancelled("Vibe-Trading backtest cancelled before launch")
            timeout_seconds = deadline.timeout_seconds if deadline else self.timeout_seconds
            process = subprocess.Popen(
                command,
                cwd=self.reference_root / "agent",
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            deadline_at = time.monotonic() + timeout_seconds
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    process.kill()
                    process.communicate()
                    raise ProviderCancelled("Vibe-Trading backtest cancelled during execution")
                remaining = deadline_at - time.monotonic()
                if remaining <= 0:
                    process.kill()
                    stdout, stderr = process.communicate()
                    raise VibeTradingUnavailable(
                        "Vibe-Trading backtest exceeded its execution deadline; "
                        f"stdout={stdout[-500:]}; stderr={stderr[-500:]}",
                        code="deadline_exceeded",
                        retryable=True,
                    )
                try:
                    stdout, stderr = process.communicate(timeout=min(remaining, 0.1))
                    break
                except subprocess.TimeoutExpired:
                    continue
            if process.returncode != 0:
                raise VibeTradingUnavailable(f"Vibe-Trading backtest process failed: {stderr[-1000:]}", code="provider_failed")
            if cancel_event is not None and cancel_event.is_set():
                raise ProviderCancelled("Vibe-Trading backtest cancelled after execution")
            try:
                envelope = json.loads(stdout.strip().splitlines()[-1])
            except (IndexError, json.JSONDecodeError) as exc:
                raise VibeTradingUnavailable(
                    "Vibe-Trading backtest returned an invalid result envelope",
                    code="provider_failed",
                ) from exc
            if envelope.get("status") != "ok":
                raise VibeTradingUnavailable(
                    f"Vibe-Trading backtest failed: {json.dumps(envelope, sort_keys=True)}",
                    code="provider_failed",
                )
            metrics_path = run_dir / "artifacts" / "metrics.json"
            metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else envelope.get("summary", {})
            equity = _read_equity(run_dir / "artifacts" / "equity.csv")
            fingerprint = hashlib.sha256(json.dumps({
                "fixture": self.fixture.checksum, "symbols": symbols, "start": start, "end": end,
                "initial_cash": initial_cash, "strategy": "equal-weight-long-hold", "source_commit": _git_head(self.reference_root),
            }, sort_keys=True).encode()).hexdigest()
            final_value = metrics.get("final_value")
            if not isinstance(final_value, (int, float)):
                final_value = metrics.get("final_equity")
            if not isinstance(final_value, (int, float)):
                final_value = equity[-1]["equity"] if equity else initial_cash
            final_cash = float(final_value)
            curve = tuple({"timestamp": row["timestamp"], "equity": row["equity"]} for row in equity)
            return BacktestResult(initial_cash, final_cash, (final_cash / initial_cash - 1) * 100, curve, fingerprint)
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)



def _fixture_yaml(sources: list[dict[str, Any]]) -> str:
    return "sources:\n" + "".join(f"  - symbol: {item['symbol']}\n    type: csv\n    path: {json.dumps(item['path'])}\n" for item in sources)


def _read_equity(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [{key: (float(value) if key == "equity" else value) for key, value in row.items()} for row in csv.DictReader(handle)]


def _git_head(root: Path) -> str:
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    return result.stdout.strip()
