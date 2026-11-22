"use client";

import { useEffect, useState } from "react";
import { MarketCandleChart, SyntheticFixturePreview } from "@/components/market-desk";
import type { BtcHistoryCandle, BtcHistoryDataset, BtcRealtimeCapture, LocalApiErrorKind } from "@/lib/market-api";

const REFRESH_INTERVAL_MS = 180_000;

type HistoricalFallback = {
  dataset: BtcHistoryDataset;
  candles: BtcHistoryCandle[];
} | null;

function formatUtc(value: string): string {
  return new Date(value).toISOString().replace(".000Z", "Z");
}

export function LiveBtcChart({
  initialCapture,
  initialStatus,
  fallback,
}: {
  initialCapture: BtcRealtimeCapture | null;
  initialStatus: "ready" | LocalApiErrorKind;
  fallback: HistoricalFallback;
}) {
  const [capture, setCapture] = useState(initialCapture);
  const [status, setStatus] = useState(initialStatus);
  const [refreshFailed, setRefreshFailed] = useState(false);

  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        const response = await fetch("/api/btc/realtime/latest", {
          method: "GET",
          cache: "no-store",
          credentials: "same-origin",
          redirect: "error",
          signal: AbortSignal.timeout(4_000),
        });
        if (!response.ok) throw new Error("local capture unavailable");
        const latest = await response.json() as BtcRealtimeCapture;
        if (active) {
          setCapture(latest);
          setStatus("ready");
          setRefreshFailed(false);
        }
      } catch {
        if (active) setRefreshFailed(true);
      }
    };

    void refresh();
    const timer = window.setInterval(() => void refresh(), REFRESH_INTERVAL_MS);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  if (capture && capture.candles.length >= 2) {
    const latest = capture.candles.at(-1)!;
    const latestTime = latest.receivedAt ?? capture.capture.updatedAt;
    return (
      <MarketCandleChart
        symbol={capture.capture.symbol}
        interval={capture.capture.interval}
        candles={capture.candles}
        sourceLabel={`Binance public · ${capture.capture.interval} · ${capture.capture.status} capture · updated ${formatUtc(capture.capture.updatedAt)}`}
        note={`Read-only local data. Latest candle received ${formatUtc(latestTime)}. UTC clock error bound is unverified, so this capture is excluded from B3.1 and paper decisions.${refreshFailed ? " Refresh failed; keeping the last valid chart." : ""}`}
      />
    );
  }

  if (fallback) {
    return (
      <MarketCandleChart
        dataset={fallback.dataset}
        candles={fallback.candles}
        sourceLabel="Validated historical BTC candles"
        note={`${capture ? "The live capture has not collected two closed candles yet; showing validated history while it fills." : "No local live capture is available yet; showing validated history. Start the capture runner to populate this chart."}${refreshFailed ? " The latest local refresh failed." : ""}`}
      />
    );
  }

  return (
    <div className="panel-body">
      <SyntheticFixturePreview symbol="BTCUSDT" />
      <p className="market-chart-note" role="status">
        {status === "missing"
          ? "No local live capture is available. Start the finite capture runner to populate this chart."
          : "The local BTC capture is unavailable; no live price is being invented."}
        {refreshFailed ? " The latest refresh also failed." : ""}
      </p>
    </div>
  );
}
