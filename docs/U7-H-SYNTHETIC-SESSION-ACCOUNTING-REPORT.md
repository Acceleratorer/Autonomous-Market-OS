# U7-H Synthetic Session Accounting Report

`market-os synthetic report` validates the checked-in B3.8 synthetic session
fixture through the existing manifest, strategy replay, and accounting store
contracts. It emits the versioned
`market-os.u7-h-synthetic-session-accounting-report@v1` projection as JSON and
Markdown.

The report keeps the reviewer surface bounded and explicit:

- manifest, replay, accounting, and fixture fingerprints;
- replay to accounting linkage and deterministic replay checks;
- bounded observation/fill counts;
- turnover, fees, spread, slippage, realized/unrealized/total PnL;
- final cash, BTC quantity, and mark price; and
- synthetic, paper-only, read-only, no-provider, no-network, and
  execution-disabled boundaries.

`promotion_approved` is always `false`. The interpretation is observability
only; the report makes no predictive or profitability claim.

```text
market-os synthetic report \
  --fixture market_os/tests/fixtures/b38/synthetic_session.json \
  --output-dir <session-output> \
  --markdown <synthetic-session-report.md> \
  --json <synthetic-session-report.json>
```

CI uploads the report and the validated session artifacts. Providers,
credentials, network calls, mutation routes, live execution, mobile, and
U5.5 owner-VM promotion remain deferred.
