# Next Work Handoff — U6.4-F hosted evidence

**Checkpoint:** 2026-11-15, base commit `5dad8b3`
**Status:** local implementation complete; hosted Windows/Linux evidence is the
remaining U6.4-F gate.

## Where the project stands

- U6.4-D validates a signed, target-native artifact, its Electron binary,
  Python source sidecar, storage separation, slot metadata, and runtime
  boundary without installing anything.
- U6.4-E simulates a local install by copying through a sibling staging
  directory and publishing with one rename. It verifies the published tree,
  manifest, signature, entrypoints, slot metadata, and fresh mutable storage.
- U7-A through U7-O evidence products are complete.
- U8-A/U8-B remain gated. U8-C records the permanent paper-only owner
  decision. Connected promotion, production operations, provider access,
  credentials, mutation, and live execution stay disabled.
- U6.4-F now packages a target-native embedded CPython runtime when CI passes
  `--python-runtime`; the U6.4-D preflight and U6.4-E simulation accept and
  validate that runtime. No native service is registered.
- The full Understand Anything graph has been refreshed against the current
  610-file worktree: 2,250 nodes and 4,014 edges; exact counts and warnings
  are recorded in the current graph evidence.
  Validation found no structural issues and 125 no-edge node warnings. Its
  graph, metadata, and fingerprint baseline are under `.ua/`.
- The graph includes the U6.4-F contract, accepted ADR-0055, runtime validator,
  portable installer, and focused regression tests; metadata marks the
  snapshot as a working-tree analysis because these changes are uncommitted.
- U6.4-F is accepted as signed portable tar.gz for Windows/Linux, per-user
  without elevation, CI-frozen CPython 3.11.x from python.org, manual launch,
  no native service, preserved `python/.market_os` state, and a manual
  `<destination>.rollback` copy on upgrade.
- A local `install:contract:validate` gate validates the accepted fixture,
  rejects authorization while decisions are open or proposed, and fails closed
  on any boundary change. Its focused regression tests pass with the Electron
  suite.

## Current gate: U6.4-F hosted evidence

The accepted contract is recorded in
[`U6.4-F-INSTALLER-AND-PYTHON-RUNTIME-PLANNING.md`](U6.4-F-INSTALLER-AND-PYTHON-RUNTIME-PLANNING.md),
the accepted decision is
[`ADR-0055`](decisions/ADR-0055-u6-4-f-installer-planning.md), and the evidence
schema is [`u6-4-f-installation-contract.json`](evidence/u6-4-f-installation-contract.json).

### Accepted contract decisions

1. **Targets:** supported operating systems, architectures, and minimum
   versions for the first release.
2. **Package format and install scope:** per-user or machine-wide installation
   and the target-native package format for each platform.
3. **Python runtime:** bundled runtime and dependency layout, version pinning,
   offline availability, and how the runtime is validated.
4. **Mutable state:** application, configuration, cache, and portfolio data
   locations; upgrade behavior; preservation and migration rules; uninstall
   behavior.
5. **Permissions and lifecycle:** required elevation, launch model, service
   registration (if any), upgrade, rollback, and removal semantics.
6. **Trust and evidence:** signing inputs, provenance, manifest changes,
   install-result schema, and matching Windows/Linux CI evidence.
7. **Failure handling:** atomicity, retry behavior, interrupted installation,
   conflicting destinations, and recovery after verification failure.

These choices affect installed files, machine/user state, permissions, and
rollback. They are fixed in the accepted contract; the gate closes only after
matching Windows/Linux CI evidence is retained.

## Design direction

The existing seam runs from the U6.4-C signed artifact through the U6.4-D
preflight and U6.4-E simulation. Keep those checks authoritative and put
platform-specific installation behavior in a target adapter that returns a
small, inspectable result. Preserve locality: signature, manifest, storage,
and rollback rules should live behind that installation interface rather than
being reimplemented in each caller.

Keep Python as the domain and accounting authority. Electron owns shell and
installation orchestration only. Do not introduce a second portfolio or risk
implementation. The U8-C paper-only decision remains in force; U6.4-F is
offline packaging work and does not reopen connected or live execution.

## Next steps

1. Run the updated U6.4-C/D/E/F matrix on the existing Windows/Linux runners.
2. Retain `install-evidence.json`/Markdown, runtime manifests, and exact runner
   image values from each target.
3. Re-run the local Python suite after hosted evidence is available; do not
   claim hosted success from this uncommitted worktree.

## Reference artifacts

- [Unified roadmap](ROADMAP.md)
- [Unified phases](PHASES.md)
- [Project context](PROJECT-CONTEXT.md)
- [U6.4-D installer preflight](U6.4-D-INSTALLER-PREFLIGHT.md)
- [U6.4-E offline install simulation](U6.4-E-OFFLINE-INSTALL-SIMULATION.md)
- [U8-C permanent paper-only decision](U8-C-PERMANENT-PAPER-ONLY.md)
- [Goal prompt for the next implementation chat](GOAL-PROMPT.md)
