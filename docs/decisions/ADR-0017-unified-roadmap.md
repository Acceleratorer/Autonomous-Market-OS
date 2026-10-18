# ADR-0017: Unified M/B Delivery Roadmap

- Status: Accepted
- Date: 2026-10-18

## Decision

Use one forward roadmap for Autonomous Market OS. Name new milestones `U0–U8` and map historical platform milestones `M0–M7` and BTC experiment milestones `B0–B7` onto them.

The original M roadmap remains historical. The BTC B roadmap becomes the first quantitative product track inside the unified roadmap. Shared capabilities are implemented once in Market OS and consumed by both the existing cited-research lane and the BTC lane.

## Mapping

| Unified | Historical |
|---|---|
| U0 | M0–M1 |
| U1 | M2 |
| U2 | B0–B1 |
| U3 | B2–B3 plus selected M5 evaluation controls |
| U4 | M3 + B4 |
| U5 | M4 web + B5 |
| U6 | M4 CLI/app + B6–B7 |
| U7 | M5 + selected M7 |
| U8 | M6 live-readiness decision |

## Rationale

The M sequence describes platform capabilities while the B sequence describes one domain experiment. Keeping them as parallel forward queues duplicates portfolio, evaluation, surface, and reporting work. A unified sequence makes the dependency order visible: local data and evaluation first, one shared paper engine next, then web, CLI, and app surfaces.

M2.9 remains an isolated blocked provider-smoke record and does not block U2 or U3. Jev remains an experimental provider in U3, with no policy or execution authority.

## Consequences

- New reports use the U milestone plus historical tags when useful, for example `U3/B2`.
- Existing M/B reports and evidence are not renamed.
- The next implementation prompt targets U3/B2.
- Live trading remains outside the normal sequence and requires a separate decision record.
