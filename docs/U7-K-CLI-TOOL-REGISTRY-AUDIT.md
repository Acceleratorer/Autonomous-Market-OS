# U7-K CLI Tool Registry Audit

U7-K adds a deterministic, read-only audit for a typed CLI registry. It uses
the metadata shape documented by CLI-Anything's registry/list contract:
`name`, `version`, `entry_point`, `category`, `requires`, capabilities, and
installation status. The Market OS report does not import or execute a
generated CLI.

## Command

```text
market-os tools report \
  --fixture market_os/tests/fixtures/tools/u7_k_cli_anything_registry.json \
  --markdown output/u7-k/tool-registry.md \
  --json output/u7-k/tool-registry.json
```

The audit requires typed argv entry points, unique tool names, an explicit
allowlist and denylist, and a sandbox policy for every tool. Enabled tools may
only inspect or render local artifacts. Tools that require external services,
network access, credentials, mutation, or live execution are recorded as
`deferred` and must have `execution_enabled: false`.

## Boundary and lineage

The fixture and report are private, synthetic, paper-only, read-only, and
network-disabled. The report records zero executions and keeps promotion
disabled. The source reference is CLI-Anything's `registry.json` at commit
`34f519533bc175d2fe287ab8316b0dd99bb9cc43`; the source registry is not copied
into the runtime and the CLI-Anything repository is not modified.

CI renders and uploads the stable JSON and Markdown audit. This is a capability
inventory and denial report, not permission to run generated tools.
