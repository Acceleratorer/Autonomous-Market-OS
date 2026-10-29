# Local BTC dataset detail

This page extends the local dataset registry design for `/datasets/[datasetRevision]`.

- Reuse the operator's dark, dense palette, typography, boundary banner, metric cards, and table treatment.
- Show a static candlestick chart for only the current bounded page. Use filled bodies for rising candles, hollow bodies and dashed wicks for falling candles, and a neutral outline for flat candles; include a text legend and the visible page time range.
- Show the page high and low as exact stored strings. State that prices are in USDT and that the chart covers only the loaded page.
- Keep the exact seven-column OHLCV table as the value and accessible reference below the chart. Do not infer whole-dataset movement from a page.
- Keep the dataset revision, UTC coverage, and canonical fingerprint visible above the candle rows.
- Render exact price and volume strings from the backend; format only UTC timestamps in the server component.
- Keep the seven-column candle table in a labelled, keyboard-scrollable region on narrow screens. Keep the document itself within the viewport.
- Provide first-page and next-page GET links below the table and a registry link at the heading.
- State that each page verifies the stored Parquet hash and that replay is still required for canonical-content validation.
- Keep the surface read-only, server-rendered, and motion-free. Do not add chart dependencies, client state, ingestion actions, external fonts, or provider calls.
