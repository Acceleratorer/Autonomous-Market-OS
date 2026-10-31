import type { BtcHistoryCandle, BtcHistoryDataset } from "@/lib/market-api";

function formatUtc(timestampMs: number): string {
  return new Date(timestampMs).toISOString().replace(".000Z", "Z");
}

function compareDecimalStrings(left: string, right: string): number {
  const toScaledInteger = (value: string) => {
    const [significand, exponent = "0"] = value.toLowerCase().split("e");
    const [whole, fraction = ""] = significand.split(".");
    return {
      coefficient: BigInt(`${whole}${fraction}`),
      scale: BigInt(exponent) - BigInt(fraction.length),
    };
  };
  const leftDecimal = toScaledInteger(left);
  const rightDecimal = toScaledInteger(right);
  const commonScale = leftDecimal.scale < rightDecimal.scale ? leftDecimal.scale : rightDecimal.scale;
  const leftValue = leftDecimal.coefficient * BigInt(10) ** (leftDecimal.scale - commonScale);
  const rightValue = rightDecimal.coefficient * BigInt(10) ** (rightDecimal.scale - commonScale);
  return leftValue < rightValue ? -1 : leftValue > rightValue ? 1 : 0;
}

export function MarketCandleChart({
  dataset,
  candles,
}: {
  dataset: BtcHistoryDataset;
  candles: BtcHistoryCandle[];
}) {
  const points = candles.map((candle) => ({
    time: candle.openTimeMs,
    open: Number(candle.open),
    high: Number(candle.high),
    low: Number(candle.low),
    close: Number(candle.close),
    volume: Number(candle.volume),
  }));

  if (
    points.length < 2
    || points.some((point) =>
      !Number.isFinite(point.open)
      || !Number.isFinite(point.high)
      || !Number.isFinite(point.low)
      || !Number.isFinite(point.close)
      || !Number.isFinite(point.volume)
    )
  ) {
    return <p className="empty-state">A bounded OHLCV chart needs at least two numeric candles.</p>;
  }

  const minimum = Math.min(...points.map((point) => point.low));
  const maximum = Math.max(...points.map((point) => point.high));
  const range = maximum - minimum;
  const padding = range > 0 ? range * 0.08 : Math.max(Math.abs(maximum) * 0.02, 1);
  const plotMinimum = Math.max(0, minimum - padding);
  const plotMaximum = maximum + padding;
  const width = 1000;
  const plotLeft = 28;
  const plotRight = 972;
  const plotTop = 18;
  const plotBottom = 238;
  const plotHeight = plotBottom - plotTop;
  const volumeTop = 264;
  const volumeBottom = 332;
  const volumeMax = Math.max(...points.map((point) => point.volume), 1);
  const timeRange = points.at(-1)!.time - points[0].time;
  const xFor = (index: number) => timeRange > 0
    ? plotLeft + ((points[index].time - points[0].time) / timeRange) * (plotRight - plotLeft)
    : (plotLeft + plotRight) / 2;
  const yFor = (value: number) => plotTop + ((plotMaximum - value) / (plotMaximum - plotMinimum)) * plotHeight;
  const yVolume = (value: number) => volumeBottom - (value / volumeMax) * (volumeBottom - volumeTop);
  const description = `${dataset.symbol} ${dataset.interval} candlestick chart for ${points.length} bounded candles from ${formatUtc(points[0].time)} to ${formatUtc(points.at(-1)!.time)} UTC. Filled bodies close above their open; hollow bodies close below their open. Exact OHLCV values remain in the dataset detail table.`;
  const pageHigh = candles.reduce((highest, candle) =>
    compareDecimalStrings(candle.high, highest.high) > 0 ? candle : highest,
  );
  const pageLow = candles.reduce((lowest, candle) =>
    compareDecimalStrings(candle.low, lowest.low) < 0 ? candle : lowest,
  );

  return (
    <figure className="market-chart-figure">
      <figcaption className="market-chart-caption">
        <span>OHLCV from the current bounded candle page</span>
        <span className="market-chart-caption-meta">{points.length} samples</span>
      </figcaption>
      <div className="market-chart-readouts" aria-label="Current market readouts">
        <div>
          <span>Latest close</span>
          <strong>{candles.at(-1)!.close}</strong>
        </div>
        <div>
          <span>Page high</span>
          <strong>{pageHigh.high}</strong>
        </div>
        <div>
          <span>Page low</span>
          <strong>{pageLow.low}</strong>
        </div>
      </div>
      <svg
        className="market-chart-svg"
        viewBox={`0 0 ${width} 360`}
        preserveAspectRatio="none"
        role="img"
        aria-labelledby="market-desk-chart-title market-desk-chart-description"
      >
        <title id="market-desk-chart-title">{`${dataset.symbol} ${dataset.interval} candlestick chart`}</title>
        <desc id="market-desk-chart-description">{description}</desc>
        {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
          const y = plotTop + fraction * plotHeight;
          return <line key={fraction} className="market-chart-gridline" x1={plotLeft} x2={plotRight} y1={y} y2={y} />;
        })}
        <line className="market-chart-volume-axis" x1={plotLeft} x2={plotRight} y1={volumeBottom} y2={volumeBottom} />
        {points.map((point, index) => {
          const x = xFor(index);
          const step = (plotRight - plotLeft) / points.length;
          const bodyWidth = Math.max(4, Math.min(20, step * 0.55));
          const bullish = point.close >= point.open;
          const bodyTop = yFor(Math.max(point.open, point.close));
          const bodyBottom = yFor(Math.min(point.open, point.close));
          return (
            <g
              className={`market-candle-group ${bullish ? "market-candle-up" : "market-candle-down"}`}
              key={point.time}
            >
              <line className="market-candle-wick" x1={x} x2={x} y1={yFor(point.high)} y2={yFor(point.low)} />
              <rect
                className="market-candle-body"
                x={x - bodyWidth / 2}
                y={bodyTop}
                width={bodyWidth}
                height={Math.max(2.5, bodyBottom - bodyTop)}
              />
              <rect
                className="market-volume-bar"
                x={x - bodyWidth / 2}
                y={yVolume(point.volume)}
                width={bodyWidth}
                height={Math.max(1, volumeBottom - yVolume(point.volume))}
              />
            </g>
          );
        })}
      </svg>
      <div className="market-chart-times" aria-label="Chart time range">
        <time dateTime={new Date(points[0].time).toISOString()}>{formatUtc(points[0].time)}</time>
        <time dateTime={new Date(points.at(-1)!.time).toISOString()}>{formatUtc(points.at(-1)!.time)}</time>
      </div>
      <ul className="market-chart-legend" aria-label="Chart legend">
        <li><span className="market-legend-swatch market-legend-up" aria-hidden="true" />Up candle</li>
        <li><span className="market-legend-swatch market-legend-down" aria-hidden="true" />Down candle</li>
        <li><span className="market-legend-swatch market-legend-volume" aria-hidden="true" />Volume</li>
      </ul>
      <p className="market-chart-note">Read-only chart. Exact OHLCV values remain below; no quote stream, return inference, or order action is added.</p>
    </figure>
  );
}

