# Finance UI reference for a read-only paper-market operator

Research date: 2026-10-31. Scope is product UI only: observable patterns from first-party public product pages and documentation. This is not investment research or a market view.

## Cross-product patterns

- **Linked workspace, not a single screen.** The common unit is a set of coordinated panels: watchlist or market selector, chart, order/order-status surface, and portfolio or risk context. TradingView, Coinbase Advanced, Koyfin, Bloomberg Launchpad, and IBKR Mosaic all describe customizable or linked workspaces. [TV-1][CB-1][KY-1][BBG-1][IB-1]
- **Watchlists are working surfaces.** They support custom lists, grouping, sorting, configurable columns, saved views, and quick drill-in to the selected instrument. This is more useful than a static ticker strip for a paper operator. [TV-2][KY-2][IB-2]
- **Charts preserve analytical state.** Useful state includes symbol, interval/timeframe, chart type, indicators, drawings, and templates/layouts. Users expect those choices to persist per workspace or instrument. [TV-3][TV-4][CB-2][IB-3]
- **Execution surfaces expose state explicitly.** Real products distinguish order entry, preview/confirmation, open orders, fills, partial fills, cancellation, and unavailable/view-only modes. A read-only operator should preserve these states visually while disabling mutation controls. [TV-5][CB-3][CB-4][IB-4]
- **Portfolio context sits next to the action.** Positions, P&L, margin/exposure, attribution, and what-if or stress views appear as nearby context rather than a separate mental workflow. [BBG-2][IB-1][IB-5][KY-3]

## Product observations

### TradingView

- Watchlists support custom sections, drag ordering, configurable metrics, table or row presentation, symbol details, and an advanced view with performance, risk, technical, and financial groupings. [TV-2]
- A saved chart layout contains the symbol, interval, chart type, indicators, drawings, colors, and settings. Multiple charts can synchronize symbol, interval, crosshair, and other context. [TV-3]
- The interval control supports common time units, favorites pinned to the toolbar, custom intervals, and keyboard entry of a numeric interval. That argues for a compact, high-frequency timeframe control with a small “More…” path. [TV-4]
- Paper Trading separates a dedicated order ticket from chart trading and depth-of-market views. The order flow includes an order preview/confirmation by default; positions expose close and partial-close actions. For our read-only surface, keep the ticket and preview anatomy but replace submit/close with disabled controls and an explicit `READ ONLY` state. [TV-1][TV-5]

### Coinbase Advanced

- The trade view is organized as distinct panels: price chart, depth chart, order book, buy/sell order panel, and open orders. The order panel and order-management view expose type, side, price, amount, fill percentage, fee, timestamp, and status. [CB-1][CB-3]
- The chart exposes both a time range and a candle interval, plus chart type and indicators. Coinbase documents per-market persistence for interval, chart type, indicators, drawings, order-book precision, and the primary chart/depth tab. [CB-1]
- The product has a useful explicit state for a paper operator: **View-only mode**, where a market can be inspected but not traded. This is a strong model for disabled execution states, and should be represented as a first-class status rather than inferred from disabled buttons. [CB-4]
- The order form remembers recent side, order type, time-in-force, and execution selections. For a read-only tool, persist the user’s inspection/filter state, but never imply that a remembered order configuration can be submitted. [CB-1]

### Koyfin

- Koyfin treats watchlists as configurable data tables: users can choose columns, groups, summary rows, sorting, notes, custom calculations, and reusable views. Watchlists are available as a main page, dashboard widget, and right-side sidebar. [KY-2][KY-4]
- Dashboards are composable workspaces containing watchlists, charts, news, and other widgets. Widgets are resizable, draggable, and linkable through groups so a selected instrument can coordinate multiple panels. [KY-1][KY-5]
- Portfolio surfaces emphasize holdings, lots, P/L, exposure, allocation, risk, and scenario-style analysis. This is useful precedent for a compact portfolio/risk strip beside the chart even when execution is out of scope. [KY-3]
- Koyfin documents a mobile app, browser zoom support for smaller screens, dark mode, and a `/` command bar for keyboard navigation. For our operator, retain a responsive single-column fallback and a visible keyboard route to symbol/search actions. [KY-6]
- Koyfin is primarily a research, portfolio, and reporting workspace rather than an execution-ticket reference. Reuse its context density and linking patterns, not its investment language or any implied trade action. [KY-1][KY-3]

### Bloomberg

- Bloomberg describes Launchpad as a customizable workspace for multi-asset security monitors, alerts, charting, and news. The useful pattern is a persistent operator workspace assembled from small, purpose-specific modules. [BBG-1]
- Bloomberg PORT unifies positions, risk, and performance, with exposure views and scenario analysis across asset classes. For a read-only paper operator, this supports an always-available “why this matters to the book” context area rather than a chart-only screen. [BBG-2]
- The Bloomberg Professional App carries worksheets to mobile and lets users monitor portfolios and securities in watch lists. The responsive cue is continuity of the selected workspace and monitoring context across desktop and mobile, not a literal desktop-scale layout on a phone. [BBG-3]
- Bloomberg’s public product pages expose limited accessibility detail. The practical takeaway is to make dense modules independently collapsible, keep status text next to color, and provide a narrow-screen reading order that preserves symbol → chart → portfolio context. [BBG-1][BBG-3]

### Interactive Brokers

