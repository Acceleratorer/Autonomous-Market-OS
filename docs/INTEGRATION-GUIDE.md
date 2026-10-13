# Integration guide

## Before moving code

Record the source repository, owning domain, public entry point, configuration inputs, persistent state, external services, and test command. A module is ready to move only when these are explicit.

## Adapter shape

Use a narrow adapter with typed request/response objects. Keep provider-specific objects inside the adapter. Return stable identifiers for runs, tasks, knowledge items, and artifacts. Emit lifecycle events around long-running work.

## State and artifacts

Use explicit storage interfaces. A path on disk, a JSONL file, or an in-memory singleton is an implementation detail until promoted into a contract. Every artifact should have lineage to its task/run and a media type.

## Security and operations

Apply least privilege to generated code, broker actions, external CLIs, and file access. Credentials belong in configuration/secret providers, never in fusion docs or event payloads. Preserve audit logs for tool calls and financial actions. Define timeouts, retries, cancellation, and idempotency for every remote adapter.

## Verification gate

For each integration slice, verify: import/build, happy path, failure path, restart behavior, state persistence, permission denial, and artifact retrieval. Compare outputs against the source project’s existing tests before replacing behavior.

## Documentation convention

Keep architectural decisions and non-obvious constraints in `docs/`. Keep generated inventories dated. Link to source files instead of copying code. Update `UNDERSTANDING-LOG.md` whenever an assumption is confirmed or rejected.