export function MarketContextStrip({
  dataset,
  candles,
}: {
  dataset?: BtcHistoryDataset;
  candles?: BtcHistoryCandle[];
}) {
  const lastCandle = candles?.at(-1);
  const values = [
    { label: "Instrument", value: dataset?.symbol ?? "BTCUSDT" },
    { label: "Interval", value: dataset?.interval ?? "n/a" },
    { label: "Venue", value: dataset?.venue ?? "n/a" },
    { label: "Latest close", value: lastCandle?.close ?? "n/a" },
    { label: "Candles shown", value: candles ? String(candles.length) : "n/a" },
  ];

  return (
    <section className="market-context-strip" aria-label="Market context strip">
      {values.map((item) => (
        <div className="market-context-item" key={item.label}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
        </div>
      ))}
    </section>
  );
}

export function SyntheticFixturePreview({ symbol }: { symbol: string }) {
  return (
    <div className="market-fixture-preview">
      <div className="market-fixture-preview-head">
        <span className="market-fixture-badge">SYNTHETIC FIXTURE</span>
        <span className="market-fixture-caption">Local preview only</span>
      </div>
      <div className="market-fixture-preview-body">
        <div className="market-fixture-window" aria-hidden="true">
          <span className="market-fixture-window-crosshair" />
          <span className="market-fixture-window-axis market-fixture-window-axis-x" />
          <span className="market-fixture-window-axis market-fixture-window-axis-y" />
        </div>
        <div>
          <h3>{symbol} chart surface ready</h3>
          <p>Mount a validated local dataset to render OHLCV candles. No live quote or invented price is shown here.</p>
        </div>
      </div>
      <dl className="market-fixture-facts">
        <div><dt>Feed</dt><dd>None</dd></div>
        <div><dt>Mode</dt><dd>Paper</dd></div>
        <div><dt>Access</dt><dd>Read only</dd></div>
      </dl>
    </div>
  );
}
