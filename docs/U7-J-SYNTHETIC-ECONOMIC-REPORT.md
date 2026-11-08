# U7-J Synthetic Economic Report

U7-J adds a deterministic, read-only economic projection over a checked-in
synthetic fixture. It takes the useful accounting semantics from ClawWork:
token pricing, API cost channels, score-gated work income, balance changes,
and survival status. The repository keeps the implementation local and does
not import or run ClawWork.

## Command

```text
market-os synthetic economic-report \
  --fixture market_os/tests/fixtures/economic/u7_j_synthetic_economic.json \
  --markdown output/u7-j/economic-report.md \
  --json output/u7-j/economic-report.json
```

The report validates the fixture fingerprint, unique task IDs, finite
non-negative values, token/API pricing, and the payment threshold. It then
emits per-task cost, income, net change, balance, channel totals, aggregate
income/cost, and a ClawWork-shaped survival status. A report fingerprint is
computed from canonical JSON and excludes the fingerprint field itself.

## Boundary

The fixture and report are synthetic, paper-only, read-only, private, and
network-disabled. They make no provider, credential, payment, profitability,
or promotion claim. `promotion.approved` is always `false`; live execution and
mutation routes remain disabled.

The source reference is ClawWork's `EconomicTracker` semantics at commit
`9c73ac05fdb0bffdb23febdd971eb70f44dd46eb` (`livebench/agent/economic_tracker.py`).
The runtime is not imported, vendored, or modified.

## Evidence

The focused tests cover deterministic replay, threshold payment behavior,
channel and balance reconciliation, tamper rejection, and the CLI output.
CI renders the JSON and Markdown report and uploads both as U7-J evidence.
