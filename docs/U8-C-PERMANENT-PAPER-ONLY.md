# U8-C Permanent Paper-Only Decision

## Scope

U8-C records the owner decision to keep Market OS in permanent paper-only
mode while no VM/access evidence exists. It consumes the U8-A live-readiness
pack and U8-B local operational-readiness pack, verifies that both remain
gated with blocked external gates, and emits a deterministic decision record.

The output schema is `market-os.u8-c-permanent-paper-only@v1`.

## Decision

The owner selected `permanent-paper-only`.

- `status`: `accepted`
- `classification`: `permanent_paper_only_by_owner_decision`
- `paper_only_permanent`: `true`
- `execution_boundary_change`: `false`
- credentials, providers, mutation routes, connected runtime, and live
  execution remain disabled;
- reopening requires a new explicit owner decision and a complete U8 review.

## Reproducible command

```text
python -m market_os.u8c_paper_mode \
  --u8-a docs/evidence/u8-a-live-readiness-decision.json \
  --u8-b docs/evidence/u8-b-local-operational-readiness.json \
  --decision permanent-paper-only \
  --markdown output/u8-c/permanent-paper-only.md \
  --json output/u8-c/permanent-paper-only.json
```

CI renders the pack after U8-A and U8-B and uploads the JSON/Markdown output.

## Evidence

The current committed decision is in
`docs/evidence/u8-c-permanent-paper-only.json` and
`docs/evidence/u8-c-permanent-paper-only.md`.