- IBKR Mosaic is a unified customizable workspace with linkable windows for orders, charts, quotes, watchlists, news, and portfolio tools; Classic TWS offers a spreadsheet-style, keyboard-driven workflow. [IB-1][IB-4]
- Watchlists support sorting, custom views, configurable columns, and synchronization across trading platforms. The selected symbol can drive linked chart, quote, news, and order-entry windows. [IB-2][IB-6]
- Advanced Charts expose time interval, bar type, indicators, templates, snapshots, and multi-chart layouts. This supports a chart toolbar with explicit interval and saved-template controls rather than hidden defaults. [IB-3]
- IBKR places risk checks before order transmission: its Risk Navigator compares current portfolio-relative P&L with a what-if P&L including the queued order. A paper operator can use the same visual distinction for “current state” versus “simulated/selected scenario,” without exposing a transmit action. [IB-5]
- IBKR Mobile documents synchronized watchlists, alerts, account settings, portfolio monitoring, detailed charts, and mobile-optimized order tickets. It also documents hover help in TWS and keyboard-driven execution in Classic, useful cues for tooltips, visible focus, and non-pointer access. [IB-1][IB-6][IB-7]

## Translation into the read-only operator

1. **Desktop shell:** watchlist/market selector on the left; chart and timeframe controls in the center; read-only order/status panel on the right; portfolio/risk strip below or collapsible on narrow screens.
2. **State model:** make `view-only`, `paper`, `queued`, `partially filled`, `filled`, `cancelled`, `unavailable`, and `no data` explicit text states. Never communicate state by color alone.
3. **Persistence:** remember selected symbol, timeframe, chart type, indicators, panel visibility, and watchlist view locally. Do not persist or render credentials, broker connectivity, or a plausible live-submit affordance.
4. **Responsive behavior:** collapse panels in a deliberate order; preserve the selected symbol and current timeframe; turn wide tables into prioritized rows or horizontal scrolling with a clear accessible label.
5. **Accessibility:** use semantic table headers, visible keyboard focus, labeled icon buttons, tooltip text for unfamiliar controls, sufficient contrast, and a reduced-motion path. Keyboard shortcuts should supplement—not replace—visible controls.

## Sources

- [TV-1 — TradingView: Paper trading — main functionality](https://www.tradingview.com/support/solutions/43000516466-paper-trading-main-functionality/)
- [TV-2 — TradingView: Mastering the TradingView watchlists](https://www.tradingview.com/support/solutions/43000745825-mastering-the-tradingview-watchlists/)
- [TV-3 — TradingView: TradingView layouts: a quick guide](https://www.tradingview.com/support/solutions/43000746975-tradingview-layouts-a-quick-guide/)
- [TV-4 — TradingView: Time intervals](https://www.tradingview.com/support/solutions/43000747934-time-intervals-how-much-market-activity-each-candle-shows/)
- [TV-5 — TradingView: How to place an order on TradingView](https://www.tradingview.com/support/solutions/43000786671-how-to-place-an-order-on-tradingview/)
- [CB-1 — Coinbase Help: Coinbase Advanced dashboard overview](https://help.coinbase.com/en-au/coinbase/trading-and-funding/advanced-trade/dashboard-overview)
- [CB-2 — Coinbase Help: What is Coinbase Advanced?](https://help.coinbase.com/en/coinbase/trading-and-funding/advanced-trade/what-is-advanced-trade)
- [CB-3 — Coinbase Help: Order management](https://help.coinbase.com/en/coinbase/trading-and-funding/advanced-trade/order-management)
- [CB-4 — Coinbase Help: Market statuses](https://help.coinbase.com/en/coinbase/trading-and-funding/advanced-trade/market-availability)
- [KY-1 — Koyfin: Product features](https://www.koyfin.com/features/)
- [KY-2 — Koyfin: My Watchlists](https://www.koyfin.com/help/mywatchlists/)
- [KY-3 — Koyfin: Getting started with Koyfin](https://www.koyfin.com/help/getting-started-with-koyfin/)
- [KY-4 — Koyfin: My Views for Watchlists and Dashboards](https://www.koyfin.com/help/my-views/)
- [KY-5 — Koyfin: My Dashboards](https://www.koyfin.com/help/mydashboards-myd/)
- [KY-6 — Koyfin: Start Here](https://www.koyfin.com/help/getting-started-with-koyfin/)
- [BBG-1 — Bloomberg: Bloomberg Terminal](https://bloomberg.com/professional/solution/bloomberg-terminal/)
- [BBG-2 — Bloomberg: Portfolio & Risk Analytics](https://professional.bloomberg.com/products/bloomberg-terminal/portfolio-analytics/)
- [BBG-3 — Bloomberg: Bloomberg Professional App](https://bloomberg.com/mobile/businessweek)
- [IB-1 — Interactive Brokers: Trader Workstation](https://www.interactivebrokers.com/en/trading/tws.php)
- [IB-2 — IBKR Guides: Watchlist](https://www.ibkrguides.com/ibkrdesktop/watchlists.htm)
- [IB-3 — IBKR Guides: Advanced Chart](https://www.ibkrguides.com/traderworkstation/advanced-chart.htm)
- [IB-4 — IBKR Guides: Classic TWS Layout](https://www.ibkrguides.com/traderworkstation/classic-layout.htm)
- [IB-5 — IBKR Guides: Check Risk Pre Order](https://www.ibkrguides.com/traderworkstation/check-risk-pre-order.htm)
- [IB-6 — Interactive Brokers: TWS Introduction Webinar Notes](https://www.interactivebrokers.com/en/?f=%2Fen%2Fgeneral%2Feducation%2Fpdfnotes%2FWN-TWSIntroduction.php)
- [IB-7 — Interactive Brokers: IBKR Mobile Trading App](https://www.interactivebrokers.com/en/trading/ibkr-mobile.php)
